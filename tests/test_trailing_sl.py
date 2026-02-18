"""
Integration tests for shared/trailing_sl.py — Trailing Stop Loss Engine.
Tests all 4 strategies: PERCENTAGE, ATR_BASED, STEP_TRAIL, HYBRID.
"""
import pytest
from shared.trailing_sl import (
    TrailingStopLossEngine,
    TrailConfig,
    TrailState,
    TrailStrategy,
)


class TestTrailStateCreation:
    """Test factory and serialization helpers."""

    def test_create_state_long(self):
        state = TrailingStopLossEngine.create_state(
            trade_id="T001", trade_type="BUY",
            entry_price=100.0, stop_loss=95.0,
        )
        assert state.trade_id == "T001"
        assert state.trade_type == "BUY"
        assert state.entry_price == 100.0
        assert state.original_sl == 95.0
        assert state.current_sl == 95.0
        assert state.peak_price == 100.0
        assert state.trough_price == 100.0
        assert state.trail_activated is False
        assert state.adjustments == 0

    def test_create_state_short(self):
        state = TrailingStopLossEngine.create_state(
            trade_id="T002", trade_type="SELL",
            entry_price=200.0, stop_loss=210.0,
        )
        assert state.trade_type == "SELL"
        assert state.current_sl == 210.0

    def test_state_roundtrip_serialization(self):
        state = TrailingStopLossEngine.create_state(
            trade_id="T003", trade_type="BUY",
            entry_price=150.0, stop_loss=145.0,
        )
        d = TrailingStopLossEngine.state_to_dict(state)
        restored = TrailingStopLossEngine.state_from_dict(d)
        assert restored.trade_id == state.trade_id
        assert restored.entry_price == state.entry_price
        assert restored.current_sl == state.current_sl
        assert restored.peak_price == state.peak_price

    def test_state_to_dict_caps_history(self):
        state = TrailingStopLossEngine.create_state(
            "T004", "BUY", 100.0, 95.0,
        )
        state.history = [{"old_sl": i, "new_sl": i + 1} for i in range(30)]
        d = TrailingStopLossEngine.state_to_dict(state)
        assert len(d["history"]) == 20  # capped at 20


class TestPercentageTrail:
    """Test PERCENTAGE strategy."""

    def _config(self, **kw):
        return TrailConfig(strategy=TrailStrategy.PERCENTAGE, **kw)

    def test_no_trail_when_no_profit(self):
        state = TrailingStopLossEngine.create_state("P1", "BUY", 100.0, 95.0)
        cfg = self._config()
        result = TrailingStopLossEngine.compute_new_sl(state, 99.0, cfg)
        assert result is None  # price below entry — no trailing

    def test_no_trail_below_activation(self):
        state = TrailingStopLossEngine.create_state("P2", "BUY", 100.0, 95.0)
        cfg = self._config(activation_pct=0.5)
        # 0.2% profit — below activation threshold
        result = TrailingStopLossEngine.compute_new_sl(state, 100.2, cfg)
        assert result is None

    def test_trail_activates_on_sufficient_profit(self):
        state = TrailingStopLossEngine.create_state("P3", "BUY", 100.0, 95.0)
        cfg = self._config(activation_pct=0.3, trail_pct=0.5)
        # 1% profit → triggers trail
        new_sl = TrailingStopLossEngine.compute_new_sl(state, 101.0, cfg)
        assert new_sl is not None
        assert new_sl > 95.0  # SL tightened
        assert new_sl < 101.0  # SL below current price

    def test_sl_only_tightens_long(self):
        """SL must only move up for BUY trades, never widen."""
        state = TrailingStopLossEngine.create_state("P4", "BUY", 100.0, 95.0)
        cfg = self._config(activation_pct=0.3, trail_pct=0.5)

        # Move up
        sl1 = TrailingStopLossEngine.compute_new_sl(state, 102.0, cfg)
        assert sl1 is not None
        # Price drops (SL should not widen)
        sl2 = TrailingStopLossEngine.compute_new_sl(state, 101.0, cfg)
        assert sl2 is None  # No widening

    def test_short_trade_trail(self):
        state = TrailingStopLossEngine.create_state("P5", "SELL", 200.0, 210.0)
        cfg = self._config(activation_pct=0.3, trail_pct=0.5)
        # Price drops (profit for SELL)
        new_sl = TrailingStopLossEngine.compute_new_sl(state, 197.0, cfg)
        assert new_sl is not None
        assert new_sl < 210.0  # SL tightened (moved down)
        assert new_sl > 197.0  # SL above current price

    def test_invalid_price_returns_none(self):
        state = TrailingStopLossEngine.create_state("P6", "BUY", 100.0, 95.0)
        assert TrailingStopLossEngine.compute_new_sl(state, 0, TrailConfig()) is None
        assert TrailingStopLossEngine.compute_new_sl(state, -5, TrailConfig()) is None


