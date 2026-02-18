"""
MarketDataStore — Rolling Candle Store + Derived Indicators
===========================================================
Maintains a rolling window of 1-min OHLCV candles (last 120 min)
and caches derived indicators updated on each new candle.

Used by both Options Scalping and Equity Intraday services.

Indicators computed:
  - ATR(14) on 1-min candles
  - VWAP + VWAP slope (10-min regression)
  - EMA(9) + EMA slope
  - RSI(7)
  - Rolling 15-min high / low
  - Opening Range High / Low (first 15 min of session)
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Candle:
    """One 1-minute OHLCV bar."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    oi: int = 0           # open interest (options)


@dataclass
class DerivedIndicators:
    """Cached indicator snapshot — refreshed each candle."""
    atr_14: float = 0.0
    vwap: float = 0.0
    vwap_slope: float = 0.0        # per-minute slope over last 10 min
    ema_9: float = 0.0
    ema_slope: float = 0.0         # per-minute slope over last 3 min
    rsi_7: float = 50.0
    high_15m: float = 0.0          # rolling 15-min high
    low_15m: float = 0.0           # rolling 15-min low
    or_high: float = 0.0           # Opening Range High (first 15 min)
    or_low: float = float("inf")   # Opening Range Low  (first 15 min)
    or_locked: bool = False        # True after first 15 min elapsed
    spot: float = 0.0              # latest close


class MarketDataStore:
    """
    Thread-safe rolling candle store with indicator engine.

    Usage::

        store = MarketDataStore(symbol="NIFTY")
        store.add_candle(candle)
        ind = store.indicators            # latest DerivedIndicators
        candles = store.get_candles(n=15)  # last 15 1-min candles
    """

    MAX_CANDLES = 120   # 2 hours of 1-min bars

    def __init__(self, symbol: str = ""):
        self.symbol = symbol
        self._candles: deque[Candle] = deque(maxlen=self.MAX_CANDLES)
        self._lock = threading.Lock()
        self._indicators = DerivedIndicators()
        # Internal EMA state
        self._ema_prev: Optional[float] = None
        self._ema_history: List[float] = []
        # VWAP accumulators (reset each session)
        self._vwap_cum_vol: float = 0.0
        self._vwap_cum_pv: float = 0.0
        self._vwap_history: List[float] = []
        # OR tracking
        self._session_start_minute: Optional[int] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_candle(self, candle: Candle) -> DerivedIndicators:
        """Append a 1-min candle and recompute all indicators."""
        with self._lock:
            self._candles.append(candle)
            self._recompute(candle)
            return self._indicators

    @property
    def indicators(self) -> DerivedIndicators:
        return self._indicators

    def get_candles(self, n: int = 0) -> List[Candle]:
        """Return last *n* candles (or all if n <= 0)."""
        with self._lock:
            if n <= 0:
                return list(self._candles)
            return list(self._candles)[-n:]

    @property
    def candle_count(self) -> int:
        return len(self._candles)

    def reset_session(self) -> None:
        """Call at 9:15 AM (or new session) to reset VWAP / OR."""
        with self._lock:
            self._candles.clear()
            self._indicators = DerivedIndicators()
            self._ema_prev = None
            self._ema_history.clear()
            self._vwap_cum_vol = 0.0
            self._vwap_cum_pv = 0.0
            self._vwap_history.clear()
            self._session_start_minute = None

    # ------------------------------------------------------------------
    # Internal computation
    # ------------------------------------------------------------------

    def _recompute(self, latest: Candle) -> None:
        candles = list(self._candles)
        n = len(candles)
        if n == 0:
            return

        self._indicators.spot = latest.close

        # ── ATR(14) ──
        self._indicators.atr_14 = self._calc_atr(candles, period=14)

        # ── VWAP + slope ──
        self._update_vwap(latest)
        self._indicators.vwap = self._current_vwap()
        self._indicators.vwap_slope = self._calc_slope(self._vwap_history, window=10)

        # ── EMA(9) + slope ──
        self._indicators.ema_9 = self._update_ema(latest.close, period=9)
        self._indicators.ema_slope = self._calc_slope(self._ema_history, window=3)

        # ── RSI(7) ──
        self._indicators.rsi_7 = self._calc_rsi(candles, period=7)

        # ── 15-min rolling high / low ──
        last15 = candles[-15:] if n >= 15 else candles
        self._indicators.high_15m = max(c.high for c in last15)
        self._indicators.low_15m = min(c.low for c in last15)

        # ── Opening Range (first 15 min) ──
        self._update_or(latest)

    # ---- ATR ----
    @staticmethod
    def _calc_atr(candles: List[Candle], period: int = 14) -> float:
        if len(candles) < 2:
            return candles[0].high - candles[0].low if candles else 0.0
        trs: List[float] = []
        for i in range(1, len(candles)):
            prev_close = candles[i - 1].close
            c = candles[i]
            tr = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
            trs.append(tr)
        if not trs:
            return 0.0
        # Simple moving average of True Range for the last *period* bars
        window = trs[-period:]
        return sum(window) / len(window)

    # ---- VWAP ----
    def _update_vwap(self, c: Candle) -> None:
        typical = (c.high + c.low + c.close) / 3.0
        vol = max(c.volume, 1)
        self._vwap_cum_pv += typical * vol
        self._vwap_cum_vol += vol
        vwap = self._vwap_cum_pv / self._vwap_cum_vol if self._vwap_cum_vol else typical
        self._vwap_history.append(vwap)
        if len(self._vwap_history) > 120:
            self._vwap_history = self._vwap_history[-120:]

    def _current_vwap(self) -> float:
        return self._vwap_history[-1] if self._vwap_history else 0.0

    # ---- EMA ----
    def _update_ema(self, close: float, period: int = 9) -> float:
        k = 2.0 / (period + 1)
        if self._ema_prev is None:
            self._ema_prev = close
        else:
            self._ema_prev = close * k + self._ema_prev * (1 - k)
        self._ema_history.append(self._ema_prev)
        if len(self._ema_history) > 120:
            self._ema_history = self._ema_history[-120:]
        return self._ema_prev

    # ---- RSI ----
    @staticmethod
    def _calc_rsi(candles: List[Candle], period: int = 7) -> float:
        if len(candles) < period + 1:
            return 50.0
        closes = [c.close for c in candles]
        gains: List[float] = []
        losses: List[float] = []
        for i in range(len(closes) - period, len(closes)):
            delta = closes[i] - closes[i - 1]
            if delta >= 0:
                gains.append(delta)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(-delta)
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    # ---- Slope (linear regression per minute) ----
    @staticmethod
    def _calc_slope(series: List[float], window: int = 10) -> float:
        data = series[-window:]
        n = len(data)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2.0
        y_mean = sum(data) / n
        num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(data))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den != 0 else 0.0

    # ---- Opening Range ----
    def _update_or(self, c: Candle) -> None:
        if self._indicators.or_locked:
            return
        if self._session_start_minute is None:
            self._session_start_minute = self._minute_of_day(c.timestamp)
        elapsed = self._minute_of_day(c.timestamp) - self._session_start_minute
        if elapsed < 15:
            if c.high > self._indicators.or_high:
                self._indicators.or_high = c.high
            if c.low < self._indicators.or_low:
                self._indicators.or_low = c.low
        else:
            self._indicators.or_locked = True

    @staticmethod
    def _minute_of_day(ts: datetime) -> int:
        return ts.hour * 60 + ts.minute


