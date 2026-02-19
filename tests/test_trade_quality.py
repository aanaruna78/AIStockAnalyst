"""
Tests for trade quality fixes:
  - Options Greeks filtering (delta, gamma, theta gates)
  - Options cooldown after consecutive losses
  - Options per-strike daily limit
  - Equity per-symbol daily cooldown after SL hit
  - Equity max entries per symbol per day
  - Trailing SL config widened for equity
"""
import time
import sys
import os
from datetime import datetime
try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except ImportError:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")

def _today():
    return datetime.now(IST).strftime("%Y-%m-%d")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ─────────────────────────────────────────────────────────
# Options Greeks Filtering
# ─────────────────────────────────────────────────────────

class TestOptionsGreeksFiltering:
    """Test that options service rejects trades with bad greeks."""

    def _make_engine(self):
        """Create a fresh PaperTradingEngine for testing."""
        from services.options_scalping_service.main_v2 import (
            PaperTradingEngine, risk_engine,
        )
        today = _today()
        engine = PaperTradingEngine()
        engine.capital = 500000  # Large capital so capital gate doesn't fire
        engine.day_trade_count = 0
        engine.current_date = today  # Prevent _reset_daily() from wiping test state
        engine.active_trades = []
        engine._consecutive_losses = 0
        engine._last_loss_time = 0
        engine._daily_strike_entries = {}
        # Fix clock to market hours so time gate doesn't fire
        engine._test_now = datetime(2026, 2, 19, 11, 0, 0, tzinfo=IST)
        # Ensure risk engine is ready
        risk_engine.reset_daily(500000, today)
        return engine

    def test_reject_low_delta(self):
        """Deep OTM options (delta < 0.25) should be rejected."""
        engine = self._make_engine()
        result = engine.place_trade(
            direction="CE", strike=26000, entry_premium=10.0, lots=5,
            greeks={"delta": 0.15, "gamma": 0.001, "theta": -0.5, "vega": 3.0, "iv": 15.0},
        )
        assert result["status"] == "rejected"
        assert "OTM" in result["reason"] or "Delta" in result["reason"]

    def test_reject_deep_itm(self):
        """Deep ITM options (delta > 0.75) should be rejected."""
        engine = self._make_engine()
        result = engine.place_trade(
            direction="CE", strike=24000, entry_premium=200.0, lots=5,
            greeks={"delta": 0.85, "gamma": 0.0003, "theta": -3.0, "vega": 2.0, "iv": 12.0},
        )
        assert result["status"] == "rejected"
        assert "ITM" in result["reason"] or "Delta" in result["reason"]

    def test_reject_low_gamma(self):
        """Options with almost no gamma should be rejected."""
        engine = self._make_engine()
        result = engine.place_trade(
            direction="CE", strike=25800, entry_premium=50.0, lots=5,
            greeks={"delta": 0.50, "gamma": 0.0001, "theta": -2.0, "vega": 5.0, "iv": 15.0},
        )
        assert result["status"] == "rejected"
        assert "Gamma" in result["reason"] or "gamma" in result["reason"]

    def test_reject_high_theta(self):
        """Options where daily theta > 5% of premium should be rejected."""
        engine = self._make_engine()
        result = engine.place_trade(
            direction="CE", strike=25800, entry_premium=10.0, lots=5,
            greeks={"delta": 0.40, "gamma": 0.002, "theta": -1.0, "vega": 3.0, "iv": 15.0},
            # theta = 1.0/10.0 = 10% > 5% cap
        )
        assert result["status"] == "rejected"
        assert "Theta" in result["reason"] or "theta" in result["reason"]

    def test_accept_good_greeks(self):
        """Options with acceptable greeks should be allowed."""
        engine = self._make_engine()
        result = engine.place_trade(
            direction="CE", strike=25800, entry_premium=120.0, lots=5,
            greeks={"delta": 0.50, "gamma": 0.002, "theta": -2.0, "vega": 5.0, "iv": 15.0},
        )
        # Should be either placed or rejected for non-greeks reason (e.g. risk engine)
        if result["status"] == "rejected":
            assert "Delta" not in result["reason"]
            assert "Gamma" not in result["reason"]
            assert "Theta" not in result["reason"]

    def test_reject_too_cheap(self):
        """Options priced below ₹5 should be rejected."""
        engine = self._make_engine()
        result = engine.place_trade(
            direction="PE", strike=26500, entry_premium=3.0, lots=5,
            greeks={"delta": -0.30, "gamma": 0.001, "theta": -0.1, "vega": 1.0, "iv": 20.0},
        )
        assert result["status"] == "rejected"
        assert "cheap" in result["reason"].lower() or "Premium" in result["reason"]


