"""Tests for services/recommendation_engine/level_calculator.py — price level math."""
import pytest
from services.recommendation_engine.level_calculator import LevelCalculator


@pytest.fixture
def calc():
    return LevelCalculator(min_rr=2.0)


class TestLevelCalculatorUp:
    """Tests for UP (LONG) direction."""

    def test_basic_up(self, calc):
        levels = calc.calculate_levels(current_price=1000.0, atr=20.0, direction="UP")
        assert levels is not None
        assert levels["entry"] == 1000.0
        assert levels["sl"] < 1000.0
        assert levels["target1"] > 1000.0
        assert levels["target2"] > levels["target1"]

    def test_rr_ratio_at_least_2(self, calc):
        levels = calc.calculate_levels(current_price=500.0, atr=10.0, direction="UP")
        assert levels["rr"] >= 2.0

    def test_stop_loss_uses_atr(self, calc):
        levels = calc.calculate_levels(current_price=100.0, atr=5.0, direction="UP")
        assert levels["sl"] == pytest.approx(95.0, abs=0.01)

    def test_vix_widens_levels(self, calc):
        normal = calc.calculate_levels(current_price=1000.0, atr=20.0, direction="UP", vix=10.0)
        high_vix = calc.calculate_levels(current_price=1000.0, atr=20.0, direction="UP", vix=22.0)
        # Higher VIX → wider SL (further from entry) and wider targets
        assert high_vix["sl"] < normal["sl"]
        assert high_vix["target1"] > normal["target1"]

    def test_extreme_vix(self, calc):
        levels = calc.calculate_levels(current_price=1000.0, atr=20.0, direction="UP", vix=30.0)
        assert levels["vix_multiplier"] == 1.5

    def test_vix_multiplier_default(self, calc):
        levels = calc.calculate_levels(current_price=1000.0, atr=20.0, direction="UP", vix=0.0)
        assert levels["vix_multiplier"] == 1.0


class TestLevelCalculatorDown:
    """Tests for DOWN (SHORT) direction."""

    def test_basic_down(self, calc):
        levels = calc.calculate_levels(current_price=1000.0, atr=20.0, direction="DOWN")
        assert levels is not None
        assert levels["entry"] == 1000.0
        assert levels["sl"] > 1000.0
        assert levels["target1"] < 1000.0
        assert levels["target2"] < levels["target1"]

    def test_rr_ratio_at_least_2_down(self, calc):
        levels = calc.calculate_levels(current_price=500.0, atr=10.0, direction="DOWN")
        assert levels["rr"] >= 2.0

    def test_stop_loss_above_entry(self, calc):
        levels = calc.calculate_levels(current_price=100.0, atr=5.0, direction="DOWN")
        assert levels["sl"] == pytest.approx(105.0, abs=0.01)


class TestLevelCalculatorEdgeCases:
    def test_zero_atr_returns_none(self, calc):
        result = calc.calculate_levels(current_price=100.0, atr=0.0, direction="UP")
        assert result is None

    def test_negative_atr_returns_none(self, calc):
        result = calc.calculate_levels(current_price=100.0, atr=-5.0, direction="UP")
        assert result is None

    def test_invalid_direction_returns_none(self, calc):
        result = calc.calculate_levels(current_price=100.0, atr=10.0, direction="SIDEWAYS")
        assert result is None

    def test_case_insensitive_direction(self, calc):
        up = calc.calculate_levels(current_price=100.0, atr=5.0, direction="up")
        assert up is not None
        down = calc.calculate_levels(current_price=100.0, atr=5.0, direction="Down")
        assert down is not None

    def test_symmetry(self, calc):
        """UP and DOWN with same params should produce symmetric risk:reward."""
        up = calc.calculate_levels(current_price=1000.0, atr=20.0, direction="UP")
        down = calc.calculate_levels(current_price=1000.0, atr=20.0, direction="DOWN")
        assert up["rr"] == pytest.approx(down["rr"], abs=0.01)
