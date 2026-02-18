"""Unit tests for MetricsEngine — recording, daily report, KPIs."""

import sys
import os
import tempfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.metrics_engine import MetricsEngine, TradeMetrics


class TestMetricsEngine:
    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.engine = MetricsEngine(data_dir=self.tmp_dir)

    def _make_trade(self, trade_id: str, pnl: float, mfe: float = 0, mae: float = 0,
                    regime: str = "MID_TREND", profile: str = "P3_MID_TREND") -> TradeMetrics:
        return TradeMetrics(
            trade_id=trade_id,
            regime=regime,
            profile_id=profile,
            breakout_level=23050,
            entry_mode="BREAKOUT_CONFIRM",
            pnl=pnl,
            pnl_pct=pnl / 100 * 100,
            mfe=mfe,
            mae=mae,
            spread_cost=10,
            slippage_cost=5,
            entry_time="2025-03-10T10:00:00",
            exit_time="2025-03-10T10:30:00",
            hold_seconds=1800,
            exit_reason="TP1_HIT" if pnl > 0 else "SL_HIT",
        )

    def test_record_trade(self):
        self.engine.record_trade(self._make_trade("T-1", 500, mfe=700, mae=100))
        assert len(self.engine._trades) == 1

    def test_record_filtered(self):
        self.engine.record_filtered("Low volume")
        self.engine.record_filtered("Low volume")
        self.engine.record_filtered("VWAP magnet")
        assert len(self.engine._filtered_reasons) == 2
        assert self.engine._filtered_reasons["Low volume"] == 2

    def test_generate_daily_report(self):
        self.engine.record_trade(self._make_trade("T-1", 500, mfe=700, mae=100))
        self.engine.record_trade(self._make_trade("T-2", -200, mfe=50, mae=300))
        self.engine.record_trade(self._make_trade("T-3", 300, mfe=400, mae=50, regime="OPEN_TREND"))

        report = self.engine.generate_daily_report("2025-03-10")
        assert report.total_trades == 3
        assert report.total_pnl == 600
        assert report.wins == 2
        assert report.losses == 1
        assert len(report.by_regime) >= 1

    def test_compute_kpis(self):
        for i in range(10):
            pnl = 500 if i % 3 != 0 else -200
            self.engine.record_trade(self._make_trade(f"T-{i}", pnl, mfe=abs(pnl) * 1.2, mae=abs(pnl) * 0.3))

        kpis = self.engine.compute_kpis()
        assert "profit_factor" in kpis
        assert "expectancy" in kpis
        assert "win_rate" in kpis
        assert kpis["win_rate"] > 0

    def test_reset_daily(self):
        self.engine.record_filtered("test")
        self.engine.record_filtered("test2")
        self.engine.reset_daily()
        # reset_daily only clears filtered reasons, keeps trade history
        assert len(self.engine._filtered_reasons) == 0

    def test_empty_report(self):
        report = self.engine.generate_daily_report("2025-03-10")
        assert report.total_trades == 0
        assert report.total_pnl == 0
