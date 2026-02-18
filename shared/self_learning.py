"""
SelfLearningEngine v2 — Profiles + Bandit Selection
=====================================================
Replaces the hyper-reactive "recalibrate every 5 trades" approach
with stable profile-based parameter management + UCB bandit selection.

Profiles (options example):
  P1_OPEN_TREND  — aggressive breakout, low confirmation, tight SL
  P2_OPEN_CHOP   — high confirmation, wide SL, few trades
  P3_MID_TREND   — standard breakout confirm (2 closes)
  P4_HIGH_IV     — higher conf threshold, wider SL
  P5_EXPIRY_DAY  — tighter time gates, premium-based only

Each profile has:
  - breakout confirmation type (1 / 2 closes / retest)
  - vol spike minimum
  - confidence threshold
  - SL / TP / trail parameters

Bandit uses UCB (Upper Confidence Bound) for profile selection.
Reward = net PnL - drawdown penalty - overtrade penalty.
Update cadence: after 25 trades OR End-of-day.
"""

from __future__ import annotations

import json
import math
import os
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

logger = logging.getLogger("self_learning")


@dataclass
class ProfileParams:
    """Tunable parameters associated with one profile."""
    profile_id: str
    label: str
    # Entry
    confirm_candles: int = 2            # 1, 2, or 0 (retest)
    entry_mode: str = "BREAKOUT_CONFIRM"  # or "BREAKOUT_RETEST"
    vol_spike_min: float = 1.5
    confidence_threshold: float = 70.0
    # Risk
    sl_pct: float = 0.10               # options: 10% premium
    tp1_pct: float = 0.12              # options: +12%
    tp1_book_pct: float = 0.60
    runner_trail_pct: float = 0.06     # min trail for runner
    # Equity overrides
    equity_sl_atr_mult: float = 1.0
    equity_tp1_atr_mult: float = 1.2
    # Trail
    trail_pct: float = 0.3
    activation_pct: float = 0.2


# ── Default profile library ──
DEFAULT_PROFILES: Dict[str, ProfileParams] = {
    "P1_OPEN_TREND": ProfileParams(
        profile_id="P1_OPEN_TREND",
        label="Open Trend",
        confirm_candles=1,
        vol_spike_min=1.3,
        confidence_threshold=65.0,
        sl_pct=0.08,
        tp1_pct=0.15,
        tp1_book_pct=0.50,
        runner_trail_pct=0.05,
        trail_pct=0.25,
        activation_pct=0.15,
    ),
    "P2_OPEN_CHOP": ProfileParams(
        profile_id="P2_OPEN_CHOP",
        label="Open Chop / Defensive",
        confirm_candles=2,
        vol_spike_min=2.0,
        confidence_threshold=80.0,
        sl_pct=0.12,
        tp1_pct=0.10,
        tp1_book_pct=0.70,
        runner_trail_pct=0.08,
        trail_pct=0.4,
        activation_pct=0.3,
    ),
    "P3_MID_TREND": ProfileParams(
        profile_id="P3_MID_TREND",
        label="Mid-Day Trend",
        confirm_candles=2,
        vol_spike_min=1.5,
        confidence_threshold=70.0,
        sl_pct=0.10,
        tp1_pct=0.12,
        tp1_book_pct=0.60,
        runner_trail_pct=0.06,
    ),
    "P4_HIGH_IV": ProfileParams(
        profile_id="P4_HIGH_IV",
        label="High IV / Volatile",
        confirm_candles=2,
        vol_spike_min=1.5,
        confidence_threshold=78.0,
        sl_pct=0.12,
        tp1_pct=0.15,
        tp1_book_pct=0.55,
        runner_trail_pct=0.08,
    ),
    "P5_EXPIRY_DAY": ProfileParams(
        profile_id="P5_EXPIRY_DAY",
        label="Expiry Day",
        confirm_candles=1,
        vol_spike_min=1.3,
        confidence_threshold=78.0,
        sl_pct=0.08,
        tp1_pct=0.20,
        tp1_book_pct=0.50,
        runner_trail_pct=0.05,
    ),
}


@dataclass
class BanditArm:
    """UCB statistics for one profile."""
    profile_id: str
    total_reward: float = 0.0
    n_selections: int = 0
    avg_reward: float = 0.0
    ucb_score: float = float("inf")


