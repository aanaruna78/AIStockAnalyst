"""
Options Scalping Service v2 — Momentum-first Nifty Weekly Options
==================================================================
Complete rewrite of signal generation and risk management.
Keeps: PaperTradingEngine core, Iceberg splitting, JSON persistence.

New:
  - MarketDataStore (rolling 1-min candles + indicators)
  - RegimeEngine (mandatory gate)
  - MomentumSignalEngine (breakout + expansion + participation)
  - RiskEngine v2 (premium-based SL/TP + MFE/MAE)
  - SelfLearningEngine v2 (profiles + bandit)
  - MetricsEngine (telemetry + daily report)
  - PremiumSimulator (Greeks-based)
  - Two-loop runtime: SignalLoop (30s) + RiskLoop (3s)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import json
import os
import logging
import re
import requests
import threading
import time as _time
import random as _random

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from shared.iceberg_order import IcebergEngine
from shared.market_data_store import MarketDataStore, Candle, OptionDataStore, PremiumCandle
from shared.regime_engine import RegimeEngine, Regime
from shared.momentum_signal import (
    MomentumSignalEngine, MomentumConfig, SignalDirection, EntryMode,
)
from shared.risk_engine import RiskEngine, RiskConfig, RiskMode
from shared.self_learning import SelfLearningEngine
from shared.metrics_engine import MetricsEngine, TradeMetrics
from shared.premium_simulator import PremiumSimulator

app = FastAPI(title="SignalForge Options Scalping Service v2")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OptionsScalpingV2")

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except ImportError:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")

# ──────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────
NIFTY_LOT_SIZE = 65
DEFAULT_LOTS = 5
ICEBERG_THRESHOLD_LOTS = 5
INITIAL_CAPITAL = 100000.0
MAX_TRADES_PER_DAY = 8            # v2: 8 trades (momentum = fewer, cleaner)
SQUARE_OFF_HOUR = 15
SQUARE_OFF_MIN = 15
SIGNAL_LOOP_SEC = 30              # signal loop interval
RISK_LOOP_SEC = 3                 # risk loop interval
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
TRADES_FILE = os.path.join(DATA_DIR, "options_paper_trades.json")
GOOGLE_FINANCE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
SLIPPAGE_MIN = 0.0001
SLIPPAGE_MAX = 0.0003
LATENCY_MIN_MS = 50
LATENCY_MAX_MS = 200

# ── Greeks Filtering Thresholds ──────────────────────────────────
MIN_DELTA_ABS = 0.25          # Reject deep OTM (delta < 0.25)
MAX_DELTA_ABS = 0.75          # Reject deep ITM (delta > 0.75)
MIN_PREMIUM = 5.0             # Reject options priced below ₹5
MAX_THETA_PCT_OF_PREMIUM = 5.0  # Reject if |theta/day| > 5% of premium
MIN_GAMMA = 0.0005            # Minimum gamma for meaningful delta moves

# ── Cooldown Configuration ───────────────────────────────────────
LOSS_COOLDOWN_SEC = 300       # 5 min cooldown after a loss
CONSEC_LOSS_COOLDOWN_SEC = 600  # 10 min after 2+ consecutive losses
MAX_SAME_STRIKE_PER_DAY = 2   # Max entries at same strike/direction per day


# ──────────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────────
class TradeRequest(BaseModel):
    direction: str
    strike: int
    entry_premium: float
    lots: int = DEFAULT_LOTS
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    broker: Optional[str] = "paper"


class TradeCloseRequest(BaseModel):
    trade_id: str
    exit_premium: float
    user_id: Optional[str] = None


# ──────────────────────────────────────────────────────────────────
# Engine singletons
# ──────────────────────────────────────────────────────────────────
market_store = MarketDataStore(symbol="NIFTY")
option_store = OptionDataStore()
regime_engine = RegimeEngine(atr_min_threshold=5.0)
momentum_engine = MomentumSignalEngine()
risk_engine = RiskEngine(RiskConfig(
    mode=RiskMode.PREMIUM_PCT,
    sl_pct=0.10,
    tp1_pct=0.12,
    tp1_book_pct=0.60,
    runner_trail_pct_min=0.06,
    max_trades_per_day=MAX_TRADES_PER_DAY,
    daily_loss_cap_pct=0.02,
    consecutive_loss_limit=3,
    cooldown_seconds=1800,
))
learning_engine = SelfLearningEngine(data_dir=DATA_DIR)
metrics_engine = MetricsEngine(data_dir=DATA_DIR)


# ──────────────────────────────────────────────────────────────────
# Paper Trading Engine (kept, enhanced with v2 fields)
# ──────────────────────────────────────────────────────────────────
class PaperTradingEngine:
    def __init__(self):
        self.capital = INITIAL_CAPITAL
        self.active_trades = []
        self.trade_history = []
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.day_trade_count = 0
        self.current_date = None
        # Auto-trade state
        self.auto_trade_enabled = True
        self.auto_trade_log = []
        self.last_scan_time = None
        self.last_signal = None
        # Iceberg orders
        self.iceberg_orders: list = []
        # Premium simulators per trade
        self._premium_sims: dict = {}
        # Candle index counter
        self._candle_idx: int = 0
        # ── Cooldown tracking ──
        self._last_loss_time: float = 0        # epoch secs of last loss
        self._consecutive_losses: int = 0       # running consecutive loss count
        self._daily_strike_entries: dict = {}   # {f"{strike}-{dir}": count} per day
        self._load()

    def _load(self):
        try:
            if os.path.exists(TRADES_FILE):
                with open(TRADES_FILE, "r") as f:
                    data = json.load(f)
                self.capital = data.get("capital", INITIAL_CAPITAL)
                self.active_trades = data.get("active_trades", [])
                self.trade_history = data.get("trade_history", [])
                self.total_pnl = data.get("total_pnl", 0.0)
                self.daily_pnl = data.get("daily_pnl", 0.0)
                self.day_trade_count = data.get("day_trade_count", 0)
                self.current_date = data.get("current_date")
                self.iceberg_orders = data.get("iceberg_orders", [])
                # GAP-9: restore cooldown state
                cs = data.get("cooldown_state", {})
                self._last_loss_time = cs.get("last_loss_time", 0)
                self._consecutive_losses = cs.get("consecutive_losses", 0)
                self._daily_strike_entries = cs.get("daily_strike_entries", {})
                logger.info(f"Loaded paper trades: capital=₹{self.capital:,.2f}, trades={len(self.trade_history)}, cooldown_losses={self._consecutive_losses}")
        except Exception as e:
            logger.error(f"Failed to load paper trades: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
            data = {
                "capital": self.capital,
                "active_trades": self.active_trades,
                "trade_history": self.trade_history,
                "total_pnl": self.total_pnl,
                "daily_pnl": self.daily_pnl,
                "day_trade_count": self.day_trade_count,
                "current_date": self.current_date,
                "iceberg_orders": self.iceberg_orders[-50:],
                # GAP-9: persist cooldown state across restarts
                "cooldown_state": {
                    "last_loss_time": self._last_loss_time,
                    "consecutive_losses": self._consecutive_losses,
                    "daily_strike_entries": self._daily_strike_entries,
                },
            }
            with open(TRADES_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save paper trades: {e}")

    def _reset_daily(self):
        today = datetime.now(IST).strftime("%Y-%m-%d")
        if self.current_date != today:
            self.current_date = today
            self.daily_pnl = 0.0
            self.day_trade_count = 0
            self._consecutive_losses = 0
            self._last_loss_time = 0
            self._daily_strike_entries = {}
            risk_engine.reset_daily(self.capital, today)
            metrics_engine.reset_daily()
            market_store.reset_session()
            option_store.reset()
            momentum_engine.reset()
            self._save()

    def place_trade(
        self,
        direction: str,
        strike: int,
        entry_premium: float,
        lots: int = DEFAULT_LOTS,
        indicators: dict = None,
        user_id: str = None,
        profile_id: str = "",
        regime: str = "",
        breakout_level: float = 0.0,
        entry_mode: str = "",
        greeks: dict = None,
    ) -> dict:
        self._reset_daily()

        # v2: Portfolio-level risk gate
        can_trade, reason = risk_engine.check_can_trade(is_option=True)
        if not can_trade:
            return {"status": "rejected", "reason": reason}

        if self.day_trade_count >= MAX_TRADES_PER_DAY:
            return {"status": "rejected", "reason": f"Max {MAX_TRADES_PER_DAY} trades/day reached"}

        if len(self.active_trades) > 0:
            return {"status": "rejected", "reason": "Close existing position before opening new"}

        now = datetime.now(IST)
        if now.hour >= SQUARE_OFF_HOUR and now.minute >= SQUARE_OFF_MIN:
            return {"status": "rejected", "reason": "Past intraday cutoff (3:15 PM)"}

        # ── Cooldown after consecutive losses ──
        if self._last_loss_time > 0:
            elapsed = _time.time() - self._last_loss_time
            cooldown = CONSEC_LOSS_COOLDOWN_SEC if self._consecutive_losses >= 2 else LOSS_COOLDOWN_SEC
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                return {"status": "rejected", "reason": f"Cooldown active: {remaining}s remaining after {self._consecutive_losses} consecutive loss(es)"}

        # ── Per-strike daily limit ──
        strike_key = f"{strike}-{direction}"
        entries_today = self._daily_strike_entries.get(strike_key, 0)
        if entries_today >= MAX_SAME_STRIKE_PER_DAY:
            return {"status": "rejected", "reason": f"Max {MAX_SAME_STRIKE_PER_DAY} entries per day for {direction} {strike}"}

        # ── Greeks validation ──
        if greeks:
            delta_abs = abs(greeks.get("delta", 0.5))
            gamma_val = abs(greeks.get("gamma", 0.001))
            theta_val = abs(greeks.get("theta", 0))

            if delta_abs < MIN_DELTA_ABS:
                return {"status": "rejected", "reason": f"Delta {delta_abs:.3f} < {MIN_DELTA_ABS} — too far OTM, low probability of profit"}
            if delta_abs > MAX_DELTA_ABS:
                return {"status": "rejected", "reason": f"Delta {delta_abs:.3f} > {MAX_DELTA_ABS} — too deep ITM, poor risk/reward"}
            if gamma_val < MIN_GAMMA:
                return {"status": "rejected", "reason": f"Gamma {gamma_val:.5f} < {MIN_GAMMA} — insufficient delta sensitivity"}
            if entry_premium > 0 and theta_val > 0:
                theta_pct = (theta_val / entry_premium) * 100
                if theta_pct > MAX_THETA_PCT_OF_PREMIUM:
                    return {"status": "rejected", "reason": f"Theta decay {theta_pct:.1f}%/day > {MAX_THETA_PCT_OF_PREMIUM}% — rapid time decay"}

        if entry_premium < MIN_PREMIUM:
            return {"status": "rejected", "reason": f"Premium ₹{entry_premium:.2f} < ₹{MIN_PREMIUM} — too cheap, wide spreads"}

        # Capital gate: max 20% per trade
        max_cost = self.capital * risk_engine.config.max_capital_per_trade_pct
        trade_cost = entry_premium * NIFTY_LOT_SIZE * lots
        if trade_cost > max_cost:
            return {"status": "rejected", "reason": f"Cost ₹{trade_cost:,.0f} > {risk_engine.config.max_capital_per_trade_pct*100:.0f}% cap ₹{max_cost:,.0f}"}

        # Simulate slippage
        slippage_pct = _random.uniform(SLIPPAGE_MIN, SLIPPAGE_MAX)
        slipped_premium = round(entry_premium * (1 + slippage_pct), 2)
        latency_ms = _random.randint(LATENCY_MIN_MS, LATENCY_MAX_MS)

        quantity = NIFTY_LOT_SIZE * lots

        # v2: RiskEngine computes SL / TP1
        premium_atr = option_store.premium_atr(side=direction, period=14)
        risk_params = risk_engine.init_option_trade(
            trade_id=f"OPT-{now.strftime('%Y%m%d%H%M%S')}-{_random.randint(1000,9999)}",
            entry_premium=slipped_premium,
            premium_atr=premium_atr,
            quantity=quantity,
            is_long=True,
        )

        trade = {
            "trade_id": risk_params.get("trade_id", f"OPT-{now.strftime('%Y%m%d%H%M%S')}-{_random.randint(1000,9999)}"),
            "direction": direction,
            "strike": strike,
            "lots": lots,
            "lot_size": NIFTY_LOT_SIZE,
            "entry_premium": slipped_premium,
            "original_premium": entry_premium,
            "slippage_pct": round(slippage_pct * 100, 4),
            "latency_ms": latency_ms,
            "sl_premium": risk_params["sl"],
            "target_premium": risk_params["tp1"],
            "tp1_book_qty": risk_params["tp1_book_qty"],
            "runner_qty": risk_params["runner_qty"],
            "status": "OPEN",
            "entry_time": now.isoformat(),
            "quantity": quantity,
            "indicators": indicators or {},
            "user_id": user_id,
            "is_intraday": True,
            "iceberg_used": lots >= ICEBERG_THRESHOLD_LOTS,
            # v2: momentum context
            "profile_id": profile_id,
            "regime": regime,
            "breakout_level": breakout_level,
            "entry_mode": entry_mode,
            "mfe": 0.0,
            "mae": 0.0,
        }

        # Use RiskEngine's trade_id
        trade_id = list(risk_engine._trade_states.keys())[-1] if risk_engine._trade_states else trade["trade_id"]
        trade["trade_id"] = trade_id

        # Iceberg: trigger at >= threshold (5 lots splits into 2+2+1)
        if lots >= ICEBERG_THRESHOLD_LOTS:
            iceberg = IcebergEngine.create_option_iceberg(
                symbol=f"NIFTY-{strike}-{direction}",
                trade_type="BUY",
                lots=lots,
                premium=slipped_premium,
                lot_size=NIFTY_LOT_SIZE,
                user_id=user_id,
            )
            trade["iceberg_id"] = iceberg.iceberg_id
            trade["iceberg_slices"] = len(iceberg.slices)
            self.iceberg_orders.append(IcebergEngine.order_to_dict(iceberg))

        # Premium simulator for this trade
        spot = market_store.indicators.spot or get_nifty_spot() or 23000
        dte = _days_to_expiry()
        self._premium_sims[trade_id] = PremiumSimulator(
            spot=spot, strike=strike, option_type=direction,
            days_to_expiry=dte, iv=_get_real_iv(direction), lot_size=NIFTY_LOT_SIZE,
        )

        self.active_trades.append(trade)
        self.day_trade_count += 1
        # Track per-strike entries for daily limit
        strike_key = f"{strike}-{direction}"
        self._daily_strike_entries[strike_key] = self._daily_strike_entries.get(strike_key, 0) + 1
        self._save()

        logger.info(f"MOMENTUM ENTRY: {direction} {strike} @ ₹{slipped_premium} x{lots}lots SL=₹{risk_params['sl']} TP1=₹{risk_params['tp1']} profile={profile_id}")
        return {"status": "placed", "trade": trade}

    def close_trade(self, trade_id: str, exit_premium: float, exit_reason: str = "Manual") -> dict:
        trade = None
        for t in self.active_trades:
            if t["trade_id"] == trade_id:
                trade = t
                break
        if not trade:
            return {"status": "error", "reason": "Trade not found"}

        slippage_pct = _random.uniform(SLIPPAGE_MIN, SLIPPAGE_MAX)
        slipped_exit = round(exit_premium * (1 - slippage_pct), 2)

        pnl_per_unit = slipped_exit - trade["entry_premium"]
        total_pnl = round(pnl_per_unit * trade["quantity"], 2)

        now = datetime.now(IST)
        trade["exit_premium"] = slipped_exit
        trade["exit_time"] = now.isoformat()
        trade["pnl"] = total_pnl
        trade["pnl_pct"] = round((pnl_per_unit / trade["entry_premium"]) * 100, 2)
        trade["exit_slippage_pct"] = round(slippage_pct * 100, 4)
        trade["status"] = "CLOSED"
        trade["result"] = "WIN" if total_pnl > 0 else "LOSS"
        trade["exit_reason"] = exit_reason

        entry_time = datetime.fromisoformat(trade["entry_time"])
        hold_seconds = (now - entry_time).total_seconds()
        trade["hold_duration_sec"] = round(hold_seconds, 1)

        # v2: Get MFE/MAE from risk engine
        risk_state = risk_engine.get_trade_state(trade_id)
        if risk_state:
            trade["mfe"] = round(risk_state.mfe, 2)
            trade["mae"] = round(risk_state.mae, 2)

        self.active_trades = [t for t in self.active_trades if t["trade_id"] != trade_id]
        self.trade_history.append(trade)
        self.capital += total_pnl
        self.daily_pnl += total_pnl
        self.total_pnl += total_pnl

        # ── Track consecutive losses for cooldown ──
        if total_pnl < 0:
            self._consecutive_losses += 1
            self._last_loss_time = _time.time()
        else:
            self._consecutive_losses = 0
            self._last_loss_time = 0

        # v2: Record in risk engine + metrics + learning
        risk_engine.record_trade_result(total_pnl)
        risk_engine.remove_trade(trade_id)
        self._premium_sims.pop(trade_id, None)

        # Metrics
        slippage_cost = abs(slippage_pct) * trade["entry_premium"] * trade["quantity"]
        spread_cost = 0
        if option_store.ce_candles or option_store.pe_candles:
            sp = option_store.ce_spread if trade["direction"] == "CE" else option_store.pe_spread
            spread_cost = sp * trade["quantity"] * 0.5

        metrics_engine.record_trade(TradeMetrics(
            trade_id=trade_id,
            regime=trade.get("regime", ""),
            profile_id=trade.get("profile_id", ""),
            breakout_level=trade.get("breakout_level", 0),
            entry_mode=trade.get("entry_mode", ""),
            pnl=total_pnl,
            pnl_pct=trade["pnl_pct"],
            mfe=trade.get("mfe", 0),
            mae=trade.get("mae", 0),
            spread_cost=round(spread_cost, 2),
            slippage_cost=round(slippage_cost, 2),
            entry_time=trade["entry_time"],
            exit_time=trade["exit_time"],
            hold_seconds=hold_seconds,
            exit_reason=exit_reason,
        ))

        # Learning
        drawdown = trade.get("mae", 0)
        mfe = trade.get("mfe", 0)
        capture = total_pnl / mfe if mfe > 0 and total_pnl > 0 else 0
        learning_engine.record_trade_result(
            profile_id=trade.get("profile_id", "P3_MID_TREND"),
            pnl=total_pnl,
            drawdown=drawdown,
            regime=trade.get("regime", ""),
            mfe_capture=capture,
        )

        self._save()
        logger.info(f"CLOSED [{trade['result']}]: {trade['direction']} {trade['strike']} PnL=₹{total_pnl:,.2f} ({trade['pnl_pct']:+.2f}%) Reason={exit_reason} MFE={trade.get('mfe',0):.2f}")
        return {"status": "closed", "trade": trade}

    def get_portfolio(self) -> dict:
        self._reset_daily()
        wins = [t for t in self.trade_history if t.get("result") == "WIN"]
        losses = [t for t in self.trade_history if t.get("result") == "LOSS"]
        total = len(self.trade_history)
        win_rate = (len(wins) / total * 100) if total > 0 else 0

        realized_pnl = round(sum(t.get("pnl", 0) for t in self.trade_history), 2)
        unrealized_pnl = 0.0
        for trade in self.active_trades:
            sim = self._premium_sims.get(trade["trade_id"])
            if sim:
                trade["ltp"] = round(sim.premium, 2)
                trade["unrealized_pnl"] = round((sim.premium - trade["entry_premium"]) * trade["quantity"], 2)
                unrealized_pnl += trade["unrealized_pnl"]

        return {
            "capital": round(self.capital, 2),
            "initial_capital": INITIAL_CAPITAL,
            "total_pnl": round(self.total_pnl, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "realized_pnl": realized_pnl,
            "unrealized_pnl": round(unrealized_pnl, 2),
            "active_trades": self.active_trades,
            "trade_history": self.trade_history[-50:],
            "stats": {
                "total_trades": total,
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(win_rate, 1),
                "avg_win": round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0,
                "avg_loss": round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0,
                "best_trade": round(max((t["pnl"] for t in self.trade_history), default=0), 2),
                "worst_trade": round(min((t["pnl"] for t in self.trade_history), default=0), 2),
                "day_trade_count": self.day_trade_count,
                "max_trades_per_day": MAX_TRADES_PER_DAY,
            },
            "lot_size": NIFTY_LOT_SIZE,
            "default_lots": DEFAULT_LOTS,
            "current_date": self.current_date,
        }

    def reset(self) -> dict:
        self.capital = INITIAL_CAPITAL
        self.active_trades = []
        self.trade_history = []
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.day_trade_count = 0
        self.current_date = None
        self.iceberg_orders = []
        self._premium_sims = {}
        self._save()
        self.auto_trade_log = []
        return {"status": "reset", "capital": self.capital}

    def _add_log(self, action: str, detail: str = ""):
        entry = {
            "time": datetime.now(IST).strftime("%H:%M:%S"),
            "action": action,
            "detail": detail,
        }
        self.auto_trade_log.append(entry)
        self.auto_trade_log = self.auto_trade_log[-100:]


paper_engine = PaperTradingEngine()


# ──────────────────────────────────────────────────────────────────
# Nifty Spot / Options Helpers
# ──────────────────────────────────────────────────────────────────
def get_nifty_spot() -> Optional[float]:
    """GAP-4: Multi-source Nifty spot with fallback chain.
    1. Market Data Service (internal, reliable)
    2. Google Finance (scraping)
    3. yfinance direct (circuit-breaker safe)
    Also returns volume when available via _last_spot_data.
    """
    global _last_spot_data

    # Source 1: Internal market-data-service
    try:
        mds_url = os.environ.get("MARKET_DATA_SERVICE_URL", "http://market-data-service:8000")
        resp = requests.get(f"{mds_url}/quote/NIFTY_50", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            ltp = data.get("ltp")
            if ltp and ltp > 0:
                _last_spot_data = data  # Cache volume + other fields
                return float(ltp)
    except Exception as e:
        logger.debug(f"Market data service unavailable: {e}")

    # Source 2: Google Finance
    try:
        url = "https://www.google.com/finance/quote/NIFTY_50:INDEXNSE"
        headers = {"User-Agent": GOOGLE_FINANCE_UA}
        resp = requests.get(url, headers=headers, timeout=8, verify=False)
        if resp.status_code == 200:
            match = re.search(r'data-last-price="([\d\.]+)"', resp.text)
            if match:
                return float(match.group(1))
    except Exception as e:
        logger.debug(f"Google Finance failed: {e}")

    # Source 3: yfinance direct
    try:
        import yfinance as yf
        ticker = yf.Ticker("^NSEI")
        data = ticker.fast_info
        ltp = getattr(data, "last_price", None) or getattr(data, "previous_close", None)
        if ltp and ltp > 0:
            return float(ltp)
    except Exception as e:
        logger.debug(f"yfinance direct failed: {e}")

    logger.warning("All spot data sources failed")
    return None


# Cache for last spot data (includes volume from market-data-service)
_last_spot_data: dict = {}

# GAP-1: NSE option chain OI cache (refreshed every 3 minutes)
_oi_cache: dict = {"data": None, "timestamp": 0}
_OI_CACHE_TTL = 180  # 3 minutes

# GAP-3: Real IV cache (populated from NSE option chain)
_iv_cache: dict = {"ce_iv": 15.0, "pe_iv": 15.0}


def _get_real_iv(direction: str) -> float:
    """GAP-3: Return real IV from NSE option chain if available, else default 15%."""
    key = "ce_iv" if direction.upper() == "CE" else "pe_iv"
    return _iv_cache.get(key, 15.0)


def _fetch_nse_option_oi(spot: float) -> dict:
    """GAP-1: Fetch real Open Interest data from NSE option chain API.
    Falls back to volume-derived estimates if NSE is unavailable.
    Returns: {oi_change_call_pct, oi_change_put_pct, spread_pct}
    """
    now_ts = _time.time()

    # Check cache
    if _oi_cache["data"] and (now_ts - _oi_cache["timestamp"]) < _OI_CACHE_TTL:
        return _oi_cache["data"]

    # Try NSE option chain API
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        # First get cookies from NSE main page
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=5)
        resp = session.get(
            "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY",
            headers=headers,
            timeout=8,
        )
        if resp.status_code == 200:
            chain_data = resp.json()
            records = chain_data.get("records", {}).get("data", [])
            atm = round(spot / 50) * 50

            # Find ATM and nearby strikes for OI analysis
            total_ce_oi_chg = 0
            total_pe_oi_chg = 0
            total_ce_oi = 0
            total_pe_oi = 0
            bid_ask_spreads = []

            for rec in records:
                strike = rec.get("strikePrice", 0)
                if abs(strike - atm) > 200:  # Only look at strikes within 200 pts
                    continue
                ce = rec.get("CE", {})
                pe = rec.get("PE", {})
                if ce:
                    total_ce_oi += ce.get("openInterest", 0)
                    total_ce_oi_chg += ce.get("changeinOpenInterest", 0)
                    if ce.get("bidprice", 0) > 0 and ce.get("askprice", 0) > 0:
                        s = (ce["askprice"] - ce["bidprice"]) / ce["askprice"] * 100
                        bid_ask_spreads.append(s)
                    # GAP-3: Extract real IV from ATM strike
                    if strike == atm and ce.get("impliedVolatility", 0) > 0:
                        _iv_cache["ce_iv"] = ce["impliedVolatility"]
                if pe:
                    total_pe_oi += pe.get("openInterest", 0)
                    total_pe_oi_chg += pe.get("changeinOpenInterest", 0)
                    if pe.get("bidprice", 0) > 0 and pe.get("askprice", 0) > 0:
                        s = (pe["askprice"] - pe["bidprice"]) / pe["askprice"] * 100
                        bid_ask_spreads.append(s)
                    # GAP-3: Extract real IV from ATM strike
                    if strike == atm and pe.get("impliedVolatility", 0) > 0:
                        _iv_cache["pe_iv"] = pe["impliedVolatility"]

            # Convert to percentage change
            oi_call_pct = (total_ce_oi_chg / total_ce_oi * 100) if total_ce_oi > 0 else 0
            oi_put_pct = (total_pe_oi_chg / total_pe_oi * 100) if total_pe_oi > 0 else 0
            avg_spread = sum(bid_ask_spreads) / len(bid_ask_spreads) if bid_ask_spreads else 0.5

            result = {
                "oi_change_call_pct": round(oi_call_pct, 2),
                "oi_change_put_pct": round(oi_put_pct, 2),
                "spread_pct": round(avg_spread, 2),
                "source": "nse",
            }
            _oi_cache["data"] = result
            _oi_cache["timestamp"] = now_ts
            return result

    except Exception as e:
        logger.debug(f"NSE option chain fetch failed: {e}")

    # Fallback: volume-based OI estimation
    # Higher volume tends to correlate with OI buildup
    all_candles = market_store.get_candles()
    if all_candles and len(all_candles) >= 2:
        recent_vol = all_candles[-1].volume
        avg_vol = sum(c.volume for c in all_candles) / len(all_candles)
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

        # Estimate OI change from volume (muted range vs random)
        oi_call_est = (vol_ratio - 1.0) * 3.0  # Positive vol spike → positive OI
        oi_put_est = (vol_ratio - 1.0) * 2.5
        result = {
            "oi_change_call_pct": round(max(-3, min(5, oi_call_est)), 2),
            "oi_change_put_pct": round(max(-3, min(5, oi_put_est)), 2),
            "spread_pct": round(0.3 + max(0, (1 - vol_ratio) * 0.4), 2),  # Wider spread on low vol
            "source": "volume_estimate",
        }
    else:
        # Conservative defaults (not random)
        result = {
            "oi_change_call_pct": 0.0,
            "oi_change_put_pct": 0.0,
            "spread_pct": 0.5,
            "source": "default",
        }

    _oi_cache["data"] = result
    _oi_cache["timestamp"] = now_ts
    return result


def _days_to_expiry() -> float:
    """GAP-8: Count trading days to next weekly expiry (Thursday).
    Excludes weekends and NSE holidays for accurate theta calculation.
    """
    now = datetime.now(IST)
    days_ahead = 3 - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    expiry = now + timedelta(days=days_ahead)

    # Count only trading days (excluding weekends & holidays)
    try:
        from services.market_data_service.trading_calendar import TradingCalendar
        return TradingCalendar.trading_days_to_expiry(expiry)
    except ImportError:
        pass

    # Inline fallback: count business days (weekdays only)
    count = 0
    current = now
    while current.date() < expiry.date():
        current = current + timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            count += 1
    # Add fractional portion of today
    if now.weekday() < 5:
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        if now < market_close:
            remaining_secs = (market_close - now).total_seconds()
            count += remaining_secs / (6.25 * 3600)  # 6h15m trading day
    return max(0.01, count)


def _get_next_thursday() -> str:
    now = datetime.now(IST)
    days_ahead = 3 - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


def _minute_of_day() -> int:
    now = datetime.now(IST)
    return now.hour * 60 + now.minute


def _is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 555 <= minutes <= 915   # 9:15 – 15:15


# ──────────────────────────────────────────────────────────────────
# Two-Loop Runtime
# ──────────────────────────────────────────────────────────────────

def _signal_loop():
    """
    Signal Loop (30s):
      1. Fetch spot, build candle
      2. RegimeEngine classify
      3. SelfLearning select profile
      4. MomentumSignalEngine evaluate
      5. If eligible + gates pass → place trade
    """
    logger.info("Signal loop started")
    _last_spot = None
    _candle_start = None
    _candle_high = 0
    _candle_low = float("inf")
    _candle_open = 0
    _candle_vol = 0
    _has_real_volume = False  # Track if we have real volume data

    while True:
        try:
            if not paper_engine.auto_trade_enabled or not _is_market_open():
                _time.sleep(SIGNAL_LOOP_SEC)
                continue

            spot = get_nifty_spot()
            if not spot:
                paper_engine._add_log("SIGNAL", "No spot data")
                _time.sleep(SIGNAL_LOOP_SEC)
                continue

            paper_engine.last_scan_time = datetime.now(IST).isoformat()
            paper_engine._reset_daily()

            # ── Build 1-min candle (accumulate over signal ticks) ──
            now = datetime.now(IST)
            current_minute = now.replace(second=0, microsecond=0)

            if _candle_start is None or current_minute != _candle_start:
                # Flush previous candle
                if _candle_start is not None and _candle_open > 0:
                    candle = Candle(
                        timestamp=_candle_start,
                        open=_candle_open,
                        high=_candle_high,
                        low=_candle_low,
                        close=spot,
                        volume=_candle_vol,
                    )
                    market_store.add_candle(candle)
                    paper_engine._candle_idx += 1

                    # Also feed premium sim candles (simulated)
                    atm = round(spot / 50) * 50
                    for side in ("CE", "PE"):
                        sim = PremiumSimulator(spot=spot, strike=atm, option_type=side,
                                              days_to_expiry=_days_to_expiry(), iv=_get_real_iv(side))
                        pc = PremiumCandle(
                            timestamp=_candle_start,
                            open=sim.premium * 0.99, high=sim.premium * 1.01,
                            low=sim.premium * 0.98, close=sim.premium,
                            volume=_candle_vol,
                            iv=sim.iv,
                            bid=sim.premium * 0.998, ask=sim.premium * 1.002,
                        )
                        if side == "CE":
                            option_store.add_ce_candle(pc)
                        else:
                            option_store.add_pe_candle(pc)

                # Start new candle — GAP-2: use real volume from market-data-service
                _candle_start = current_minute
                _candle_open = spot
                _candle_high = spot
                _candle_low = spot
                _raw_vol = _last_spot_data.get("volume") if _last_spot_data else None
                _candle_vol = int(_raw_vol) if _raw_vol and _raw_vol > 0 else 0
                if _candle_vol > 0:
                    _has_real_volume = True
                else:
                    _has_real_volume = False
                    _candle_vol = _random.randint(50000, 200000)  # Fallback if no real data
            else:
                _candle_high = max(_candle_high, spot)
                _candle_low = min(_candle_low, spot)
                # Accumulate volume from real data if available
                _raw_tick_vol = _last_spot_data.get("volume") if _last_spot_data else None
                tick_vol = int(_raw_tick_vol) if _raw_tick_vol and _raw_tick_vol > 0 else 0
                if tick_vol > 0:
                    _candle_vol = tick_vol  # Cumulative from source
                    _has_real_volume = True
                else:
                    _candle_vol += _random.randint(5000, 20000)  # Fallback

            ind = market_store.indicators

            # ── Regime classification ──
            candles = market_store.get_candles(n=3)
            range_3 = 0
            if len(candles) >= 3:
                range_3 = max(c.high for c in candles[-3:]) - min(c.low for c in candles[-3:])

            regime_result = regime_engine.classify(
                spot=spot,
                vwap=ind.vwap if ind.vwap > 0 else spot,
                vwap_slope=ind.vwap_slope,
                atr=ind.atr_14 if ind.atr_14 > 0 else spot * 0.001,
                minute_of_day=_minute_of_day(),
                range_last_3=range_3,
            )

            # ── Profile selection ──
            profile = learning_engine.select_profile(regime_result.recommended_profile_id)

            # ── Momentum signal ──
            # When volume is synthetic (no real data from source), bypass vol spike filter
            effective_vol_spike_min = profile.vol_spike_min if _has_real_volume else 0.0
            mom_config = MomentumConfig(
                confirm_candles=profile.confirm_candles,
                vol_spike_min=effective_vol_spike_min,
                confidence_min=profile.confidence_threshold,
                default_entry_mode=EntryMode(profile.entry_mode),
            )

            # Average volume for spike calculation
            all_candles = market_store.get_candles()
            avg_vol = sum(c.volume for c in all_candles) / max(1, len(all_candles)) if all_candles else 100000

            # OI data — GAP-1: fetch real OI from NSE option chain
            oi_data = _fetch_nse_option_oi(spot)
            oi_call = oi_data["oi_change_call_pct"]
            oi_put = oi_data["oi_change_put_pct"]
            spread_pct = oi_data["spread_pct"]

            signal = momentum_engine.evaluate(
                ind=ind,
                candles=all_candles,
                config=mom_config,
                volume_avg=avg_vol,
                oi_change_call_pct=oi_call,
                oi_change_put_pct=oi_put,
                spread_pct=spread_pct,
                is_option=True,
            )

            # Update regime result with confidence for chop-window override
            if signal.is_filtered:
                metrics_engine.record_filtered(signal.filter_reason)
                paper_engine._add_log("SIGNAL", f"Filtered: {signal.filter_reason}")
                paper_engine.last_signal = {"filtered": True, "reason": signal.filter_reason}
                _time.sleep(SIGNAL_LOOP_SEC)
                continue

            # Regime gate re-check with confidence
            regime_result = regime_engine.classify(
                spot=spot,
                vwap=ind.vwap if ind.vwap > 0 else spot,
                vwap_slope=ind.vwap_slope,
                atr=ind.atr_14 if ind.atr_14 > 0 else spot * 0.001,
                minute_of_day=_minute_of_day(),
                range_last_3=range_3,
                confidence=signal.confidence,
            )

            if not regime_result.is_trade_allowed:
                metrics_engine.record_filtered(f"Regime: {regime_result.no_trade_reason}")
                paper_engine._add_log("SIGNAL", f"Regime blocked: {regime_result.no_trade_reason}")
                _time.sleep(SIGNAL_LOOP_SEC)
                continue

            # Confidence threshold (profile-specific)
            if signal.confidence < profile.confidence_threshold:
                metrics_engine.record_filtered(f"Low confidence ({signal.confidence:.0f} < {profile.confidence_threshold})")
                paper_engine._add_log("SIGNAL", f"Low conf {signal.confidence:.0f}")
                _time.sleep(SIGNAL_LOOP_SEC)
                continue

            # ── Place trade ──
            if not paper_engine.active_trades:
                direction = "CE" if signal.direction == SignalDirection.BULL else "PE"
                atm_strike = round(spot / 50) * 50
                dte = _days_to_expiry()
                sim = PremiumSimulator(spot=spot, strike=atm_strike, option_type=direction,
                                      days_to_expiry=dte, iv=_get_real_iv(direction))
                entry_premium = sim.premium

                # GAP-6: ATR-based dynamic position sizing
                # Risk budget = 2% of capital per trade
                # Lots = risk_budget / (premium_atr * lot_size)
                premium_atr = option_store.premium_atr(side=direction, period=14)
                if premium_atr > 0 and entry_premium > 0:
                    risk_budget = paper_engine.capital * 0.02
                    atr_lots = int(risk_budget / (premium_atr * NIFTY_LOT_SIZE))
                    dynamic_lots = max(1, min(atr_lots, DEFAULT_LOTS * 2))  # Cap at 2x default
                else:
                    dynamic_lots = DEFAULT_LOTS

                # ── Greeks validation data for place_trade ──
                greeks_data = {
                    "delta": sim.greeks.delta,
                    "gamma": sim.greeks.gamma,
                    "theta": sim.greeks.theta,
                    "vega": sim.greeks.vega,
                    "iv": sim.greeks.iv,
                }

                result = paper_engine.place_trade(
                    direction=direction,
                    strike=atm_strike,
                    entry_premium=entry_premium,
                    lots=dynamic_lots,  # GAP-6: ATR-based sizing
                    indicators={
                        "confidence": signal.confidence,
                        "breakout_score": signal.breakout_score,
                        "expansion_score": signal.expansion_score,
                        "participation_score": signal.participation_score,
                        "trend_score": signal.trend_score,
                        "regime": regime_result.regime.value,
                        "reasons": signal.reasons[:5],
                        "greeks": greeks_data,
                        "dynamic_lots": dynamic_lots,
                        "premium_atr": round(premium_atr, 2) if premium_atr else 0,
                    },
                    profile_id=profile.profile_id,
                    regime=regime_result.regime.value,
                    breakout_level=signal.breakout_level,
                    entry_mode=signal.entry_mode.value,
                    greeks=greeks_data,
                )

                paper_engine.last_signal = {
                    "direction": direction,
                    "strike": atm_strike,
                    "entry": entry_premium,
                    "confidence": signal.confidence,
                    "regime": regime_result.regime.value,
                    "profile": profile.profile_id,
                    "time": datetime.now(IST).isoformat(),
                }

                if result["status"] == "placed":
                    paper_engine._add_log("MOMENTUM-ENTRY",
                        f"{direction} {atm_strike} @ ₹{entry_premium:.2f} conf={signal.confidence:.0f} regime={regime_result.regime.value}")
                else:
                    paper_engine._add_log("REJECTED", result.get("reason", ""))
            else:
                paper_engine._add_log("SIGNAL", "Position open — monitoring")

        except Exception as e:
            logger.error(f"Signal loop error: {e}")
            paper_engine._add_log("ERROR", str(e)[:80])

        _time.sleep(SIGNAL_LOOP_SEC)


def _risk_loop():
    """
    Risk Loop (3s):
      1. Update spot / premium via simulator
      2. Maintain MFE / MAE per trade
      3. Update trailing SL
      4. Apply momentum-failure exit rules
      5. Apply kill-switch & cooldown
    """
    logger.info("Risk loop started")
    while True:
        try:
            if not paper_engine.active_trades or not _is_market_open():
                _time.sleep(RISK_LOOP_SEC)
                continue

            spot = get_nifty_spot()
            if not spot:
                _time.sleep(RISK_LOOP_SEC)
                continue

            now = datetime.now(IST)
            # Intraday square-off
            if now.hour >= SQUARE_OFF_HOUR and now.minute >= SQUARE_OFF_MIN:
                for trade in list(paper_engine.active_trades):
                    sim = paper_engine._premium_sims.get(trade["trade_id"])
                    exit_prem = sim.premium if sim else trade["entry_premium"]
                    paper_engine.close_trade(trade["trade_id"], exit_prem, "Intraday Square-off")
                    paper_engine._add_log("SQUAREOFF", f"{trade['direction']} {trade['strike']}")
                continue

            ind = market_store.indicators
            is_late = _minute_of_day() >= 14 * 60

            for trade in list(paper_engine.active_trades):
                trade_id = trade["trade_id"]
                sim = paper_engine._premium_sims.get(trade_id)

                # Update premium via simulator
                if sim:
                    regime_result = regime_engine.classify(
                        spot=spot,
                        vwap=ind.vwap if ind.vwap > 0 else spot,
                        vwap_slope=ind.vwap_slope,
                        atr=ind.atr_14 if ind.atr_14 > 0 else spot * 0.001,
                        minute_of_day=_minute_of_day(),
                    )
                    is_breakout = regime_result.regime in (Regime.OPEN_TREND, Regime.MID_TREND, Regime.LATE_TREND)
                    is_chop = regime_result.regime in (Regime.OPEN_CHOP, Regime.MID_CHOP)

                    current_premium = sim.tick(
                        new_spot=spot,
                        elapsed_seconds=RISK_LOOP_SEC,
                        is_breakout=is_breakout,
                        is_chop=is_chop,
                    )
                else:
                    current_premium = trade["entry_premium"]

                # Check if spot is back inside breakout zone
                bl = trade.get("breakout_level", 0)
                spot_in_bo = False
                if bl > 0:
                    if trade["direction"] == "CE":
                        spot_in_bo = spot < bl
                    else:
                        spot_in_bo = spot > bl

                vwap_recrossed = False
                if ind.vwap > 0:
                    if trade["direction"] == "CE":
                        vwap_recrossed = spot < ind.vwap
                    else:
                        vwap_recrossed = spot > ind.vwap

                # Volume ratio for momentum failure
                all_candles = market_store.get_candles()
                avg_vol = sum(c.volume for c in all_candles) / max(1, len(all_candles)) if all_candles else 100000
                last_vol = all_candles[-1].volume if all_candles else avg_vol
                vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1

                premium_atr = option_store.premium_atr(side=trade["direction"])

                exit_reason = risk_engine.update_tick(
                    trade_id=trade_id,
                    current_price=current_premium,
                    premium_atr=premium_atr,
                    candle_idx=paper_engine._candle_idx,
                    volume_ratio=vol_ratio,
                    spot_in_breakout_zone=spot_in_bo,
                    vwap_recrossed=vwap_recrossed,
                    is_late_session=is_late,
                    is_option=True,
                )

                if exit_reason:
                    paper_engine.close_trade(trade_id, current_premium, exit_reason.value)
                    paper_engine._add_log(f"RISK-EXIT ({exit_reason.value})",
                        f"{trade['direction']} {trade['strike']} @ ₹{current_premium:.2f}")
                else:
                    # Update trade's current state
                    trade["ltp"] = round(current_premium, 2)
                    rs = risk_engine.get_trade_state(trade_id)
                    if rs:
                        trade["sl_premium"] = rs.current_sl
                        trade["mfe"] = round(rs.mfe, 2)
                        trade["mae"] = round(rs.mae, 2)

        except Exception as e:
            logger.error(f"Risk loop error: {e}")

        _time.sleep(RISK_LOOP_SEC)


# ──────────────────────────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "options-scalping-v2", "version": "2.0"}


@app.get("/spot")
async def get_spot_endpoint():
    spot = get_nifty_spot()
    if not spot:
        raise HTTPException(status_code=503, detail="Could not fetch Nifty spot")
    atm = round(spot / 50) * 50
    return {
        "spot": spot,
        "atm_strike": atm,
        "lot_size": NIFTY_LOT_SIZE,
        "timestamp": datetime.now(IST).isoformat(),
    }


@app.get("/regime")
async def get_regime():
    """Current market regime classification."""
    ind = market_store.indicators
    spot = ind.spot or get_nifty_spot() or 0
    if spot <= 0:
        raise HTTPException(status_code=503, detail="No spot data")
    candles = market_store.get_candles(n=3)
    range_3 = 0
    if len(candles) >= 3:
        range_3 = max(c.high for c in candles[-3:]) - min(c.low for c in candles[-3:])
    result = regime_engine.classify(
        spot=spot,
        vwap=ind.vwap if ind.vwap > 0 else spot,
        vwap_slope=ind.vwap_slope,
        atr=ind.atr_14 if ind.atr_14 > 0 else spot * 0.001,
        minute_of_day=_minute_of_day(),
        range_last_3=range_3,
    )
    return RegimeEngine.result_to_dict(result)


@app.get("/signal/momentum")
async def get_momentum_signal():
    """Current momentum signal evaluation."""
    ind = market_store.indicators
    candles = market_store.get_candles()
    if not candles:
        return {"signal": None, "message": "No candle data yet"}
    avg_vol = sum(c.volume for c in candles) / max(1, len(candles))
    signal = momentum_engine.evaluate(
        ind=ind, candles=candles, volume_avg=avg_vol, is_option=True,
    )
    return {
        "direction": signal.direction.value,
        "confidence": signal.confidence,
        "breakout_level": signal.breakout_level,
        "entry_mode": signal.entry_mode.value,
        "scores": {
            "breakout": signal.breakout_score,
            "expansion": signal.expansion_score,
            "participation": signal.participation_score,
            "trend": signal.trend_score,
            "cleanliness": signal.cleanliness_score,
        },
        "is_filtered": signal.is_filtered,
        "filter_reason": signal.filter_reason,
        "reasons": signal.reasons,
    }


@app.get("/risk/status")
async def risk_status():
    """Global risk status (kill switch, cooldown, daily loss)."""
    return risk_engine.get_status()


@app.get("/metrics/daily")
async def daily_metrics():
    """Daily PF, expectancy, capture ratio."""
    today = datetime.now(IST).strftime("%Y-%m-%d")
    report = metrics_engine.generate_daily_report(today)
    from dataclasses import asdict
    return asdict(report)


@app.get("/profiles")
async def get_profiles():
    """Active profiles + parameters."""
    return {"profiles": learning_engine.get_profiles()}


@app.post("/profiles/select")
async def select_profile(profile_id: str):
    """Force a profile for manual testing."""
    if learning_engine.force_profile(profile_id):
        return {"status": "forced", "profile_id": profile_id}
    raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")


@app.get("/learning/bandit")
async def bandit_stats():
    """Profile stats + selection probabilities."""
    return learning_engine.get_bandit_stats()


@app.post("/trade/place")
async def place_trade(req: TradeRequest):
    result = paper_engine.place_trade(
        req.direction, req.strike, req.entry_premium, req.lots,
        user_id=req.user_id,
    )
    return result


@app.post("/trade/close")
async def close_trade(req: TradeCloseRequest):
    result = paper_engine.close_trade(req.trade_id, req.exit_premium)
    return result


@app.get("/portfolio")
async def get_portfolio():
    return paper_engine.get_portfolio()


@app.post("/portfolio/reset")
async def reset_portfolio():
    return paper_engine.reset()


@app.get("/auto-trade/status")
async def auto_trade_status():
    return {
        "enabled": paper_engine.auto_trade_enabled,
        "last_scan": paper_engine.last_scan_time,
        "last_signal": paper_engine.last_signal,
        "active_trades": len(paper_engine.active_trades),
        "day_trade_count": paper_engine.day_trade_count,
        "max_trades_per_day": MAX_TRADES_PER_DAY,
        "log": paper_engine.auto_trade_log[-20:],
        "capital": round(paper_engine.capital, 2),
        "candle_count": market_store.candle_count,
        "timestamp": datetime.now(IST).isoformat(),
    }


@app.post("/auto-trade/toggle")
async def toggle_auto_trade():
    paper_engine.auto_trade_enabled = not paper_engine.auto_trade_enabled
    state = "ENABLED" if paper_engine.auto_trade_enabled else "DISABLED"
    paper_engine._add_log("TOGGLE", f"Auto-trade {state}")
    return {"enabled": paper_engine.auto_trade_enabled}


@app.get("/stats/daily")
async def daily_stats():
    today = datetime.now(IST).strftime("%Y-%m-%d")
    today_trades = [t for t in paper_engine.trade_history if t.get("entry_time", "").startswith(today)]
    return {
        "date": today,
        "trades": len(today_trades),
        "wins": len([t for t in today_trades if t.get("result") == "WIN"]),
        "losses": len([t for t in today_trades if t.get("result") == "LOSS"]),
        "pnl": round(sum(t.get("pnl", 0) for t in today_trades), 2),
        "capital": round(paper_engine.capital, 2),
    }


@app.get("/trailing-sl/status")
async def trailing_sl_status():
    states = {}
    for trade in paper_engine.active_trades:
        tid = trade["trade_id"]
        rs = risk_engine.get_trade_state(tid)
        if rs:
            states[tid] = risk_engine.trade_risk_to_dict(tid)
    return {"trailing_sl_states": states}


@app.get("/iceberg/history")
async def iceberg_history():
    return {"iceberg_orders": paper_engine.iceberg_orders[-20:]}


@app.get("/chain")
async def get_options_chain():
    spot = get_nifty_spot()
    if not spot:
        raise HTTPException(status_code=503, detail="Could not fetch Nifty spot")
    atm = round(spot / 50) * 50
    chain = []
    dte = _days_to_expiry()
    for i in range(-5, 6):
        strike = atm + i * 50
        ce_sim = PremiumSimulator(spot=spot, strike=strike, option_type="CE", days_to_expiry=dte, iv=_get_real_iv("CE"))
        pe_sim = PremiumSimulator(spot=spot, strike=strike, option_type="PE", days_to_expiry=dte, iv=_get_real_iv("PE"))
        chain.append({
            "strike": strike,
            "ce_premium": ce_sim.premium,
            "pe_premium": pe_sim.premium,
            "ce_delta": ce_sim.greeks.delta,
            "pe_delta": pe_sim.greeks.delta,
            "ce_iv": ce_sim.greeks.iv,
            "pe_iv": pe_sim.greeks.iv,
            "ce_theta": ce_sim.greeks.theta,
            "pe_theta": pe_sim.greeks.theta,
            "is_atm": strike == atm,
        })
    return {
        "spot": spot, "atm": atm, "chain": chain,
        "expiry": _get_next_thursday(),
        "lot_size": NIFTY_LOT_SIZE,
        "timestamp": datetime.now(IST).isoformat(),
    }


@app.get("/premium/sim")
async def premium_sim_status():
    """Return premium simulator state for active trades."""
    result = {}
    for trade in paper_engine.active_trades:
        sim = paper_engine._premium_sims.get(trade["trade_id"])
        if sim:
            result[trade["trade_id"]] = sim.to_dict()
    return result


@app.get("/diagnostics")
async def diagnostics():
    """Comprehensive diagnostics endpoint for monitoring and debugging.
    Shows cooldown state, per-strike limits, data source health, filter stats.
    """
    now = datetime.now(IST)

    # Cooldown state
    cooldown_active = False
    cooldown_remaining = 0
    if paper_engine._last_loss_time > 0:
        elapsed = _time.time() - paper_engine._last_loss_time
        cooldown = CONSEC_LOSS_COOLDOWN_SEC if paper_engine._consecutive_losses >= 2 else LOSS_COOLDOWN_SEC
        if elapsed < cooldown:
            cooldown_active = True
            cooldown_remaining = int(cooldown - elapsed)

    # Data source health
    oi_source = _oi_cache.get("data", {}).get("source", "none")
    oi_age = int(_time.time() - _oi_cache.get("timestamp", 0))
    spot_source = "market_data_service" if _last_spot_data.get("ltp") else "google_finance"

    # Filter statistics from metrics engine
    filter_stats = {}
    if hasattr(metrics_engine, '_filtered_reasons'):
        filter_stats = dict(metrics_engine._filtered_reasons)

    # Risk engine state
    risk_status_data = risk_engine.get_status()

    return {
        "timestamp": now.isoformat(),
        "cooldown": {
            "active": cooldown_active,
            "remaining_sec": cooldown_remaining,
            "consecutive_losses": paper_engine._consecutive_losses,
            "last_loss_epoch": paper_engine._last_loss_time,
        },
        "per_strike_entries": paper_engine._daily_strike_entries,
        "day_trade_count": paper_engine.day_trade_count,
        "max_trades_per_day": MAX_TRADES_PER_DAY,
        "data_sources": {
            "spot_source": spot_source,
            "oi_source": oi_source,
            "oi_cache_age_sec": oi_age,
            "iv_cache": {
                "ce_iv": _iv_cache.get("ce_iv", 15.0),
                "pe_iv": _iv_cache.get("pe_iv", 15.0),
            },
        },
        "market_state": {
            "is_market_open": _is_market_open(),
            "candle_count": market_store.candle_count,
            "minute_of_day": _minute_of_day(),
        },
        "risk_engine": risk_status_data,
        "filter_stats": filter_stats,
        "capital": round(paper_engine.capital, 2),
        "daily_pnl": round(paper_engine.daily_pnl, 2),
        "active_trades": len(paper_engine.active_trades),
    }


# ──────────────────────────────────────────────────────────────────
# Startup — launch two-loop runtime
# ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def start_loops():
    threading.Thread(target=_signal_loop, daemon=True, name="signal-loop").start()
    threading.Thread(target=_risk_loop, daemon=True, name="risk-loop").start()
    logger.info("Two-loop runtime started (signal=30s, risk=3s)")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