# ─────────────────────────────────────────────────────────
# Options Cooldown After Losses
# ─────────────────────────────────────────────────────────

class TestOptionsCooldown:
    """Test cooldown timer after consecutive option losses."""

    def _make_engine(self):
        from services.options_scalping_service.main_v2 import (
            PaperTradingEngine, risk_engine,
        )
        today = _today()
        engine = PaperTradingEngine()
        engine.capital = 500000  # Large capital so capital gate doesn't fire
        engine.day_trade_count = 0
        engine.current_date = today  # Prevent _reset_daily() from wiping test state
        engine.active_trades = []
        engine._consecutive_losses = 0
        engine._last_loss_time = 0
        engine._daily_strike_entries = {}
        # Fix clock to market hours so time gate doesn't fire
        engine._test_now = datetime(2026, 2, 19, 11, 0, 0, tzinfo=IST)
        risk_engine.reset_daily(500000, today)
        return engine

    def test_cooldown_after_loss(self):
        """After a loss, cooldown should block next trade for 300s."""
        engine = self._make_engine()
        # Simulate having just had a loss
        engine._consecutive_losses = 1
        engine._last_loss_time = time.time()  # just now

        result = engine.place_trade(
            direction="CE", strike=25800, entry_premium=120.0, lots=5,
            greeks={"delta": 0.50, "gamma": 0.002, "theta": -2.0, "vega": 5.0, "iv": 15.0},
        )
        assert result["status"] == "rejected"
        assert "Cooldown" in result["reason"] or "cooldown" in result["reason"]

    def test_longer_cooldown_after_2_consecutive_losses(self):
        """After 2+ consecutive losses, cooldown should be 600s."""
        engine = self._make_engine()
        engine._consecutive_losses = 2
        engine._last_loss_time = time.time()

        result = engine.place_trade(
            direction="CE", strike=25800, entry_premium=120.0, lots=5,
            greeks={"delta": 0.50, "gamma": 0.002, "theta": -2.0, "vega": 5.0, "iv": 15.0},
        )
        assert result["status"] == "rejected"
        assert "Cooldown" in result["reason"] or "cooldown" in result["reason"]

    def test_no_cooldown_if_expired(self):
        """Cooldown should expire after the timeout period."""
        engine = self._make_engine()
        engine._consecutive_losses = 1
        engine._last_loss_time = time.time() - 400  # 400s ago > 300s cooldown

        # Should NOT be rejected for cooldown (might be rejected for other reasons)
        result = engine.place_trade(
            direction="CE", strike=25800, entry_premium=120.0, lots=5,
            greeks={"delta": 0.50, "gamma": 0.002, "theta": -2.0, "vega": 5.0, "iv": 15.0},
        )
        if result["status"] == "rejected":
            assert "Cooldown" not in result["reason"]


# ─────────────────────────────────────────────────────────
# Options Per-Strike Daily Limit
# ─────────────────────────────────────────────────────────

class TestOptionsStrikeLimit:
    """Test max entries per strike/direction per day."""

    def _make_engine(self):
        from services.options_scalping_service.main_v2 import (
            PaperTradingEngine, risk_engine,
        )
        engine = PaperTradingEngine()
        today = _today()
        engine.capital = 500000  # Large capital so capital gate doesn't fire
        engine.day_trade_count = 0
        engine.current_date = today  # Prevent _reset_daily() from wiping test state
        engine.active_trades = []
        engine._consecutive_losses = 0
        engine._last_loss_time = 0
        engine._daily_strike_entries = {}
        # Fix clock to market hours so time gate doesn't fire
        engine._test_now = datetime(2026, 2, 19, 11, 0, 0, tzinfo=IST)
        risk_engine.reset_daily(500000, today)
        return engine

    def test_block_after_max_entries(self):
        """Should block entry after MAX_SAME_STRIKE_PER_DAY entries on same strike."""
        engine = self._make_engine()
        engine._daily_strike_entries = {"25800-CE": 2}  # Already 2 entries

        result = engine.place_trade(
            direction="CE", strike=25800, entry_premium=120.0, lots=5,
            greeks={"delta": 0.50, "gamma": 0.002, "theta": -2.0, "vega": 5.0, "iv": 15.0},
        )
        assert result["status"] == "rejected"
        assert "entries per day" in result["reason"]

    def test_allow_different_strike(self):
        """Different strike should still be allowed."""
        engine = self._make_engine()
        engine._daily_strike_entries = {"25800-CE": 2}  # 25800 maxed out

        # 25850 should be allowed (different strike)
        result = engine.place_trade(
            direction="CE", strike=25850, entry_premium=100.0, lots=5,
            greeks={"delta": 0.45, "gamma": 0.002, "theta": -1.8, "vega": 5.0, "iv": 15.0},
        )
        # Should not be rejected for strike limit
        if result["status"] == "rejected":
            assert "entries per day" not in result["reason"]


