"""
RegimeEngine — Market Regime Classification
=============================================
Classify the market every minute to prevent chop trading.

Regime outputs:
  OPEN_TREND, OPEN_CHOP, MID_CHOP, MID_TREND, LATE_TREND, EVENT_SPIKE

Also returns:
  is_trade_allowed  (bool)
  recommended_profile_id  (str)
  no_trade_reason  (str, for logs)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Regime(str, Enum):
    OPEN_TREND = "OPEN_TREND"
    OPEN_CHOP = "OPEN_CHOP"
    MID_CHOP = "MID_CHOP"
    MID_TREND = "MID_TREND"
    LATE_TREND = "LATE_TREND"
    EVENT_SPIKE = "EVENT_SPIKE"


@dataclass
class RegimeResult:
    """Output of a regime classification tick."""
    regime: Regime
    is_trade_allowed: bool
    recommended_profile_id: str
    no_trade_reason: str = ""
    # Additional diagnostics
    vwap_distance_atr: float = 0.0   # abs(spot - VWAP) / ATR
    atr_value: float = 0.0
    vwap_slope: float = 0.0
    spot: float = 0.0


# ── Profile mapping by regime ──
_REGIME_PROFILE_MAP = {
    Regime.OPEN_TREND: "P1_OPEN_TREND",
    Regime.OPEN_CHOP: "P2_OPEN_CHOP",
    Regime.MID_TREND: "P3_MID_TREND",
    Regime.MID_CHOP: "P2_OPEN_CHOP",   # reuse chop profile
    Regime.LATE_TREND: "P3_MID_TREND",  # reuse mid trend
    Regime.EVENT_SPIKE: "P4_HIGH_IV",
}

# ── Time-of-day session boundaries (minutes from midnight IST) ──
_OPEN_START = 9 * 60 + 15     # 9:15
_OPEN_END = 9 * 60 + 45       # 9:45
_MID_END = 14 * 60 + 0        # 14:00
_LATE_END = 15 * 60 + 15      # 15:15

# ── Chop window: 11:00 – 13:15 (high-conf override available) ──
_CHOP_WINDOW_START = 11 * 60   # 11:00
_CHOP_WINDOW_END = 13 * 60 + 15  # 13:15


class RegimeEngine:
    """
    Stateless regime classifier.  Call ``classify()`` each minute
    (or each signal-loop tick) with latest indicator snapshot.

    Parameters
    ----------
    atr_min_threshold : float
        ATR below this = low movement (chop).  Default 5 for Nifty.
    vwap_magnet_ratio : float
        If abs(spot-VWAP)/ATR < this, price is "stuck at VWAP" → chop.
    event_spike_atr_mult : float
        If range-of-last-3-candles > this many ATRs → EVENT_SPIKE.
    """

    def __init__(
        self,
        atr_min_threshold: float = 5.0,
        vwap_magnet_ratio: float = 0.25,
        event_spike_atr_mult: float = 2.5,
    ):
        self.atr_min_threshold = atr_min_threshold
        self.vwap_magnet_ratio = vwap_magnet_ratio
        self.event_spike_atr_mult = event_spike_atr_mult

    def classify(
        self,
        spot: float,
        vwap: float,
        vwap_slope: float,
        atr: float,
        minute_of_day: int,
        range_last_3: float = 0.0,
        confidence: float = 0.0,
    ) -> RegimeResult:
        """
        Classify the current market regime.

        Parameters
        ----------
        spot : current close / LTP
        vwap : current VWAP
        vwap_slope : VWAP slope (per-minute, positive = rising)
        atr : ATR(14) on 1-min candles
        minute_of_day : e.g. 570 for 9:30 AM
        range_last_3 : high-low range of last 3 candles
        confidence : signal confidence (used for chop-window override)
        """
        # Safe-guard zero ATR
        if atr <= 0:
            atr = 0.01

        vwap_dist = abs(spot - vwap)
        vwap_distance_atr = vwap_dist / atr

        base = RegimeResult(
            regime=Regime.MID_TREND,
            is_trade_allowed=True,
            recommended_profile_id="P3_MID_TREND",
            vwap_distance_atr=round(vwap_distance_atr, 3),
            atr_value=round(atr, 3),
            vwap_slope=round(vwap_slope, 6),
            spot=spot,
        )

        # ── EVENT_SPIKE: explosive move ──
        if range_last_3 > 0 and range_last_3 > self.event_spike_atr_mult * atr:
            base.regime = Regime.EVENT_SPIKE
            base.recommended_profile_id = _REGIME_PROFILE_MAP[Regime.EVENT_SPIKE]
            base.is_trade_allowed = False
            base.no_trade_reason = f"Event spike (range {range_last_3:.1f} > {self.event_spike_atr_mult}×ATR={self.event_spike_atr_mult * atr:.1f})"
            return base

        # ── Time-of-day session ──
        is_open = _OPEN_START <= minute_of_day < _OPEN_END
        is_mid = _OPEN_END <= minute_of_day < _MID_END
        is_late = _MID_END <= minute_of_day <= _LATE_END

        # ── Chop detection ──
        is_chop = False
        chop_reason = ""

        # Rule 1: VWAP magnet
        if vwap_distance_atr < self.vwap_magnet_ratio:
            is_chop = True
            chop_reason = f"VWAP magnet (dist/ATR={vwap_distance_atr:.2f} < {self.vwap_magnet_ratio})"

        # Rule 2: Low ATR
        if atr < self.atr_min_threshold:
            is_chop = True
            chop_reason = f"Low ATR ({atr:.2f} < {self.atr_min_threshold})"

        # ── Time-of-day chop window enforcement ──
        in_chop_window = _CHOP_WINDOW_START <= minute_of_day < _CHOP_WINDOW_END

        if is_chop:
            if is_open:
                base.regime = Regime.OPEN_CHOP
            elif is_mid:
                base.regime = Regime.MID_CHOP
            else:
                base.regime = Regime.MID_CHOP  # late chop treated same
            base.recommended_profile_id = _REGIME_PROFILE_MAP[base.regime]
            base.is_trade_allowed = False
            base.no_trade_reason = chop_reason
            return base

        # ── Trend classification ──
        # Determine trend: VWAP slope positive + price above/below VWAP
        is_trend = abs(vwap_slope) > 0 and vwap_distance_atr >= self.vwap_magnet_ratio

        if is_open:
            base.regime = Regime.OPEN_TREND if is_trend else Regime.OPEN_CHOP
        elif is_late:
            base.regime = Regime.LATE_TREND if is_trend else Regime.MID_CHOP
        else:
            base.regime = Regime.MID_TREND if is_trend else Regime.MID_CHOP

        base.recommended_profile_id = _REGIME_PROFILE_MAP[base.regime]

        # ── Chop-window gate: block mid-day trades unless confidence ≥ 85 ──
        if in_chop_window and confidence < 85:
            base.is_trade_allowed = False
            base.no_trade_reason = f"Chop window (11:00-13:15) + confidence {confidence:.0f} < 85"
            return base

        # If classified as chop variant, block
        if base.regime in (Regime.OPEN_CHOP, Regime.MID_CHOP):
            base.is_trade_allowed = False
            base.no_trade_reason = "Regime is CHOP"

        return base

    # ------------------------------------------------------------------
    # Serialisation helpers (for API / persistence)
    # ------------------------------------------------------------------

    @staticmethod
    def result_to_dict(r: RegimeResult) -> dict:
        return {
            "regime": r.regime.value,
            "is_trade_allowed": r.is_trade_allowed,
            "recommended_profile_id": r.recommended_profile_id,
            "no_trade_reason": r.no_trade_reason,
            "vwap_distance_atr": r.vwap_distance_atr,
            "atr_value": r.atr_value,
            "vwap_slope": r.vwap_slope,
            "spot": r.spot,
        }
