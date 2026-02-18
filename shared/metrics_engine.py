"""
MetricsEngine — Trade Telemetry & Daily Reporting
==================================================
Tracks per-trade and daily aggregate metrics:

Per trade:
  regime, profile_id, breakout_level, entry_mode,
  MFE, MAE (premium for options / price for equity),
  capture_ratio = realized / MFE,
  cost breakdown (spread + slippage)

Daily report:
  trades by regime/profile, win rate, PF, expectancy,
  best/worst time windows, filtered trade reasons
"""

from __future__ import annotations

import json
import os
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("metrics_engine")


@dataclass
class TradeMetrics:
    """Rich per-trade telemetry persisted alongside trade data."""
    trade_id: str
    # Context
    regime: str = ""
    profile_id: str = ""
    breakout_level: float = 0.0
    entry_mode: str = ""
    # P&L
    pnl: float = 0.0
    pnl_pct: float = 0.0
    # MFE / MAE
    mfe: float = 0.0                # max favourable excursion (premium or price)
    mae: float = 0.0                # max adverse excursion
    capture_ratio: float = 0.0      # realised / MFE
    # Costs
    spread_cost: float = 0.0
    slippage_cost: float = 0.0
    total_cost: float = 0.0
    # Timing
    entry_time: str = ""
    exit_time: str = ""
    hold_seconds: float = 0.0
    exit_reason: str = ""


@dataclass
class DailyReport:
    """Aggregated daily performance report."""
    date: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0      # sum(wins) / abs(sum(losses))
    expectancy: float = 0.0         # avg PnL per trade
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_mfe: float = 0.0
    avg_mae: float = 0.0
    avg_capture_ratio: float = 0.0
    total_costs: float = 0.0
    # Regime breakdown
    by_regime: Dict[str, dict] = field(default_factory=dict)
    # Profile breakdown
    by_profile: Dict[str, dict] = field(default_factory=dict)
    # Best / worst window
    best_window: str = ""
    worst_window: str = ""
    # Filtered trades (reasons)
    filtered_reasons: Dict[str, int] = field(default_factory=dict)


