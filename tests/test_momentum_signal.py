"""Unit tests for MomentumSignalEngine — scoring, filtering, breakout confirmation."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime
from shared.momentum_signal import (
    MomentumSignalEngine, MomentumConfig, SignalDirection,
)
from shared.market_data_store import Candle, DerivedIndicators


def _candle(minute: int, o: float, h: float, lo: float, c: float, v: int = 100000) -> Candle:
    ts = datetime(2025, 3, 10, 9, 15 + minute)
    return Candle(timestamp=ts, open=o, high=h, low=lo, close=c, volume=v)


def _make_indicators(
    spot: float = 23000,
    or_high: float = 23050,
    or_low: float = 22950,
    ema_9: float = 22980,
    ema_slope: float = 2.0,
    vwap: float = 22970,
    vwap_slope: float = 1.5,
    atr_14: float = 20,
    rsi_7: float = 60,
    high_15m: float = 23060,
    low_15m: float = 22940,
) -> DerivedIndicators:
    ind = DerivedIndicators()
    ind.spot = spot
    ind.or_high = or_high
    ind.or_low = or_low
    ind.or_locked = True
    ind.ema_9 = ema_9
    ind.ema_slope = ema_slope
    ind.vwap = vwap
    ind.vwap_slope = vwap_slope
    ind.atr_14 = atr_14
    ind.rsi_7 = rsi_7
    ind.high_15m = high_15m
    ind.low_15m = low_15m
    return ind


class TestMomentumSignalEngine:
    def setup_method(self):
        self.engine = MomentumSignalEngine()
        self.config = MomentumConfig()

    def _make_candles(self, n: int = 20, base: float = 23000, trend: float = 1.0) -> list:
        candles = []
        for i in range(n):
            price = base + i * trend
            candles.append(_candle(i, price, price + 3, price - 2, price + trend * 0.5, v=150000))
        return candles

    def test_bullish_breakout_signal(self):
        """Spot above OR high with expansion → BULL signal."""
        # spot must be > max(or_high, high_15m). Set high_15m < spot.
        # atr_14=8 so expansion_ratio = range_3 / 8 ≈ 1.4 > 1.2
        ind = _make_indicators(
            spot=23070, or_high=23050, or_low=22950,
            ema_9=23040, ema_slope=3.0,
            vwap=23020, vwap_slope=2.0,
            atr_14=8, rsi_7=65,
            high_15m=23055,
        )
        candles = self._make_candles(20, base=22990, trend=3)
        for c in candles[-5:]:
            c.volume = 300000

        # Call evaluate() twice for confirm_candles=2 default
        # Use confirm_candles=1 for this test
        config = MomentumConfig(confirm_candles=1)
        signal = self.engine.evaluate(
            ind=ind, candles=candles, config=config,
            volume_avg=100000, is_option=False,
        )
        assert signal.direction == SignalDirection.BULL
        assert signal.confidence > 0

    def test_bearish_breakout_signal(self):
        """Spot below OR low → BEAR signal."""
        # spot must be < min(or_low, low_15m)
        # atr_14=8 so expansion passes
        ind = _make_indicators(
            spot=22930, or_high=23050, or_low=22950,
            ema_9=22960, ema_slope=-3.0,
            vwap=22980, vwap_slope=-2.0,
            atr_14=8, rsi_7=35,
            low_15m=22945,
        )
        candles = self._make_candles(20, base=23010, trend=-3)
        for c in candles[-5:]:
            c.volume = 300000

        config = MomentumConfig(confirm_candles=1)
        signal = self.engine.evaluate(
            ind=ind, candles=candles, config=config,
            volume_avg=100000, is_option=False,
        )
        assert signal.direction == SignalDirection.BEAR
        assert signal.confidence > 0

    def test_no_breakout_filtered(self):
        """Spot inside OR → no breakout → filtered."""
        ind = _make_indicators(
            spot=23000, or_high=23050, or_low=22950,
            ema_9=22990, ema_slope=0.5,
        )
        candles = self._make_candles(20, base=22990, trend=0.5)

        signal = self.engine.evaluate(
            ind=ind, candles=candles, config=self.config,
            volume_avg=100000, is_option=False,
        )
        assert signal.is_filtered or signal.direction == SignalDirection.NONE

    def test_low_volume_filtered(self):
        """Low volume participation → filtered."""
        ind = _make_indicators(
            spot=23060, or_high=23050, or_low=22950,
            ema_9=23040, ema_slope=3.0,
            vwap=23020, atr_14=20,
        )
        candles = self._make_candles(20, base=22990, trend=3)
        # Keep volume LOW
        for c in candles:
            c.volume = 50000

        signal = self.engine.evaluate(
            ind=ind, candles=candles, config=self.config,
            volume_avg=100000, is_option=False,
        )
        # Either filtered or very low confidence
        assert signal.is_filtered or signal.confidence < 50

    def test_vwap_magnet_filtered(self):
        """Spot very close to VWAP → VWAP magnet filter."""
        ind = _make_indicators(
            spot=23060, or_high=23050, or_low=22950,
            vwap=23058,  # very close
            atr_14=20,
        )
        candles = self._make_candles(20, base=22990, trend=3)

        signal = self.engine.evaluate(
            ind=ind, candles=candles, config=self.config,
            volume_avg=100000, is_option=False,
        )
        # Should be filtered for VWAP magnet
        assert signal.is_filtered

    def test_wide_spread_filtered_for_options(self):
        """Wide spread → filtered for options."""
        # Ensure breakout + expansion pass first, then spread filter triggers
        ind = _make_indicators(
            spot=23070, or_high=23050, or_low=22950,
            ema_9=23040, ema_slope=3.0,
            vwap=23020, atr_14=8,
            high_15m=23055,
        )
        candles = self._make_candles(20, base=22990, trend=3)
        for c in candles[-5:]:
            c.volume = 300000

        config = MomentumConfig(confirm_candles=1)
        signal = self.engine.evaluate(
            ind=ind, candles=candles, config=config,
            volume_avg=100000,
            spread_pct=2.0,  # Very wide
            is_option=True,
        )
        assert signal.is_filtered
        assert "spread" in signal.filter_reason.lower()

    def test_reset_clears_state(self):
        """Reset clears confirmation counts."""
        self.engine._bull_confirm_count = 5
        self.engine._bear_confirm_count = 3
        self.engine.reset()
        assert self.engine._bull_confirm_count == 0
        assert self.engine._bear_confirm_count == 0

    def test_confidence_components_sum(self):
        """All component scores should sum to confidence."""
        ind = _make_indicators(
            spot=23070, or_high=23050, or_low=22950,
            ema_9=23040, ema_slope=3.0,
            vwap=23020, vwap_slope=2.0,
            atr_14=8, rsi_7=65,
            high_15m=23055,
        )
        candles = self._make_candles(20, base=22990, trend=3)
        for c in candles[-5:]:
            c.volume = 300000

        config = MomentumConfig(confirm_candles=1)
        signal = self.engine.evaluate(
            ind=ind, candles=candles, config=config,
            volume_avg=100000, is_option=False,
        )
        if not signal.is_filtered:
            total = (signal.breakout_score + signal.expansion_score +
                    signal.participation_score + signal.trend_score +
                    signal.cleanliness_score)
            assert abs(signal.confidence - total) < 0.1