class SelfLearningEngine:
    """
    Profile + UCB-bandit engine.

    Usage::

        engine = SelfLearningEngine(data_dir="/app/data")
        profile = engine.select_profile(regime_profile_id="P3_MID_TREND")
        # ... trade using profile.confidence_threshold, profile.sl_pct, etc.
        engine.record_trade_result(profile_id, reward)
        # End of day:
        engine.eod_update()
    """

    LEARNING_FILE_NAME = "momentum_learning.json"
    UPDATE_CADENCE = 25   # update bandit every N trades

    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = data_dir
        self._profiles: Dict[str, ProfileParams] = {
            k: ProfileParams(**asdict(v)) for k, v in DEFAULT_PROFILES.items()
        }
        self._arms: Dict[str, BanditArm] = {
            k: BanditArm(profile_id=k) for k in self._profiles
        }
        self._total_selections: int = 0
        self._trade_buffer: List[dict] = []   # trades since last update
        self._version: int = 1
        self._forced_profile: Optional[str] = None
        self._load()

    # ------------------------------------------------------------------
    # Profile selection
    # ------------------------------------------------------------------

    def select_profile(self, regime_profile_id: str = "") -> ProfileParams:
        """
        Select the best profile using UCB.
        If *regime_profile_id* matches a known profile, prefer it (with UCB tiebreak).
        """
        if self._forced_profile and self._forced_profile in self._profiles:
            return self._profiles[self._forced_profile]

        # Recompute UCB scores
        self._recompute_ucb()

        # If regime recommends a profile and it wasn't terrible, use it
        if regime_profile_id in self._profiles:
            arm = self._arms[regime_profile_id]
            # Use regime suggestion if its UCB is within 80% of best
            best_ucb = max(a.ucb_score for a in self._arms.values())
            if arm.ucb_score >= 0.8 * best_ucb or arm.n_selections < 3:
                self._total_selections += 1
                arm.n_selections += 1
                return self._profiles[regime_profile_id]

        # UCB argmax
        best_id = max(self._arms, key=lambda k: self._arms[k].ucb_score)
        self._total_selections += 1
        self._arms[best_id].n_selections += 1
        return self._profiles[best_id]

    def force_profile(self, profile_id: str) -> bool:
        """Manually force a profile (for testing). Pass "" to clear."""
        if profile_id == "":
            self._forced_profile = None
            return True
        if profile_id in self._profiles:
            self._forced_profile = profile_id
            return True
        return False

    # ------------------------------------------------------------------
    # Trade recording
    # ------------------------------------------------------------------

    def record_trade_result(
        self,
        profile_id: str,
        pnl: float,
        drawdown: float = 0.0,
        regime: str = "",
        mfe_capture: float = 0.0,
    ) -> None:
        """Record a completed trade's result for the profile that was used."""
        # Reward = PnL - drawdown penalty - overshoot penalty
        reward = pnl - (0.5 * max(0, drawdown))

        self._trade_buffer.append({
            "profile_id": profile_id,
            "pnl": pnl,
            "reward": reward,
            "regime": regime,
            "mfe_capture": mfe_capture,
        })

        if profile_id in self._arms:
            arm = self._arms[profile_id]
            arm.total_reward += reward
            arm.avg_reward = arm.total_reward / max(1, arm.n_selections)

        # Auto-update cadence
        if len(self._trade_buffer) >= self.UPDATE_CADENCE:
            self._bandit_update()

    # ------------------------------------------------------------------
    # EOD / periodic update
    # ------------------------------------------------------------------

    def eod_update(self) -> dict:
        """End-of-day recalibration. Returns summary."""
        if not self._trade_buffer:
            return {"status": "no_trades"}
        summary = self._bandit_update()
        self._save()
        return summary

    def _bandit_update(self) -> dict:
        """Recalculate bandit statistics from buffer."""
        if not self._trade_buffer:
            return {}

        # Profile-level aggregation
        by_profile: Dict[str, List[dict]] = {}
        for t in self._trade_buffer:
            pid = t["profile_id"]
            by_profile.setdefault(pid, []).append(t)

        summary = {}
        for pid, trades in by_profile.items():
            wins = [t for t in trades if t["pnl"] > 0]
            total_pnl = sum(t["pnl"] for t in trades)
            avg_reward = sum(t["reward"] for t in trades) / len(trades)
            win_rate = len(wins) / len(trades) * 100 if trades else 0

            summary[pid] = {
                "trades": len(trades),
                "total_pnl": round(total_pnl, 2),
                "avg_reward": round(avg_reward, 2),
                "win_rate": round(win_rate, 1),
            }

        self._trade_buffer.clear()
        self._version += 1
        self._recompute_ucb()
        self._save()

        return {"version": self._version, "profiles": summary}

    # ------------------------------------------------------------------
    # UCB computation
    # ------------------------------------------------------------------

    def _recompute_ucb(self) -> None:
        """UCB1: score = avg_reward + c * sqrt(ln(N) / n_i)"""
        c = 1.41  # exploration coefficient
        n_total = max(1, self._total_selections)
        for arm in self._arms.values():
            if arm.n_selections == 0:
                arm.ucb_score = float("inf")
            else:
                exploration = c * math.sqrt(math.log(n_total) / arm.n_selections)
                arm.ucb_score = arm.avg_reward + exploration

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _filepath(self) -> str:
        return os.path.join(self.data_dir, self.LEARNING_FILE_NAME)

    def _load(self) -> None:
        fp = self._filepath()
        if not os.path.exists(fp):
            return
        try:
            with open(fp, "r") as f:
                data = json.load(f)
            self._version = data.get("version", 1)
            self._total_selections = data.get("total_selections", 0)
            for arm_dict in data.get("arms", []):
                pid = arm_dict.get("profile_id")
                if pid in self._arms:
                    a = self._arms[pid]
                    a.total_reward = arm_dict.get("total_reward", 0)
                    a.n_selections = arm_dict.get("n_selections", 0)
                    a.avg_reward = arm_dict.get("avg_reward", 0)
            # Reload profile overrides if saved
            for prof_dict in data.get("profiles", []):
                pid = prof_dict.get("profile_id")
                if pid in self._profiles:
                    for key in ("confidence_threshold", "sl_pct", "tp1_pct",
                                "vol_spike_min", "confirm_candles", "entry_mode"):
                        if key in prof_dict:
                            setattr(self._profiles[pid], key, prof_dict[key])
            logger.info(f"Loaded learning engine v{self._version}")
        except Exception as e:
            logger.error(f"Failed to load learning: {e}")

    def _save(self) -> None:
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            data = {
                "version": self._version,
                "total_selections": self._total_selections,
                "arms": [
                    {
                        "profile_id": a.profile_id,
                        "total_reward": round(a.total_reward, 4),
                        "n_selections": a.n_selections,
                        "avg_reward": round(a.avg_reward, 4),
                    }
                    for a in self._arms.values()
                ],
                "profiles": [asdict(p) for p in self._profiles.values()],
            }
            with open(self._filepath(), "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save learning: {e}")

    # ------------------------------------------------------------------
    # API / diagnostics
    # ------------------------------------------------------------------

    def get_profiles(self) -> List[dict]:
        """Return all profiles with their current parameters."""
        return [asdict(p) for p in self._profiles.values()]

    def get_bandit_stats(self) -> dict:
        """Return bandit arm statistics + selection probabilities."""
        self._recompute_ucb()
        total_ucb = sum(max(0, a.ucb_score) for a in self._arms.values()
                        if a.ucb_score != float("inf"))
        arms = []
        for a in self._arms.values():
            prob = 0.0
            if a.ucb_score == float("inf"):
                prob = 1.0  # unexplored — will be selected next
            elif total_ucb > 0:
                prob = max(0, a.ucb_score) / total_ucb
            arms.append({
                "profile_id": a.profile_id,
                "label": self._profiles[a.profile_id].label,
                "n_selections": a.n_selections,
                "avg_reward": round(a.avg_reward, 4),
                "ucb_score": round(a.ucb_score, 4) if a.ucb_score != float("inf") else "unexplored",
                "selection_probability": round(prob, 3),
            })
        return {
            "version": self._version,
            "total_selections": self._total_selections,
            "forced_profile": self._forced_profile,
            "arms": arms,
        }
