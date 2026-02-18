"""Unit tests for MarketDataStore — indicators, rolling window, OR lock."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime
from shared.market_data_store import MarketDataStore, Candle, OptionDataStore, PremiumCandle


def _candle(minute: int, o: float, h: float, lo: float, c: float, v: int = 100000, oi: float = 0) -> Candle:
    total_min = 15 + minute
    hour = 9 + total_min // 60
    mins = total_min % 60
    ts = datetime(2025, 3, 10, hour, mins)
    return Candle(timestamp=ts, open=o, high=h, low=lo, close=c, volume=v, oi=oi)


class TestMarketDataStore:
    def test_add_candle_and_count(self):
        store = MarketDataStore("TEST")
        assert store.candle_count == 0
        store.add_candle(_candle(0, 100, 101, 99, 100.5))
        assert store.candle_count == 1

    def test_rolling_window_limit(self):
        store = MarketDataStore("TEST")
        # MAX_CANDLES = 120; fill more than that
        for i in range(130):
            store.add_candle(_candle(i, 100 + i, 101 + i, 99 + i, 100.5 + i))
        assert store.candle_count == 120
        candles = store.get_candles()
        assert len(candles) == 120

    def test_get_candles_n(self):
        store = MarketDataStore("TEST")
        for i in range(20):
            store.add_candle(_candle(i, 100, 101, 99, 100))
        assert len(store.get_candles(n=5)) == 5
        assert len(store.get_candles(n=100)) == 20

    def test_spot_updated(self):
        store = MarketDataStore("TEST")
        store.add_candle(_candle(0, 100, 101, 99, 100.5))
        assert store.indicators.spot == 100.5

    def test_ema9_computed(self):
        store = MarketDataStore("TEST")
        # Feed 10 candles with increasing closes
        for i in range(10):
            store.add_candle(_candle(i, 100 + i, 101 + i, 99 + i, 100 + i))
        assert store.indicators.ema_9 > 0
        # EMA should be close to recent prices
        assert 104 < store.indicators.ema_9 < 110

    def test_atr_computed(self):
        store = MarketDataStore("TEST")
        for i in range(20):
            store.add_candle(_candle(i, 100, 102, 98, 100, v=100000))
        assert store.indicators.atr_14 > 0
        # ATR should reflect the 4-point range
        assert 2 < store.indicators.atr_14 < 6

    def test_vwap_computed(self):
        store = MarketDataStore("TEST")
        for i in range(5):
            store.add_candle(_candle(i, 100, 101, 99, 100, v=100000))
        assert store.indicators.vwap > 0
        assert 99 < store.indicators.vwap < 101

    def test_rsi_computed(self):
        store = MarketDataStore("TEST")
        # Feed consistently rising prices → RSI should be high
        for i in range(20):
            store.add_candle(_candle(i, 100 + i, 101 + i, 99.5 + i, 100 + i))
        assert store.indicators.rsi_7 > 0
        assert store.indicators.rsi_7 > 60  # Strong uptrend

    def test_opening_range_locks(self):
        store = MarketDataStore("TEST")
        # First 15 candles (9:15-9:30) → OR should not be locked until after 15 min
        # Candles at 9:15, 9:16, ..., 9:29 = 15 candles
        for i in range(15):
            ts = datetime(2025, 3, 10, 9, 15 + i)
            store.add_candle(Candle(
                timestamp=ts, open=100 + i, high=105 + i, low=95 + i,
                close=100 + i, volume=100000,
            ))
        # OR should now have values
        assert store.indicators.or_high > 0
        assert store.indicators.or_low > 0
        assert store.indicators.or_high >= store.indicators.or_low

    def test_15m_high_low(self):
        store = MarketDataStore("TEST")
        for i in range(20):
            store.add_candle(_candle(i, 100, 100 + (i % 5), 100 - (i % 3), 100))
        assert store.indicators.high_15m > 0
        assert store.indicators.low_15m > 0

    def test_reset_session(self):
        store = MarketDataStore("TEST")
        for i in range(5):
            store.add_candle(_candle(i, 100, 101, 99, 100))
        assert store.candle_count == 5
        store.reset_session()
        assert store.candle_count == 0
        assert store.indicators.spot == 0


class TestOptionDataStore:
    def test_add_premium_candles(self):
        store = OptionDataStore()
        ts = datetime(2025, 3, 10, 9, 15)
        pc = PremiumCandle(timestamp=ts, open=50, high=52, low=48, close=51,
                          volume=10000, iv=15.0, bid=50.5, ask=51.5)
        store.add_ce_candle(pc)
        assert len(store.ce_candles) == 1
        assert store.ce_spread > 0

    def test_premium_atr(self):
        store = OptionDataStore()
        for i in range(20):
            ts = datetime(2025, 3, 10, 9, 15 + i)
            pc = PremiumCandle(timestamp=ts, open=50 + i, high=53 + i, low=48 + i,
                              close=51 + i, volume=10000, iv=15.0)
            store.add_ce_candle(pc)
        atr = store.premium_atr("CE", period=14)
        assert atr > 0

    def test_reset(self):
        store = OptionDataStore()
        ts = datetime(2025, 3, 10, 9, 15)
        store.add_ce_candle(PremiumCandle(timestamp=ts, open=50, high=52, low=48,
                                         close=51, volume=10000))
        store.reset()
        assert len(store.ce_candles) == 0
