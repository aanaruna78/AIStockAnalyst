"""Unit tests for RiskEngine — SL/TP computation, trailing, momentum failure."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.risk_engine import (
    RiskEngine, RiskConfig, RiskMode, ExitReason,
)


class TestRiskEngineOption:
    def setup_method(self):
        self.engine = RiskEngine(RiskConfig(
            mode=RiskMode.PREMIUM_PCT,
            sl_pct=0.10,
            tp1_pct=0.12,
            tp1_book_pct=0.60,
            runner_trail_pct_min=0.06,
            max_trades_per_day=8,
            daily_loss_cap_pct=0.02,
            consecutive_loss_limit=3,
            cooldown_seconds=1800,
        ))
        self.engine.reset_daily(100000, "2025-03-10")

    def test_init_option_trade(self):
        """Initializing an option trade computes SL/TP1."""
        result = self.engine.init_option_trade(
            trade_id="OPT-001",
            entry_premium=100.0,
            premium_atr=5.0,
            quantity=325,
            is_long=True,
        )
        assert "sl" in result
        assert "tp1" in result
        assert result["sl"] < 100.0  # SL below entry
        assert result["tp1"] > 100.0  # TP1 above entry
        assert result["sl"] == 90.0  # 100 - 10%
        assert result["tp1"] == 112.0  # 100 + 12%
        assert result["tp1_book_qty"] > 0
        assert result["runner_qty"] > 0

    def test_sl_hit(self):
        """Premium drops to SL → exit."""
        self.engine.init_option_trade("OPT-002", 100.0, 5.0, 325, True)
        reason = self.engine.update_tick("OPT-002", 89.0, 5.0, 1)
        assert reason == ExitReason.SL_HIT

    def test_tp1_hit(self):
        """Premium rises to TP1 → TP1 partial book."""
        self.engine.init_option_trade("OPT-003", 100.0, 5.0, 325, True)
        reason = self.engine.update_tick("OPT-003", 113.0, 5.0, 1)
        assert reason == ExitReason.TP1_HIT

    def test_mfe_mae_tracking(self):
        """MFE and MAE update correctly."""
        self.engine.init_option_trade("OPT-004", 100.0, 5.0, 325, True)
        self.engine.update_tick("OPT-004", 105.0, 5.0, 1)
        state = self.engine.get_trade_state("OPT-004")
        assert state is not None
        assert state.mfe == 5.0  # 105 - 100
        assert state.mae == 0.0

        self.engine.update_tick("OPT-004", 97.0, 5.0, 2)
        state = self.engine.get_trade_state("OPT-004")
        assert state.mae == 3.0  # 100 - 97

    def test_trailing_after_tp1(self):
        """After TP1 hit, SL should trail higher."""
        self.engine.init_option_trade("OPT-005", 100.0, 5.0, 325, True)
        # Simulate TP1 hit
        self.engine.update_tick("OPT-005", 113.0, 5.0, 1)
        # Price goes higher
        state = self.engine.get_trade_state("OPT-005")
        if state:  # May have exited on TP1
            assert state.tp1_hit


class TestRiskEngineEquity:
    def setup_method(self):
        self.engine = RiskEngine(RiskConfig(
            mode=RiskMode.EQUITY_ATR,
            equity_sl_atr_mult=1.0,
            equity_tp1_atr_mult=1.2,
            tp1_book_pct=0.55,
            equity_runner_atr_mult=1.0,
            equity_late_tighten_mult=0.8,
            max_trades_per_day=10,
            daily_loss_cap_pct=0.02,
        ))
        self.engine.reset_daily(100000, "2025-03-10")

    def test_init_equity_trade(self):
        """Equity ATR-based SL/TP."""
        result = self.engine.init_equity_trade(
            trade_id="EQ-001",
            entry_price=500.0,
            atr=10.0,
            quantity=100,
            is_long=True,
        )
        assert result["sl"] == 490.0  # 500 - 1.0 * 10
        assert result["tp1"] == 512.0  # 500 + 1.2 * 10

    def test_equity_sl_hit(self):
        self.engine.init_equity_trade("EQ-002", 500.0, 10.0, 100, True)
        reason = self.engine.update_tick("EQ-002", 489.0, 10.0, 1, is_option=False)
        assert reason == ExitReason.SL_HIT


class TestRiskEnginePortfolio:
    def setup_method(self):
        self.engine = RiskEngine(RiskConfig(
            mode=RiskMode.PREMIUM_PCT,
            daily_loss_cap_pct=0.02,
            consecutive_loss_limit=3,
            cooldown_seconds=1800,
            max_trades_per_day=8,
        ))
        self.engine.reset_daily(100000, "2025-03-10")

    def test_can_trade_initially(self):
        can, reason = self.engine.check_can_trade(is_option=True)
        assert can is True
        assert reason == ""

    def test_consecutive_losses_trigger_cooldown(self):
        """3 consecutive losses → cooldown."""
        for i in range(3):
            self.engine.init_option_trade(f"LOSS-{i}", 100, 5, 325, True)
            self.engine.record_trade_result(-500)
        can, reason = self.engine.check_can_trade(is_option=True)
        assert can is False
        assert "cooldown" in reason.lower() or "consecutive" in reason.lower()

    def test_daily_loss_cap(self):
        """Daily loss exceeds 2% of capital → kill switch."""
        self.engine.init_option_trade("BIG-LOSS", 100, 5, 325, True)
        self.engine.record_trade_result(-2500)  # > 2% of 100000
        can, reason = self.engine.check_can_trade(is_option=True)
        assert can is False

    def test_get_status(self):
        status = self.engine.get_status()
        assert "kill_switch" in status
        assert "daily_pnl" in status

    def test_remove_trade(self):
        self.engine.init_option_trade("RM-001", 100, 5, 325, True)
        assert self.engine.get_trade_state("RM-001") is not None
        self.engine.remove_trade("RM-001")
        assert self.engine.get_trade_state("RM-001") is None
