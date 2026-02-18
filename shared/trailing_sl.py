"""
Trailing Stop Loss Engine
=========================
Adaptive trailing stop-loss strategy that dynamically adjusts SL
based on price movement, volatility, and trade type.

Strategies:
  1. PERCENTAGE  — Fixed % trail from peak/trough
  2. ATR_BASED   — Trail by N x ATR (Average True Range)
  3. STEP_TRAIL  — Move SL in steps as price crosses thresholds
  4. HYBRID      — Combines percentage + step for intraday

Used by both Options Scalping Service and Intraday Stock Trading.
"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("trailing_sl")


class TrailStrategy(str, Enum):
    PERCENTAGE = "percentage"
    ATR_BASED = "atr_based"
    STEP_TRAIL = "step_trail"
    HYBRID = "hybrid"


@dataclass
class TrailConfig:
    """Configuration for trailing stop loss."""
    strategy: TrailStrategy = TrailStrategy.HYBRID
    # Percentage trail
    trail_pct: float = 0.5          # 0.5% default trail distance
    activation_pct: float = 0.3    # Activate trailing after 0.3% profit
    # Step trail
    step_size_pct: float = 0.5     # Move SL every 0.5% price move
    step_lock_pct: float = 0.3     # Lock in 0.3% of each step
    # ATR-based
    atr_multiplier: float = 1.5    # Trail at 1.5x ATR
    # Hybrid
    min_trail_pct: float = 0.2     # Minimum trail distance (never closer)
    max_trail_pct: float = 2.0     # Maximum trail distance
    # Breakeven
    breakeven_trigger_pct: float = 0.5  # Move SL to breakeven after 0.5% profit
    breakeven_buffer_pct: float = 0.05  # Small buffer above breakeven
    # Cost-aware
    include_costs: bool = True      # Factor in brokerage/taxes


@dataclass
class TrailState:
    """Mutable state for an active trailing stop loss."""
    trade_id: str
    trade_type: str                 # "BUY" or "SELL"
    entry_price: float
    original_sl: float
    current_sl: float
    peak_price: float               # Highest price seen (BUY) / Lowest (SELL)
    trough_price: float             # Lowest price seen (SELL)
    trail_activated: bool = False
    breakeven_set: bool = False
    step_level: int = 0             # Current step level reached
    adjustments: int = 0            # Number of SL adjustments made
    last_adjusted_price: float = 0.0
    history: list = field(default_factory=list)  # Audit trail


class TrailingStopLossEngine:
    """
    Computes new stop-loss levels based on price movement and strategy.
    Stateless per call — caller maintains TrailState per trade.
    """

    @staticmethod
    def compute_new_sl(
        state: TrailState,
        current_price: float,
        config: TrailConfig = TrailConfig(),
        atr: Optional[float] = None,
    ) -> Optional[float]:
        """
        Compute a new SL given current price and trail state.

        Returns:
            New SL value if it should be updated, None if no change needed.
        """
        if current_price <= 0 or state.entry_price <= 0:
            return None

        is_long = state.trade_type.upper() in ("BUY", "LONG")

        # Update peak/trough tracking
        if is_long:
            if current_price > state.peak_price:
                state.peak_price = current_price
        else:
            if state.trough_price == 0 or current_price < state.trough_price:
                state.trough_price = current_price

        # Calculate profit %
        if is_long:
            profit_pct = ((current_price - state.entry_price) / state.entry_price) * 100
        else:
            profit_pct = ((state.entry_price - current_price) / state.entry_price) * 100

        # Not in profit yet — no trailing
        if profit_pct <= 0:
            return None

        new_sl = None

        if config.strategy == TrailStrategy.PERCENTAGE:
            new_sl = TrailingStopLossEngine._percentage_trail(
                state, current_price, config, is_long, profit_pct
            )
        elif config.strategy == TrailStrategy.ATR_BASED:
            new_sl = TrailingStopLossEngine._atr_trail(
                state, current_price, config, is_long, atr
            )
        elif config.strategy == TrailStrategy.STEP_TRAIL:
            new_sl = TrailingStopLossEngine._step_trail(
                state, current_price, config, is_long, profit_pct
            )
        elif config.strategy == TrailStrategy.HYBRID:
            new_sl = TrailingStopLossEngine._hybrid_trail(
                state, current_price, config, is_long, profit_pct, atr
            )

        if new_sl is None:
            return None

        new_sl = round(new_sl, 2)

        # Validate: SL must only tighten, never widen
        if is_long:
            if new_sl <= state.current_sl:
                return None  # Would widen SL
        else:
            if new_sl >= state.current_sl:
                return None  # Would widen SL

        # Validate: SL must not cross current price
        if is_long and new_sl >= current_price:
            return None
        if not is_long and new_sl <= current_price:
            return None

        # Validate: minimum trail distance
        if is_long:
            trail_dist_pct = ((current_price - new_sl) / current_price) * 100
        else:
            trail_dist_pct = ((new_sl - current_price) / current_price) * 100

        if trail_dist_pct < config.min_trail_pct:
            # Too close — enforce minimum distance
            if is_long:
                new_sl = round(current_price * (1 - config.min_trail_pct / 100), 2)
            else:
                new_sl = round(current_price * (1 + config.min_trail_pct / 100), 2)

        # Final re-check after min distance enforcement
        if is_long and new_sl <= state.current_sl:
            return None
        if not is_long and new_sl >= state.current_sl:
            return None

        # Record adjustment
        state.history.append({
            "old_sl": state.current_sl,
            "new_sl": new_sl,
            "price": current_price,
            "profit_pct": round(profit_pct, 2),
            "step_level": state.step_level,
        })
        state.current_sl = new_sl
        state.last_adjusted_price = current_price
        state.adjustments += 1
        state.trail_activated = True

        return new_sl

    @staticmethod
    def _percentage_trail(
        state: TrailState, price: float, config: TrailConfig,
        is_long: bool, profit_pct: float,
    ) -> Optional[float]:
        """Simple percentage trail from peak/trough."""
        if profit_pct < config.activation_pct:
            return None

        if is_long:
            # Trail below peak
            new_sl = state.peak_price * (1 - config.trail_pct / 100)
        else:
            # Trail above trough
            new_sl = state.trough_price * (1 + config.trail_pct / 100)

        return new_sl

    @staticmethod
    def _atr_trail(
        state: TrailState, price: float, config: TrailConfig,
        is_long: bool, atr: Optional[float],
    ) -> Optional[float]:
        """ATR-based trailing stop."""
        if atr is None or atr <= 0:
            # Fallback to percentage trail
            return TrailingStopLossEngine._percentage_trail(
                state, price, config, is_long,
                ((price - state.entry_price) / state.entry_price) * 100 if is_long else
                ((state.entry_price - price) / state.entry_price) * 100
            )

        trail_distance = atr * config.atr_multiplier

        if is_long:
            new_sl = state.peak_price - trail_distance
        else:
            new_sl = state.trough_price + trail_distance

        return new_sl

    @staticmethod
    def _step_trail(
        state: TrailState, price: float, config: TrailConfig,
        is_long: bool, profit_pct: float,
    ) -> Optional[float]:
        """
        Step-based trailing: move SL in discrete steps.
        e.g., Every 0.5% profit move, lock in 0.3% of that step.
        """
        if config.step_size_pct <= 0:
            return None

        # Determine which step level we're at
        current_step = int(profit_pct / config.step_size_pct)
        if current_step <= state.step_level:
            return None  # Haven't reached next step yet

        # Calculate new SL: entry + (steps * lock_per_step)
        locked_profit_pct = current_step * config.step_lock_pct

        if is_long:
            new_sl = state.entry_price * (1 + locked_profit_pct / 100)
        else:
            new_sl = state.entry_price * (1 - locked_profit_pct / 100)

        state.step_level = current_step
        return new_sl

    @staticmethod
    def _hybrid_trail(
        state: TrailState, price: float, config: TrailConfig,
        is_long: bool, profit_pct: float, atr: Optional[float],
    ) -> Optional[float]:
        """
        Hybrid strategy:
          Phase 1: Breakeven once activation_pct is reached
          Phase 2: Step trail for moderate profit (0.5%-2%)
          Phase 3: Tight percentage trail for high profit (>2%)
        """
        # Phase 1: Move to breakeven
        if not state.breakeven_set and profit_pct >= config.breakeven_trigger_pct:
            state.breakeven_set = True
            if is_long:
                return state.entry_price * (1 + config.breakeven_buffer_pct / 100)
            else:
                return state.entry_price * (1 - config.breakeven_buffer_pct / 100)

        # Phase 2: Step trail (moderate profit)
        if profit_pct < 2.0:
            step_sl = TrailingStopLossEngine._step_trail(
                state, price, config, is_long, profit_pct
            )
            if step_sl is not None:
                return step_sl

        # Phase 3: Tight percentage trail (high profit)
        if profit_pct >= 1.5:
            # Tighten trail as profit grows
            dynamic_trail = max(config.min_trail_pct, config.trail_pct - (profit_pct * 0.1))
            if is_long:
                new_sl = state.peak_price * (1 - dynamic_trail / 100)
            else:
                new_sl = state.trough_price * (1 + dynamic_trail / 100)
            return new_sl

        return None

    @staticmethod
    def create_state(
        trade_id: str,
        trade_type: str,
        entry_price: float,
        stop_loss: float,
    ) -> TrailState:
        """Factory to create a new TrailState for a trade."""
        return TrailState(
            trade_id=trade_id,
            trade_type=trade_type,
            entry_price=entry_price,
            original_sl=stop_loss,
            current_sl=stop_loss,
            peak_price=entry_price,
            trough_price=entry_price,
        )

    @staticmethod
    def state_to_dict(state: TrailState) -> dict:
        """Serialize TrailState to dict for JSON persistence."""
        return {
            "trade_id": state.trade_id,
            "trade_type": state.trade_type,
            "entry_price": state.entry_price,
            "original_sl": state.original_sl,
            "current_sl": state.current_sl,
            "peak_price": state.peak_price,
            "trough_price": state.trough_price,
            "trail_activated": state.trail_activated,
            "breakeven_set": state.breakeven_set,
            "step_level": state.step_level,
            "adjustments": state.adjustments,
            "last_adjusted_price": state.last_adjusted_price,
            "history": state.history[-20:],  # Keep last 20 adjustments
        }

    @staticmethod
    def state_from_dict(d: dict) -> TrailState:
        """Deserialize TrailState from dict."""
        return TrailState(
            trade_id=d["trade_id"],
            trade_type=d["trade_type"],
            entry_price=d["entry_price"],
            original_sl=d["original_sl"],
            current_sl=d["current_sl"],
            peak_price=d["peak_price"],
            trough_price=d.get("trough_price", d["entry_price"]),
            trail_activated=d.get("trail_activated", False),
            breakeven_set=d.get("breakeven_set", False),
            step_level=d.get("step_level", 0),
            adjustments=d.get("adjustments", 0),
            last_adjusted_price=d.get("last_adjusted_price", 0),
            history=d.get("history", []),
        )