# ─────────────────────────────────────────────────────────
# Equity Per-Symbol Cooldown
# ─────────────────────────────────────────────────────────

class TestEquitySymbolCooldown:
    """Test per-symbol cooldown after SL hit for equity trades."""

    def test_cooldown_tracking_fields_exist(self):
        """TradeManager should have per-symbol cooldown tracking."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "trading_service"))
        from services.trading_service.trade_manager import TradeManager
        tm = TradeManager()
        assert hasattr(tm, "_symbol_last_exit")
        assert hasattr(tm, "_symbol_entries_today")
        assert isinstance(tm._symbol_last_exit, dict)
        assert isinstance(tm._symbol_entries_today, dict)

    def test_constants_defined(self):
        """Cooldown constants should be defined."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "trading_service"))
        from services.trading_service.trade_manager import (
            SYMBOL_COOLDOWN_SEC,
            MAX_ENTRIES_PER_SYMBOL_DAY,
        )
        assert SYMBOL_COOLDOWN_SEC == 1800  # 30 min
        assert MAX_ENTRIES_PER_SYMBOL_DAY == 2


# ─────────────────────────────────────────────────────────
# Trailing SL Configuration
# ─────────────────────────────────────────────────────────

class TestTrailingSLConfig:
    """Test that trailing SL config is widened for equity."""

    def test_equity_trail_config_widened(self):
        """Equity trailing SL should be wider than original 0.5%."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "trading_service"))
        from services.trading_service.trade_manager import TradeManager
        tm = TradeManager()
        config = tm._trail_config
        assert config.trail_pct >= 1.0, f"trail_pct {config.trail_pct} should be >= 1.0%"
        assert config.activation_pct >= 0.7, f"activation_pct {config.activation_pct} should be >= 0.7%"
        assert config.min_trail_pct >= 0.4, f"min_trail_pct {config.min_trail_pct} should be >= 0.4%"
        assert config.breakeven_trigger_pct >= 0.8, "breakeven_trigger_pct should be >= 0.8%"

    def test_equity_trail_pct_not_too_narrow(self):
        """For a ₹10k stock, trail distance should be >= ₹80."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "trading_service"))
        from services.trading_service.trade_manager import TradeManager
        tm = TradeManager()
        stock_price = 10000
        trail_dist = stock_price * tm._trail_config.trail_pct / 100
        assert trail_dist >= 80, f"Trail distance ₹{trail_dist} too narrow for ₹{stock_price} stock"


# ─────────────────────────────────────────────────────────
# Iceberg at 5 Lots
# ─────────────────────────────────────────────────────────

class TestIceberg5Lots:
    """Test iceberg triggers at exactly 5 lots and splits correctly."""

    def test_5_lots_triggers_iceberg(self):
        from shared.iceberg_order import IcebergEngine
        assert IcebergEngine.should_iceberg_option(5) is True

    def test_4_lots_no_iceberg(self):
        from shared.iceberg_order import IcebergEngine
        assert IcebergEngine.should_iceberg_option(4) is False

    def test_5_lots_splits_into_3_slices(self):
        from shared.iceberg_order import IcebergEngine
        order = IcebergEngine.create_option_iceberg(
            symbol="NIFTY-25800-CE",
            trade_type="BUY",
            lots=5,
            premium=136.0,
            lot_size=65,
        )
        # 5 lots / 2 per slice = 3 slices (2+2+1)
        assert len(order.slices) == 3
        qtys = [s.quantity for s in order.slices]
        assert qtys == [130, 130, 65]
        assert sum(qtys) == 325  # 5 * 65

    def test_7_lots_splits_correctly(self):
        from shared.iceberg_order import IcebergEngine
        order = IcebergEngine.create_option_iceberg(
            symbol="NIFTY-25800-PE",
            trade_type="BUY",
            lots=7,
            premium=100.0,
            lot_size=65,
        )
        # 7 lots / 2 per slice = 4 slices (2+2+2+1)
        assert len(order.slices) == 4
        qtys = [s.quantity for s in order.slices]
        assert qtys == [130, 130, 130, 65]
        assert sum(qtys) == 455  # 7 * 65