# ──────────────────────────────────────────────────────────────────
# Option-specific data store
# ──────────────────────────────────────────────────────────────────

@dataclass
class PremiumCandle:
    """1-min premium OHLCV for an option strike."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    oi: int = 0
    bid: float = 0.0
    ask: float = 0.0
    iv: float = 0.0


class OptionDataStore:
    """
    Thin wrapper storing ATM CE/PE premium series, IV, and spread.
    """

    MAX_BARS = 120

    def __init__(self) -> None:
        self.ce_candles: deque[PremiumCandle] = deque(maxlen=self.MAX_BARS)
        self.pe_candles: deque[PremiumCandle] = deque(maxlen=self.MAX_BARS)

    def add_ce_candle(self, c: PremiumCandle) -> None:
        self.ce_candles.append(c)

    def add_pe_candle(self, c: PremiumCandle) -> None:
        self.pe_candles.append(c)

    @property
    def ce_spread(self) -> float:
        if self.ce_candles:
            last = self.ce_candles[-1]
            return last.ask - last.bid if last.ask > 0 and last.bid > 0 else 0.0
        return 0.0

    @property
    def pe_spread(self) -> float:
        if self.pe_candles:
            last = self.pe_candles[-1]
            return last.ask - last.bid if last.ask > 0 and last.bid > 0 else 0.0
        return 0.0

    @property
    def ce_iv(self) -> float:
        return self.ce_candles[-1].iv if self.ce_candles else 0.0

    @property
    def pe_iv(self) -> float:
        return self.pe_candles[-1].iv if self.pe_candles else 0.0

    def premium_atr(self, side: str = "CE", period: int = 14) -> float:
        """ATR of premium candles (for premium-based trailing)."""
        candles = list(self.ce_candles if side == "CE" else self.pe_candles)
        return MarketDataStore._calc_atr(
            [Candle(c.timestamp, c.open, c.high, c.low, c.close, c.volume)
             for c in candles],
            period=period,
        ) if len(candles) >= 2 else 0.0

    def reset(self) -> None:
        self.ce_candles.clear()
        self.pe_candles.clear()
