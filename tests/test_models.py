"""Tests for shared/models.py — Pydantic model validations."""
import pytest
from datetime import datetime
from shared.models import (
    Direction,
    MarketRegime,
    Signal,
    UserPreferences,
    UserProfile,
    RiskTolerance,
    InvestmentHorizon,
    TradeStatus,
    TradeType,
    Trade,
    Portfolio,
)


class TestEnums:
    def test_direction_values(self):
        assert Direction.STRONG_UP == "Strong Up"
        assert Direction.STRONG_DOWN == "Strong Down"

    def test_market_regime_values(self):
        assert MarketRegime.TRENDING == "trending"
        assert MarketRegime.CHOP == "chop"
        assert MarketRegime.VOLATILE == "volatile"

    def test_risk_tolerance_values(self):
        assert set(RiskTolerance) == {RiskTolerance.LOW, RiskTolerance.MEDIUM, RiskTolerance.HIGH}

    def test_trade_status_values(self):
        assert TradeStatus.OPEN == "OPEN"
        assert TradeStatus.CLOSED == "CLOSED"


class TestSignalModel:
    def test_minimal_signal(self):
        s = Signal(source="Reddit", content="RELIANCE bullish", sentiment=0.8, relevance=0.9)
        assert s.source == "Reddit"
        assert s.confidence == 1.0  # default
        assert s.freshness == 1.0  # default

    def test_signal_with_metadata(self):
        s = Signal(
            source="Moneycontrol",
            content="TCS target raised",
            sentiment=0.6,
            relevance=0.7,
            metadata={"url": "https://moneycontrol.com/article/123"},
        )
        assert s.metadata["url"].startswith("https://")

    def test_signal_timestamp_auto(self):
        s = Signal(source="test", content="test", sentiment=0.0, relevance=0.0)
        assert isinstance(s.timestamp, datetime)


class TestUserModels:
    def test_default_preferences(self):
        prefs = UserPreferences()
        assert prefs.risk_tolerance == RiskTolerance.MEDIUM
        assert prefs.investment_horizon == InvestmentHorizon.SWING
        assert prefs.preferred_sectors == []
        assert prefs.max_allocation_per_trade == 0.1

    def test_user_profile_defaults(self):
        u = UserProfile(full_name="Test User", email="test@example.com")
        assert u.is_active is True
        assert u.is_admin is False
        assert u.onboarded is False
        assert u.picture is None

    def test_user_profile_admin(self):
        u = UserProfile(full_name="Admin", email="admin@example.com", is_admin=True)
        assert u.is_admin is True


class TestTradeModel:
    def test_trade_creation(self):
        t = Trade(
            id="T001",
            symbol="RELIANCE",
            type=TradeType.BUY,
            status=TradeStatus.OPEN,
            entry_price=2500.0,
            quantity=10,
            entry_time=datetime.now(),
            target=2600.0,
            stop_loss=2450.0,
            conviction=0.75,
        )
        assert t.pnl == 0.0  # default
        assert t.exit_price is None
        assert t.exit_time is None

    def test_trade_closed(self):
        t = Trade(
            id="T002",
            symbol="TCS",
            type=TradeType.SELL,
            status=TradeStatus.CLOSED,
            entry_price=3500.0,
            quantity=5,
            entry_time=datetime.now(),
            exit_price=3400.0,
            exit_time=datetime.now(),
            pnl=500.0,
            pnl_percent=2.86,
            target=3300.0,
            stop_loss=3550.0,
            conviction=0.6,
        )
        assert t.pnl == 500.0
        assert t.status == TradeStatus.CLOSED


class TestPortfolioModel:
    def test_default_portfolio(self):
        p = Portfolio()
        assert p.cash_balance == 100000.0
        assert p.realized_pnl == 0.0
        assert p.active_trades == []
        assert p.trade_history == []

    def test_portfolio_with_balance(self):
        p = Portfolio(cash_balance=50000.0, realized_pnl=1200.0)
        assert p.cash_balance == 50000.0
        assert p.realized_pnl == 1200.0
