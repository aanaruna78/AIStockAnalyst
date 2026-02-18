"""
RiskEngine v2 — Premium / ATR-based Risk Management
=====================================================
The biggest profitability upgrade.  Replaces old spot-based SL/target.

Options (premium-based):
  - Initial SL:  entry_premium * (1 - sl_pct)          (default -10%)
      or          entry_premium - 1.2 * premium_ATR_14
  - TP1:         entry_premium * (1 + tp1_pct)          (default +12%)
      → book 60% at TP1
  - Runner trail: max(1× premium_ATR, 6% of entry_premium)
  - Momentum-failure exit: spot recross + premium stagnation

Equity (ATR-based):
  - Initial SL:  1.0 × ATR_14 (or last swing low/high)
  - TP1:         1.2 × ATR → book 50-60%
  - Runner trail: 1.0 × ATR from peak (tighten to 0.8 late session)

Portfolio-level:
  - Daily loss cap: 2% of total capital
  - Consecutive-loss cooldown: 3 losses → 30 min
  - Max trades/day: 8 (options) / 10 (equity)
  - Spread gate (options): spread/premium > 1.2% → skip
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class RiskMode(str, Enum):
    PREMIUM_PCT = "PREMIUM_PCT"        # SL = entry * (1 - pct)
    PREMIUM_ATR = "PREMIUM_ATR"        # SL = entry - N * premium_ATR
    EQUITY_ATR = "EQUITY_ATR"          # SL = entry - N * ATR


class ExitReason(str, Enum):
    SL_HIT = "SL_HIT"
    TP1_HIT = "TP1_HIT"
    TRAILING_SL = "TRAILING_SL"
    MOMENTUM_FAILURE = "MOMENTUM_FAILURE"
    DAILY_LOSS_CAP = "DAILY_LOSS_CAP"
    COOLDOWN = "COOLDOWN"
    TIME_SQUAREOFF = "TIME_SQUAREOFF"
    MANUAL = "MANUAL"


@dataclass
class RiskConfig:
    """Risk parameters — can be overridden per profile."""
    # ── Options (premium-based) ──
    mode: RiskMode = RiskMode.PREMIUM_PCT
    sl_pct: float = 0.10                    # 10% of entry premium
    sl_atr_mult: float = 1.2               # for PREMIUM_ATR mode
    tp1_pct: float = 0.12                   # +12% premium for TP1
    tp1_book_pct: float = 0.60             # book 60% at TP1
    runner_trail_atr_mult: float = 1.0     # trail runner at 1× premium ATR
    runner_trail_pct_min: float = 0.06     # min 6% of entry premium trail

    # ── Equity (ATR-based) ──
    equity_sl_atr_mult: float = 1.0        # SL = 1.0× ATR
    equity_tp1_atr_mult: float = 1.2       # TP1 = 1.2× ATR
    equity_tp1_book_pct: float = 0.55      # book 55% at TP1
    equity_runner_atr_mult: float = 1.0    # trail at 1.0× ATR
    equity_late_tighten_mult: float = 0.8  # tighten to 0.8× ATR late session

    # ── Portfolio-level ──
    daily_loss_cap_pct: float = 0.02       # 2% of total capital
    max_capital_per_trade_pct: float = 0.20  # 20% per trade (options)
    max_trades_per_day: int = 8            # options
    equity_max_trades_per_day: int = 10    # equity
    consecutive_loss_limit: int = 3        # trigger cooldown after N losses
    cooldown_seconds: int = 1800           # 30 min cooldown

    # ── Momentum-failure exit ──
    mf_candles_stagnant: int = 3           # premium no new high for N candles
    mf_volume_collapse_ratio: float = 0.5  # volume drops to 50% of entry candle


@dataclass
class TradeRiskState:
    """Per-trade risk tracking state."""
    trade_id: str
    entry_price: float               # premium (options) or price (equity)
    entry_time: float                 # epoch
    is_long: bool = True
    # MFE / MAE tracking
    mfe: float = 0.0                 # max favorable excursion
    mae: float = 0.0                 # max adverse excursion
    peak_price: float = 0.0          # highest premium/price seen
    trough_price: float = float("inf")
    # TP1 tracking
    tp1_hit: bool = False
    tp1_price: float = 0.0
    original_qty: int = 0
    remaining_qty: int = 0
    # Premium stagnation counter
    candles_since_new_high: int = 0
    last_peak_candle_idx: int = 0
    # Trailing SL
    current_sl: float = 0.0
    initial_sl: float = 0.0


@dataclass
class PortfolioRiskState:
    """Global portfolio-level risk state."""
    total_capital: float = 100000.0
    daily_pnl: float = 0.0
    day_trade_count: int = 0
    consecutive_losses: int = 0
    cooldown_until: float = 0.0      # epoch timestamp
    kill_switch: bool = False
    kill_reason: str = ""
    current_date: str = ""


class RiskEngine:
    """
    Risk management engine for both options and equity.

    Responsibilities:
      - Compute initial SL / TP1 / trailing params
      - Track MFE / MAE per trade
      - Enforce portfolio-level kill-switch, cooldown, daily caps
      - Detect momentum-failure exits
    """

    def __init__(self, config: RiskConfig = RiskConfig()):
        self.config = config
        self.portfolio_state = PortfolioRiskState()
        self._trade_states: Dict[str, TradeRiskState] = {}

    # ------------------------------------------------------------------
    # Initialise risk for a new trade
    # ------------------------------------------------------------------

    def init_option_trade(
        self,
        trade_id: str,
        entry_premium: float,
        premium_atr: float = 0.0,
        quantity: int = 1,
        is_long: bool = True,
    ) -> dict:
        """
        Compute SL / TP1 for an options trade (premium-based).
        Returns dict with sl, tp1, tp1_book_qty, runner_qty.
        """
        cfg = self.config

        # Initial SL
        if cfg.mode == RiskMode.PREMIUM_ATR and premium_atr > 0:
            sl = entry_premium - cfg.sl_atr_mult * premium_atr if is_long else \
                 entry_premium + cfg.sl_atr_mult * premium_atr
        else:
            sl = entry_premium * (1 - cfg.sl_pct) if is_long else \
                 entry_premium * (1 + cfg.sl_pct)

        # TP1
        tp1 = entry_premium * (1 + cfg.tp1_pct) if is_long else \
              entry_premium * (1 - cfg.tp1_pct)

        tp1_book_qty = max(1, int(quantity * cfg.tp1_book_pct))
        runner_qty = quantity - tp1_book_qty

        state = TradeRiskState(
            trade_id=trade_id,
            entry_price=entry_premium,
            entry_time=time.time(),
            is_long=is_long,
            peak_price=entry_premium,
            trough_price=entry_premium,
            tp1_price=round(tp1, 2),
            original_qty=quantity,
            remaining_qty=quantity,
            current_sl=round(sl, 2),
            initial_sl=round(sl, 2),
        )
        self._trade_states[trade_id] = state

        return {
            "sl": round(sl, 2),
            "tp1": round(tp1, 2),
            "tp1_book_qty": tp1_book_qty,
            "runner_qty": runner_qty,
        }

    def init_equity_trade(
        self,
        trade_id: str,
        entry_price: float,
        atr: float,
        quantity: int = 1,
        is_long: bool = True,
    ) -> dict:
        """Compute SL / TP1 for an equity trade (ATR-based)."""
        cfg = self.config

        sl_dist = cfg.equity_sl_atr_mult * atr
        tp1_dist = cfg.equity_tp1_atr_mult * atr

        if is_long:
            sl = entry_price - sl_dist
            tp1 = entry_price + tp1_dist
        else:
            sl = entry_price + sl_dist
            tp1 = entry_price - tp1_dist

        tp1_book_qty = max(1, int(quantity * cfg.equity_tp1_book_pct))
        runner_qty = quantity - tp1_book_qty

        state = TradeRiskState(
            trade_id=trade_id,
            entry_price=entry_price,
            entry_time=time.time(),
            is_long=is_long,
            peak_price=entry_price,
            trough_price=entry_price,
            tp1_price=round(tp1, 2),
            original_qty=quantity,
            remaining_qty=quantity,
            current_sl=round(sl, 2),
            initial_sl=round(sl, 2),
        )
        self._trade_states[trade_id] = state

        return {
            "sl": round(sl, 2),
            "tp1": round(tp1, 2),
            "tp1_book_qty": tp1_book_qty,
            "runner_qty": runner_qty,
        }

    # ------------------------------------------------------------------
    # Risk loop tick — update MFE/MAE, trailing SL, momentum failure
    # ------------------------------------------------------------------

    def update_tick(
        self,
        trade_id: str,
        current_price: float,
        premium_atr: float = 0.0,
        atr: float = 0.0,
        candle_idx: int = 0,
        volume_ratio: float = 1.0,
        spot_in_breakout_zone: bool = False,
        vwap_recrossed: bool = False,
        is_late_session: bool = False,
        is_option: bool = True,
    ) -> Optional[ExitReason]:
        """
        Called every risk-loop tick (1–5 s).
        Updates MFE/MAE, trailing SL, checks exits.
        Returns ExitReason if trade should be closed, else None.
        """
        state = self._trade_states.get(trade_id)
        if state is None:
            return None

        # ── Update MFE / MAE ──
        if state.is_long:
            excursion = current_price - state.entry_price
            if excursion > state.mfe:
                state.mfe = excursion
            if excursion < 0 and abs(excursion) > state.mae:
                state.mae = abs(excursion)
            if current_price > state.peak_price:
                state.peak_price = current_price
                state.candles_since_new_high = 0
                state.last_peak_candle_idx = candle_idx
            else:
                state.candles_since_new_high = candle_idx - state.last_peak_candle_idx
        else:
            excursion = state.entry_price - current_price
            if excursion > state.mfe:
                state.mfe = excursion
            if excursion < 0 and abs(excursion) > state.mae:
                state.mae = abs(excursion)
            if current_price < state.trough_price:
                state.trough_price = current_price
                state.candles_since_new_high = 0
                state.last_peak_candle_idx = candle_idx
            else:
                state.candles_since_new_high = candle_idx - state.last_peak_candle_idx

        # ── SL hit ──
        if state.is_long and current_price <= state.current_sl:
            return ExitReason.SL_HIT
        if not state.is_long and current_price >= state.current_sl:
            return ExitReason.SL_HIT

        # ── TP1 hit (partial book) ──
        if not state.tp1_hit:
            if state.is_long and current_price >= state.tp1_price:
                state.tp1_hit = True
                return ExitReason.TP1_HIT
            if not state.is_long and current_price <= state.tp1_price:
                state.tp1_hit = True
                return ExitReason.TP1_HIT

        # ── Trailing SL for runner ──
        if state.tp1_hit:
            new_sl = self._compute_runner_trail(
                state, current_price, premium_atr, atr, is_option, is_late_session
            )
            if new_sl is not None:
                # Only tighten
                if state.is_long and new_sl > state.current_sl:
                    state.current_sl = round(new_sl, 2)
                elif not state.is_long and new_sl < state.current_sl:
                    state.current_sl = round(new_sl, 2)

        # ── Momentum-failure exit ──
        if self._check_momentum_failure(state, volume_ratio, spot_in_breakout_zone, vwap_recrossed):
            return ExitReason.MOMENTUM_FAILURE

        # ── Global kill-switch ──
        if self.portfolio_state.kill_switch:
            return ExitReason.DAILY_LOSS_CAP

        return None

    def _compute_runner_trail(
        self,
        state: TradeRiskState,
        current_price: float,
        premium_atr: float,
        atr: float,
        is_option: bool,
        is_late_session: bool,
    ) -> Optional[float]:
        cfg = self.config
        if is_option:
            trail_dist = max(
                cfg.runner_trail_atr_mult * premium_atr if premium_atr > 0 else 0,
                cfg.runner_trail_pct_min * state.entry_price,
            )
            if state.is_long:
                return state.peak_price - trail_dist
            else:
                return state.trough_price + trail_dist
        else:
            mult = cfg.equity_late_tighten_mult if is_late_session else cfg.equity_runner_atr_mult
            trail_dist = mult * atr if atr > 0 else state.entry_price * 0.01
            if state.is_long:
                return state.peak_price - trail_dist
            else:
                return state.trough_price + trail_dist

    def _check_momentum_failure(
        self,
        state: TradeRiskState,
        volume_ratio: float,
        spot_in_breakout_zone: bool,
        vwap_recrossed: bool,
    ) -> bool:
        """Detect momentum failure for fast scratch exit."""
        cfg = self.config
        # Condition 1: spot closes back inside breakout zone
        if spot_in_breakout_zone:
            return True
        # Condition 2: premium stagnation + VWAP recross
        if state.candles_since_new_high >= cfg.mf_candles_stagnant and vwap_recrossed:
            return True
        # Condition 3: volume collapse
        if volume_ratio < cfg.mf_volume_collapse_ratio and state.candles_since_new_high >= 2:
            return True
        return False

    # ------------------------------------------------------------------
    # Portfolio-level risk controls
    # ------------------------------------------------------------------

    def check_can_trade(self, is_option: bool = True) -> tuple[bool, str]:
        """Pre-trade portfolio gate. Returns (allowed, reason)."""
        ps = self.portfolio_state
        cfg = self.config

        # Kill switch
        if ps.kill_switch:
            return False, f"Kill switch: {ps.kill_reason}"

        # Daily loss cap
        if ps.total_capital > 0:
            loss_pct = abs(ps.daily_pnl) / ps.total_capital if ps.daily_pnl < 0 else 0
            if loss_pct >= cfg.daily_loss_cap_pct:
                ps.kill_switch = True
                ps.kill_reason = f"Daily loss cap {loss_pct*100:.1f}% >= {cfg.daily_loss_cap_pct*100:.1f}%"
                return False, ps.kill_reason

        # Cooldown
        if time.time() < ps.cooldown_until:
            remaining = int(ps.cooldown_until - time.time())
            return False, f"Cooldown: {remaining}s remaining ({ps.consecutive_losses} consecutive losses)"

        # Max trades
        max_t = cfg.max_trades_per_day if is_option else cfg.equity_max_trades_per_day
        if ps.day_trade_count >= max_t:
            return False, f"Max trades ({max_t}) reached"

        return True, ""

    def record_trade_result(self, pnl: float) -> None:
        """Update portfolio state after a trade closes."""
        ps = self.portfolio_state
        cfg = self.config

        ps.daily_pnl += pnl
        ps.day_trade_count += 1

        if pnl < 0:
            ps.consecutive_losses += 1
            if ps.consecutive_losses >= cfg.consecutive_loss_limit:
                ps.cooldown_until = time.time() + cfg.cooldown_seconds
        else:
            ps.consecutive_losses = 0

    def reset_daily(self, total_capital: float, date_str: str) -> None:
        """Reset daily counters at start of new trading day."""
        ps = self.portfolio_state
        if ps.current_date != date_str:
            ps.current_date = date_str
            ps.daily_pnl = 0.0
            ps.day_trade_count = 0
            ps.consecutive_losses = 0
            ps.cooldown_until = 0.0
            ps.kill_switch = False
            ps.kill_reason = ""
            ps.total_capital = total_capital

    def get_trade_state(self, trade_id: str) -> Optional[TradeRiskState]:
        return self._trade_states.get(trade_id)

    def remove_trade(self, trade_id: str) -> None:
        self._trade_states.pop(trade_id, None)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Global risk status for API."""
        ps = self.portfolio_state
        return {
            "kill_switch": ps.kill_switch,
            "kill_reason": ps.kill_reason,
            "daily_pnl": round(ps.daily_pnl, 2),
            "daily_loss_cap_pct": self.config.daily_loss_cap_pct * 100,
            "day_trade_count": ps.day_trade_count,
            "consecutive_losses": ps.consecutive_losses,
            "cooldown_until": ps.cooldown_until,
            "cooldown_remaining_s": max(0, int(ps.cooldown_until - time.time())),
            "total_capital": round(ps.total_capital, 2),
        }

    def trade_risk_to_dict(self, trade_id: str) -> Optional[dict]:
        s = self._trade_states.get(trade_id)
        if not s:
            return None
        return {
            "trade_id": s.trade_id,
            "entry_price": s.entry_price,
            "current_sl": s.current_sl,
            "initial_sl": s.initial_sl,
            "tp1_price": s.tp1_price,
            "tp1_hit": s.tp1_hit,
            "mfe": round(s.mfe, 2),
            "mae": round(s.mae, 2),
            "peak_price": round(s.peak_price, 2),
            "remaining_qty": s.remaining_qty,
            "candles_since_new_high": s.candles_since_new_high,
        }