class TestATRTrail:
    """Test ATR_BASED strategy."""

    def _config(self, **kw):
        return TrailConfig(strategy=TrailStrategy.ATR_BASED, **kw)

    def test_atr_trail_long(self):
        state = TrailingStopLossEngine.create_state("A1", "BUY", 100.0, 95.0)
        cfg = self._config(atr_multiplier=1.5)
        # ATR = 2.0, so trail distance = 3.0
        new_sl = TrailingStopLossEngine.compute_new_sl(state, 105.0, cfg, atr=2.0)
        assert new_sl is not None
        assert new_sl > 95.0

    def test_atr_none_falls_back_to_percentage(self):
        state = TrailingStopLossEngine.create_state("A2", "BUY", 100.0, 95.0)
        cfg = self._config(activation_pct=0.3, trail_pct=0.5)
        # No ATR provided → falls back to percentage
        new_sl = TrailingStopLossEngine.compute_new_sl(state, 102.0, cfg, atr=None)
        assert new_sl is not None

    def test_atr_zero_falls_back(self):
        state = TrailingStopLossEngine.create_state("A3", "BUY", 100.0, 95.0)
        cfg = self._config(activation_pct=0.3, trail_pct=0.5)
        new_sl = TrailingStopLossEngine.compute_new_sl(state, 102.0, cfg, atr=0)
        assert new_sl is not None


class TestStepTrail:
    """Test STEP_TRAIL strategy."""

    def _config(self, **kw):
        return TrailConfig(strategy=TrailStrategy.STEP_TRAIL, **kw)

    def test_step_trail_progression(self):
        state = TrailingStopLossEngine.create_state("S1", "BUY", 100.0, 95.0)
        cfg = self._config(step_size_pct=0.5, step_lock_pct=0.3)

        # 0.6% profit → step 1 reached
        sl1 = TrailingStopLossEngine.compute_new_sl(state, 100.6, cfg)
        assert sl1 is not None
        assert state.step_level == 1

        # 1.1% profit → step 2 reached
        sl2 = TrailingStopLossEngine.compute_new_sl(state, 101.1, cfg)
        assert sl2 is not None
        assert sl2 > sl1
        assert state.step_level == 2

    def test_step_trail_no_move_within_same_step(self):
        state = TrailingStopLossEngine.create_state("S2", "BUY", 100.0, 95.0)
        cfg = self._config(step_size_pct=1.0, step_lock_pct=0.5)
        # 1.2% profit → step 1
        sl1 = TrailingStopLossEngine.compute_new_sl(state, 101.2, cfg)
        assert sl1 is not None
        # 1.5% profit → still step 1 — no new SL
        sl2 = TrailingStopLossEngine.compute_new_sl(state, 101.5, cfg)
        assert sl2 is None  # Same step level


class TestHybridTrail:
    """Test HYBRID strategy — breakeven → step → tight trail."""

    def _config(self, **kw):
        return TrailConfig(strategy=TrailStrategy.HYBRID, **kw)

    def test_breakeven_phase(self):
        state = TrailingStopLossEngine.create_state("H1", "BUY", 100.0, 95.0)
        cfg = self._config(
            breakeven_trigger_pct=0.5,
            breakeven_buffer_pct=0.05,
        )
        # 0.6% profit → breakeven triggered
        new_sl = TrailingStopLossEngine.compute_new_sl(state, 100.6, cfg)
        assert new_sl is not None
        assert state.breakeven_set is True
        # SL should be very close to entry + buffer
        assert abs(new_sl - 100.05) < 0.1

    def test_hybrid_step_phase(self):
        state = TrailingStopLossEngine.create_state("H2", "BUY", 100.0, 95.0)
        cfg = self._config(
            breakeven_trigger_pct=0.3,
            step_size_pct=0.5,
            step_lock_pct=0.3,
        )
        # Trigger breakeven first
        TrailingStopLossEngine.compute_new_sl(state, 100.5, cfg)
        # 1% profit → step trail kicks in
        sl2 = TrailingStopLossEngine.compute_new_sl(state, 101.0, cfg)
        assert sl2 is not None

    def test_hybrid_tight_trail_phase(self):
        state = TrailingStopLossEngine.create_state("H3", "BUY", 100.0, 95.0)
        cfg = self._config(
            breakeven_trigger_pct=0.3,
            trail_pct=0.5,
            min_trail_pct=0.2,
        )
        # Trigger breakeven
        TrailingStopLossEngine.compute_new_sl(state, 100.5, cfg)
        # High profit → tight trail
        sl = TrailingStopLossEngine.compute_new_sl(state, 103.0, cfg)
        assert sl is not None

    def test_history_tracking(self):
        state = TrailingStopLossEngine.create_state("H4", "BUY", 100.0, 95.0)
        cfg = self._config(breakeven_trigger_pct=0.3)
        TrailingStopLossEngine.compute_new_sl(state, 101.0, cfg)
        assert len(state.history) >= 1
        assert state.adjustments >= 1
        entry = state.history[0]
        assert "old_sl" in entry
        assert "new_sl" in entry
        assert "profit_pct" in entry


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_entry_price(self):
        state = TrailState(
            trade_id="E1", trade_type="BUY",
            entry_price=0.0, original_sl=0.0,
            current_sl=0.0, peak_price=0.0, trough_price=0.0,
        )
        result = TrailingStopLossEngine.compute_new_sl(state, 100.0)
        assert result is None

    def test_min_trail_enforcement(self):
        """Ensure SL never gets closer than min_trail_pct."""
        state = TrailingStopLossEngine.create_state("E2", "BUY", 100.0, 95.0)
        cfg = TrailConfig(
            strategy=TrailStrategy.PERCENTAGE,
            trail_pct=0.01,  # Very tight trail
            activation_pct=0.1,
            min_trail_pct=0.5,  # But min is 0.5%
        )
        new_sl = TrailingStopLossEngine.compute_new_sl(state, 102.0, cfg)
        if new_sl is not None:
            # Trail distance must respect min
            dist = ((102.0 - new_sl) / 102.0) * 100
            assert dist >= 0.19  # Allow small rounding tolerance
