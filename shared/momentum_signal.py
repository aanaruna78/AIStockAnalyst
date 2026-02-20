"""
MomentumSignalEngine — Replaces old generate_scalp_signal
==========================================================
Momentum-only entries: breakout + expansion + participation + trend alignment.

Entry conditions (all must be met):
  Breakout:   spot > max(ORH, High_15m) [bull] or spot < min(ORL, Low_15m) [bear]
  Expansion:  range_last_3 / ATR_14 > 1.2
  Participation: volume spike > 1.5x, OI confirms direction
  Trend alignment: EMA9 vs VWAP + VWAP slope

Confidence 0–100 (additive):
  Breakout strength:     0–25
  Expansion strength:    0–25
  Participation:         0–20
  Trend alignment:       0–15
  Cleanliness:           0–15

Entry modes:
  BREAKOUT_CONFIRM — 2 consecutive closes beyond breakout level
  BREAKOUT_RETEST  — reclaim after pullback holds above breakout
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from shared.market_data_store import Candle, DerivedIndicators


class EntryMode(str, Enum):
    BREAKOUT_CONFIRM = "BREAKOUT_CONFIRM"
    BREAKOUT_RETEST = "BREAKOUT_RETEST"


class SignalDirection(str, Enum):
    BULL = "BULL"    # CE for options, BUY for equity
    BEAR = "BEAR"    # PE for options, SELL for equity
    NONE = "NONE"


@dataclass
class MomentumSignal:
    """Output of the MomentumSignalEngine for a single tick."""
    direction: SignalDirection
    confidence: float = 0.0           # 0–100
    breakout_level: float = 0.0       # price level that was broken
    entry_mode: EntryMode = EntryMode.BREAKOUT_CONFIRM
    # Component scores
    breakout_score: float = 0.0       # 0–25
    expansion_score: float = 0.0      # 0–25
    participation_score: float = 0.0  # 0–20
    trend_score: float = 0.0          # 0–15
    cleanliness_score: float = 0.0    # 0–15
    # Reasons
    reasons: List[str] = field(default_factory=list)
    # Filter info
    is_filtered: bool = False
    filter_reason: str = ""


# ── Default thresholds (can be overridden per-profile) ──
@dataclass
class MomentumConfig:
    # Breakout
    breakout_buffer_pct: float = 0.0   # 0% buffer above ORH/H15
    confirm_candles: int = 1           # how many closes beyond breakout
    # Expansion
    expansion_ratio_min: float = 1.0
    # Participation
    vol_spike_min: float = 1.5
    oi_change_min_pct: float = 2.0     # OI change threshold for options
    # Confidence
    confidence_min: float = 70.0
    confidence_min_chop: float = 78.0  # during HIGH_IV / EXPIRY
    # Spread gate (options)
    max_spread_pct: float = 1.2        # spread / premium
    # Entry mode
    default_entry_mode: EntryMode = EntryMode.BREAKOUT_CONFIRM


class MomentumSignalEngine:
    """
    Stateful engine — tracks breakout-confirmation candle count
    so it can enforce "2 consecutive closes beyond breakout".

    Typical usage (inside signal loop)::

        sig = engine.evaluate(indicators, candles, config)
        if not sig.is_filtered and sig.confidence >= config.confidence_min:
            # Place trade
    """

    def __init__(self) -> None:
        # Tracks consecutive closes beyond breakout level for confirm mode
        self._bull_confirm_count: int = 0
        self._bear_confirm_count: int = 0
        # Retest tracking
        self._bull_retest_pullback_seen: bool = False
        self._bear_retest_pullback_seen: bool = False

    def evaluate(
        self,
        ind: DerivedIndicators,
        candles: List[Candle],
        config: MomentumConfig = MomentumConfig(),
        volume_avg: float = 1.0,
        oi_change_call_pct: float = 0.0,
        oi_change_put_pct: float = 0.0,
        spread_pct: float = 0.0,
        is_option: bool = True,
    ) -> MomentumSignal:
        """Evaluate momentum conditions and return a signal."""
        sig = MomentumSignal(direction=SignalDirection.NONE)

        if ind.spot <= 0 or ind.atr_14 <= 0:
            sig.is_filtered = True
            sig.filter_reason = "No data"
            return sig

        spot = ind.spot
        atr = ind.atr_14

        # ── Breakout detection ──
        bull_breakout_level = max(ind.or_high, ind.high_15m) if ind.or_locked else ind.high_15m
        bear_breakout_level = min(ind.or_low, ind.low_15m) if ind.or_locked else ind.low_15m

        bull_bo = spot > bull_breakout_level * (1 + config.breakout_buffer_pct / 100)
        bear_bo = spot < bear_breakout_level * (1 - config.breakout_buffer_pct / 100)

        if not bull_bo and not bear_bo:
            sig.is_filtered = True
            sig.filter_reason = f"No breakout (spot={spot:.2f}, ORH={ind.or_high:.2f}, ORL={ind.or_low:.2f}, H15={ind.high_15m:.2f}, L15={ind.low_15m:.2f})"
            self._bull_confirm_count = 0
            self._bear_confirm_count = 0
            self._bull_retest_pullback_seen = False
            self._bear_retest_pullback_seen = False
            return sig

        # Determine primary direction
        if bull_bo:
            direction = SignalDirection.BULL
            breakout_level = bull_breakout_level
        else:
            direction = SignalDirection.BEAR
            breakout_level = bear_breakout_level

        sig.direction = direction
        sig.breakout_level = round(breakout_level, 2)
        sig.entry_mode = config.default_entry_mode

        # ── Breakout strength score (0–25) ──
        bo_distance_pct = abs(spot - breakout_level) / breakout_level * 100
        sig.breakout_score = min(25.0, bo_distance_pct * 50)  # 0.5% above BO = full 25
        sig.reasons.append(f"Breakout dist {bo_distance_pct:.2f}% → score {sig.breakout_score:.1f}")

        # ── Expansion score (0–25) ──
        if len(candles) >= 3:
            last3 = candles[-3:]
            range_3 = max(c.high for c in last3) - min(c.low for c in last3)
        else:
            range_3 = 0.0
        expansion_ratio = range_3 / atr if atr > 0 else 0
        if expansion_ratio >= config.expansion_ratio_min:
            sig.expansion_score = min(25.0, (expansion_ratio - 1.0) * 25)
            sig.reasons.append(f"Expansion {expansion_ratio:.2f}x ATR → score {sig.expansion_score:.1f}")
        else:
            sig.is_filtered = True
            sig.filter_reason = f"Low expansion ({expansion_ratio:.2f} < {config.expansion_ratio_min})"
            return sig

        # ── Participation score (0–20) ──
        latest_vol = candles[-1].volume if candles else 0
        vol_spike = latest_vol / volume_avg if volume_avg > 0 else 0
        if vol_spike >= config.vol_spike_min:
            vol_part = min(10.0, (vol_spike - 1.0) * 10)
            sig.participation_score += vol_part
            sig.reasons.append(f"Vol spike {vol_spike:.1f}x → +{vol_part:.1f}")
        else:
            sig.is_filtered = True
            sig.filter_reason = f"Low volume ({vol_spike:.1f}x < {config.vol_spike_min}x)"
            return sig

        # OI participation (options only)
        if is_option:
            if direction == SignalDirection.BULL and oi_change_call_pct >= config.oi_change_min_pct:
                oi_part = min(10.0, oi_change_call_pct * 2)
                sig.participation_score += oi_part
                sig.reasons.append(f"CE OI +{oi_change_call_pct:.1f}% → +{oi_part:.1f}")
            elif direction == SignalDirection.BEAR and oi_change_put_pct >= config.oi_change_min_pct:
                oi_part = min(10.0, oi_change_put_pct * 2)
                sig.participation_score += oi_part
                sig.reasons.append(f"PE OI +{oi_change_put_pct:.1f}% → +{oi_part:.1f}")
            else:
                sig.participation_score += 0
                sig.reasons.append("OI not confirming (no penalty, less participation)")

        sig.participation_score = min(20.0, sig.participation_score)

        # ── Trend alignment score (0–15) ──
        if direction == SignalDirection.BULL:
            ema_aligned = ind.ema_9 > ind.vwap and ind.vwap_slope > 0
        else:
            ema_aligned = ind.ema_9 < ind.vwap and ind.vwap_slope < 0

        if ema_aligned:
            sig.trend_score = 15.0
            sig.reasons.append("Trend aligned (EMA + VWAP slope)")
        else:
            # Partial credit if at least EMA is correct direction
            if (direction == SignalDirection.BULL and ind.ema_9 > ind.vwap) or \
               (direction == SignalDirection.BEAR and ind.ema_9 < ind.vwap):
                sig.trend_score = 8.0
                sig.reasons.append("Partial trend (EMA ok, slope misaligned)")
            else:
                sig.trend_score = 0.0
                sig.reasons.append("Trend misaligned")

        # ── Cleanliness score (0–15) ──
        # Low wick noise + distance from VWAP
        vwap_dist_score = min(8.0, (abs(spot - ind.vwap) / atr) * 4)
        # Wick noise: ratio of wicks to body in last candle
        wick_score = 7.0  # default; reduce if wicks are large
        if candles:
            c = candles[-1]
            body = abs(c.close - c.open)
            full_range = c.high - c.low
            if full_range > 0:
                wick_ratio = 1 - (body / full_range)
                wick_score = max(0, 7.0 * (1 - wick_ratio))
        sig.cleanliness_score = min(15.0, vwap_dist_score + wick_score)
        sig.reasons.append(f"Cleanliness → {sig.cleanliness_score:.1f}")

        # ── Total confidence ──
        sig.confidence = round(
            sig.breakout_score + sig.expansion_score +
            sig.participation_score + sig.trend_score +
            sig.cleanliness_score, 1
        )

        # ── No-trade filters ──
        # VWAP magnet
        if abs(spot - ind.vwap) < 0.15 * atr:
            sig.is_filtered = True
            sig.filter_reason = "VWAP magnet zone"
            return sig

        # Spread gate (options)
        if is_option and spread_pct > config.max_spread_pct:
            sig.is_filtered = True
            sig.filter_reason = f"Spread too wide ({spread_pct:.2f}% > {config.max_spread_pct}%)"
            return sig

        # ── Entry-mode confirmation ──
        if config.default_entry_mode == EntryMode.BREAKOUT_CONFIRM:
            if direction == SignalDirection.BULL:
                if spot > breakout_level:
                    self._bull_confirm_count += 1
                else:
                    self._bull_confirm_count = 0
                if self._bull_confirm_count < config.confirm_candles:
                    sig.is_filtered = True
                    sig.filter_reason = f"Awaiting confirm ({self._bull_confirm_count}/{config.confirm_candles} closes)"
                    return sig
            else:
                if spot < breakout_level:
                    self._bear_confirm_count += 1
                else:
                    self._bear_confirm_count = 0
                if self._bear_confirm_count < config.confirm_candles:
                    sig.is_filtered = True
                    sig.filter_reason = f"Awaiting confirm ({self._bear_confirm_count}/{config.confirm_candles} closes)"
                    return sig

        elif config.default_entry_mode == EntryMode.BREAKOUT_RETEST:
            if direction == SignalDirection.BULL:
                if spot < breakout_level:
                    self._bull_retest_pullback_seen = True
                if not self._bull_retest_pullback_seen or spot < breakout_level:
                    sig.is_filtered = True
                    sig.filter_reason = "Awaiting retest pullback + reclaim"
                    return sig
            else:
                if spot > breakout_level:
                    self._bear_retest_pullback_seen = True
                if not self._bear_retest_pullback_seen or spot > breakout_level:
                    sig.is_filtered = True
                    sig.filter_reason = "Awaiting retest pullback + reclaim"
                    return sig

        return sig

    def reset(self) -> None:
        """Reset confirmation counters (call on session start)."""
        self._bull_confirm_count = 0
        self._bear_confirm_count = 0
        self._bull_retest_pullback_seen = False
        self._bear_retest_pullback_seen = False