class MetricsEngine:
    """
    Collects trade metrics and produces daily reports.

    Usage::

        engine = MetricsEngine(data_dir="/app/data")

        # Record each closed trade
        engine.record_trade(TradeMetrics(...))

        # Record filtered/skipped signals
        engine.record_filtered("VWAP magnet zone")

        # End of day
        report = engine.generate_daily_report("2026-02-18")
    """

    METRICS_FILE = "trade_metrics.json"
    REPORT_FILE = "daily_report.json"

    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = data_dir
        self._trades: List[TradeMetrics] = []
        self._filtered_reasons: Dict[str, int] = defaultdict(int)
        self._load()

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record_trade(self, tm: TradeMetrics) -> None:
        """Record metrics for a completed trade."""
        # Compute capture ratio
        if tm.mfe > 0:
            tm.capture_ratio = round(tm.pnl / tm.mfe, 3) if tm.pnl > 0 else 0.0
        tm.total_cost = round(tm.spread_cost + tm.slippage_cost, 2)
        self._trades.append(tm)
        self._save_metrics()

    def record_filtered(self, reason: str) -> None:
        """Record a signal that was filtered/skipped (for daily report)."""
        self._filtered_reasons[reason] += 1

    # ------------------------------------------------------------------
    # Daily report
    # ------------------------------------------------------------------

    def generate_daily_report(self, date_str: str = "") -> DailyReport:
        """Generate a DailyReport from today's trades."""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        day_trades = [t for t in self._trades if t.entry_time.startswith(date_str)]

        report = DailyReport(date=date_str)
        report.total_trades = len(day_trades)
        if not day_trades:
            report.filtered_reasons = dict(self._filtered_reasons)
            return report

        winners = [t for t in day_trades if t.pnl > 0]
        losers = [t for t in day_trades if t.pnl <= 0]
        report.wins = len(winners)
        report.losses = len(losers)
        report.win_rate = round(len(winners) / len(day_trades) * 100, 1)
        report.total_pnl = round(sum(t.pnl for t in day_trades), 2)
        report.expectancy = round(report.total_pnl / len(day_trades), 2)

        sum_wins = sum(t.pnl for t in winners) if winners else 0
        sum_losses = abs(sum(t.pnl for t in losers)) if losers else 0
        report.profit_factor = round(sum_wins / sum_losses, 2) if sum_losses > 0 else float("inf")

        report.avg_win = round(sum_wins / len(winners), 2) if winners else 0
        report.avg_loss = round(-sum_losses / len(losers), 2) if losers else 0

        report.avg_mfe = round(sum(t.mfe for t in day_trades) / len(day_trades), 2)
        report.avg_mae = round(sum(t.mae for t in day_trades) / len(day_trades), 2)

        captures = [t.capture_ratio for t in day_trades if t.capture_ratio > 0]
        report.avg_capture_ratio = round(sum(captures) / len(captures), 3) if captures else 0

        report.total_costs = round(sum(t.total_cost for t in day_trades), 2)

        # ── By regime ──
        regime_groups: Dict[str, List[TradeMetrics]] = defaultdict(list)
        for t in day_trades:
            regime_groups[t.regime or "UNKNOWN"].append(t)
        for regime, trades in regime_groups.items():
            w = [t for t in trades if t.pnl > 0]
            report.by_regime[regime] = {
                "trades": len(trades),
                "wins": len(w),
                "win_rate": round(len(w) / len(trades) * 100, 1),
                "pnl": round(sum(t.pnl for t in trades), 2),
            }

        # ── By profile ──
        profile_groups: Dict[str, List[TradeMetrics]] = defaultdict(list)
        for t in day_trades:
            profile_groups[t.profile_id or "UNKNOWN"].append(t)
        for pid, trades in profile_groups.items():
            w = [t for t in trades if t.pnl > 0]
            report.by_profile[pid] = {
                "trades": len(trades),
                "wins": len(w),
                "win_rate": round(len(w) / len(trades) * 100, 1),
                "pnl": round(sum(t.pnl for t in trades), 2),
            }

        # ── Best / worst time windows ──
        hour_pnl: Dict[str, float] = defaultdict(float)
        for t in day_trades:
            if t.entry_time:
                try:
                    hour = t.entry_time[11:13]  # "HH"
                    hour_pnl[hour] += t.pnl
                except (IndexError, ValueError):
                    pass
        if hour_pnl:
            report.best_window = max(hour_pnl, key=hour_pnl.get)
            report.worst_window = min(hour_pnl, key=hour_pnl.get)

        report.filtered_reasons = dict(self._filtered_reasons)

        # Save report
        self._save_report(report)
        return report

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_metrics_for_trade(self, trade_id: str) -> Optional[TradeMetrics]:
        return next((t for t in self._trades if t.trade_id == trade_id), None)

    def get_recent_metrics(self, n: int = 50) -> List[dict]:
        return [asdict(t) for t in self._trades[-n:]]

    def get_daily_summary(self) -> Optional[dict]:
        """Return last saved daily report as dict."""
        fp = os.path.join(self.data_dir, self.REPORT_FILE)
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    # ------------------------------------------------------------------
    # Momentum KPIs (for self-learning reward)
    # ------------------------------------------------------------------

    def compute_kpis(self, trades: Optional[List[TradeMetrics]] = None) -> dict:
        """
        Compute momentum KPIs used by SelfLearningEngine.
        """
        if trades is None:
            trades = self._trades[-50:]  # last 50

        if not trades:
            return {"profit_factor": 0, "expectancy": 0, "win_rate": 0,
                    "avg_win_loss_ratio": 0, "avg_capture_ratio": 0}

        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl <= 0]
        total = len(trades)

        sum_w = sum(t.pnl for t in winners)
        sum_l = abs(sum(t.pnl for t in losers))

        pf = sum_w / sum_l if sum_l > 0 else float("inf")
        expectancy = sum(t.pnl for t in trades) / total
        win_rate = len(winners) / total * 100

        avg_win = sum_w / len(winners) if winners else 0
        avg_loss = sum_l / len(losers) if losers else 1
        wl_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")

        captures = [t.capture_ratio for t in trades if t.capture_ratio > 0]
        avg_cap = sum(captures) / len(captures) if captures else 0

        return {
            "profit_factor": round(pf, 3),
            "expectancy": round(expectancy, 2),
            "win_rate": round(win_rate, 1),
            "avg_win_loss_ratio": round(wl_ratio, 3),
            "avg_capture_ratio": round(avg_cap, 3),
            "total_trades": total,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _metrics_path(self) -> str:
        return os.path.join(self.data_dir, self.METRICS_FILE)

    def _load(self) -> None:
        fp = self._metrics_path()
        if not os.path.exists(fp):
            return
        try:
            with open(fp) as f:
                data = json.load(f)
            for item in data.get("trades", []):
                self._trades.append(TradeMetrics(**{
                    k: v for k, v in item.items()
                    if k in TradeMetrics.__dataclass_fields__
                }))
            self._filtered_reasons = defaultdict(int, data.get("filtered_reasons", {}))
            # Only keep last 500 trades in memory
            if len(self._trades) > 500:
                self._trades = self._trades[-500:]
            logger.info(f"Loaded {len(self._trades)} trade metrics")
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")

    def _save_metrics(self) -> None:
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            data = {
                "trades": [asdict(t) for t in self._trades[-500:]],
                "filtered_reasons": dict(self._filtered_reasons),
            }
            with open(self._metrics_path(), "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def _save_report(self, report: DailyReport) -> None:
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            fp = os.path.join(self.data_dir, self.REPORT_FILE)
            with open(fp, "w") as f:
                json.dump(asdict(report), f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save report: {e}")

    def reset_daily(self) -> None:
        """Reset filtered reasons for a new day. Keep trade history."""
        self._filtered_reasons.clear()
