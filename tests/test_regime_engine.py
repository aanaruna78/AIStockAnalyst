"""Unit tests for RegimeEngine — classification, time gates, chop detection."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.regime_engine import RegimeEngine, Regime


class TestRegimeEngine:
    def setup_method(self):
        self.engine = RegimeEngine(atr_min_threshold=5.0)

    # ── Session boundary tests ──

    def test_open_trend(self):
        """9:15–9:45 with good conditions → OPEN_TREND."""
        result = self.engine.classify(
            spot=23000, vwap=22950, vwap_slope=2.0,
            atr=20, minute_of_day=560,  # 9:20
            range_last_3=30,
        )
        assert result.regime == Regime.OPEN_TREND
        assert result.is_trade_allowed

    def test_open_chop(self):
        """9:15–9:45 with VWAP magnet → OPEN_CHOP."""
        result = self.engine.classify(
            spot=23000, vwap=23002, vwap_slope=0.1,
            atr=20, minute_of_day=560,
            range_last_3=30,
        )
        assert result.regime == Regime.OPEN_CHOP
        assert not result.is_trade_allowed

    def test_mid_trend(self):
        """10:00–14:00 with strong trend → MID_TREND."""
        result = self.engine.classify(
            spot=23100, vwap=23000, vwap_slope=3.0,
            atr=20, minute_of_day=630,  # 10:30
            range_last_3=40,
        )
        assert result.regime == Regime.MID_TREND
        assert result.is_trade_allowed

    def test_mid_chop(self):
        """10:00–14:00 VWAP magnet → MID_CHOP."""
        result = self.engine.classify(
            spot=23000, vwap=23001, vwap_slope=0.0,
            atr=20, minute_of_day=700,  # 11:40
            range_last_3=15,
        )
        assert result.regime == Regime.MID_CHOP
        assert not result.is_trade_allowed

    def test_late_trend(self):
        """14:00–15:15 → LATE_TREND if conditions are good."""
        result = self.engine.classify(
            spot=23200, vwap=23100, vwap_slope=2.5,
            atr=20, minute_of_day=870,  # 14:30
            range_last_3=50,
        )
        assert result.regime == Regime.LATE_TREND
        assert result.is_trade_allowed

    def test_event_spike(self):
        """Large range spike → EVENT_SPIKE."""
        result = self.engine.classify(
            spot=23000, vwap=22900, vwap_slope=5.0,
            atr=20, minute_of_day=630,
            range_last_3=60,  # 60 > 2.5 * 20
        )
        assert result.regime == Regime.EVENT_SPIKE
        assert not result.is_trade_allowed

    # ── Edge cases ──

    def test_low_atr_blocks_trade(self):
        """ATR below threshold → no trade."""
        result = self.engine.classify(
            spot=23000, vwap=22950, vwap_slope=2.0,
            atr=3,  # below 5.0 threshold
            minute_of_day=560,
            range_last_3=5,  # keep below event spike threshold (2.5*3=7.5)
        )
        assert not result.is_trade_allowed
        assert "Low ATR" in result.no_trade_reason

    def test_chop_window_high_confidence_overrides(self):
        """11:00–13:15 (chop window) with high confidence → allow trade."""
        result = self.engine.classify(
            spot=23100, vwap=23000, vwap_slope=3.0,
            atr=20, minute_of_day=720,  # 12:00
            range_last_3=40,
            confidence=90,  # > 85
        )
        assert result.is_trade_allowed

    def test_chop_window_low_confidence_blocks(self):
        """11:00–13:15 (chop window) with low confidence → block."""
        result = self.engine.classify(
            spot=23100, vwap=23000, vwap_slope=3.0,
            atr=20, minute_of_day=720,  # 12:00
            range_last_3=40,
            confidence=50,  # < 85
        )
        assert not result.is_trade_allowed

    def test_result_to_dict(self):
        result = self.engine.classify(
            spot=23000, vwap=22950, vwap_slope=2.0,
            atr=20, minute_of_day=560,
            range_last_3=30,
        )
        d = RegimeEngine.result_to_dict(result)
        assert "regime" in d
        assert "is_trade_allowed" in d
        assert isinstance(d["regime"], str)
