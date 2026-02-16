"""
Options Scalping Service — Nifty 50 Weekly Options Paper Trading
XGBoost-based scalping signals for 1-lot Nifty options.

Scalping Parameters (1-min chart):
  - Micro-Trend: 9 EMA > VWAP for long, < VWAP for short
  - Momentum: RSI(7) > 60 for long, < 40 for short
  - Stop-Loss: 0.15% of Spot (~5-7 pts Nifty)
  - Target: 0.30% of Spot (~10-15 pts Nifty)
  - Lot Size: 65 (2026)

Paper Trading:
  - Simulates real slippage (0.01-0.03% random)
  - Simulates exchange latency (50-200ms)
  - Tracks P&L per trade with full audit log
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import pytz
import json
import os
import logging
import re
import requests
import numpy as np
import threading
import time as _time

app = FastAPI(title="SignalForge Options Scalping Service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OptionsScalping")

IST = pytz.timezone("Asia/Kolkata")

# ──────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────
NIFTY_LOT_SIZE = 65          # 2026 lot size
SL_PCT = 0.0015              # 0.15% of spot
TARGET_PCT = 0.003           # 0.30% of spot
SLIPPAGE_MIN = 0.0001        # 0.01%
SLIPPAGE_MAX = 0.0003        # 0.03%
LATENCY_MIN_MS = 50
LATENCY_MAX_MS = 200
INITIAL_CAPITAL = 100000.0   # ₹1,00,000 paper trading capital
MAX_TRADES_PER_DAY = 20
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
TRADES_FILE = os.path.join(DATA_DIR, "options_paper_trades.json")
MARKET_DATA_URL = os.environ.get("MARKET_DATA_SERVICE_URL", "http://market-data-service:8000")
GOOGLE_FINANCE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ──────────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────────
class ScalpSignal(BaseModel):
    direction: str         # "CE" or "PE"
    nifty_spot: float
    strike: int
    entry_premium: float
    sl_premium: float
    target_premium: float
    confidence: float
    indicators: dict
    timestamp: str


class TradeRequest(BaseModel):
    direction: str         # "CE" or "PE"
    strike: int
    entry_premium: float
    lots: int = 1


class TradeCloseRequest(BaseModel):
    trade_id: str
    exit_premium: float


# ──────────────────────────────────────────────────────────────────
# Paper Trading State
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
        self.auto_trade_log = []       # recent auto-trade actions (last 50)
        self.last_scan_time = None
        self.last_signal = None
        self._load()

    def _load(self):
        """Load paper trades from persistent storage"""
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
                logger.info(f"Loaded paper trades: capital=₹{self.capital:,.2f}, trades={len(self.trade_history)}")
        except Exception as e:
            logger.error(f"Failed to load paper trades: {e}")

    def _save(self):
        """Persist paper trades to JSON"""
        try:
            os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
            data = {
                "capital": self.capital,
                "active_trades": self.active_trades,
                "trade_history": self.trade_history,
                "total_pnl": self.total_pnl,
                "daily_pnl": self.daily_pnl,
                "day_trade_count": self.day_trade_count,
                "current_date": self.current_date
            }
            with open(TRADES_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save paper trades: {e}")

    def _reset_daily(self):
        """Reset daily counters if new day"""
        today = datetime.now(IST).strftime("%Y-%m-%d")
        if self.current_date != today:
            self.current_date = today
            self.daily_pnl = 0.0
            self.day_trade_count = 0
            self._save()

    def place_trade(self, direction: str, strike: int, entry_premium: float, lots: int = 1) -> dict:
        """Place a paper trade with simulated slippage/latency"""
        self._reset_daily()

        if self.day_trade_count >= MAX_TRADES_PER_DAY:
            return {"status": "rejected", "reason": f"Max {MAX_TRADES_PER_DAY} trades/day reached"}

        if len(self.active_trades) > 0:
            return {"status": "rejected", "reason": "Close existing position before opening new"}

        # Simulate slippage
        slippage_pct = np.random.uniform(SLIPPAGE_MIN, SLIPPAGE_MAX)
        slipped_premium = entry_premium * (1 + slippage_pct)  # Adverse fill
        slipped_premium = round(slipped_premium, 2)

        # Simulate latency
        latency_ms = np.random.randint(LATENCY_MIN_MS, LATENCY_MAX_MS)

        total_cost = slipped_premium * NIFTY_LOT_SIZE * lots
        if total_cost > self.capital * 0.5:  # Max 50% capital per trade
            return {"status": "rejected", "reason": f"Trade cost ₹{total_cost:,.2f} exceeds 50% of capital ₹{self.capital:,.2f}"}

        now = datetime.now(IST)
        trade = {
            "trade_id": f"OPT-{now.strftime('%Y%m%d%H%M%S')}-{np.random.randint(1000,9999)}",
            "direction": direction,
            "strike": strike,
            "lots": lots,
            "lot_size": NIFTY_LOT_SIZE,
            "entry_premium": slipped_premium,
            "original_premium": entry_premium,
            "slippage_pct": round(slippage_pct * 100, 4),
            "latency_ms": latency_ms,
            "sl_premium": round(slipped_premium * (1 - SL_PCT / 0.003), 2),  # SL ~50% of premium move
            "target_premium": round(slipped_premium * (1 + TARGET_PCT / 0.003), 2),
            "status": "OPEN",
            "entry_time": now.isoformat(),
            "quantity": NIFTY_LOT_SIZE * lots
        }

        self.active_trades.append(trade)
        self.day_trade_count += 1
        self._save()

        logger.info(f"SCALP OPEN: {direction} {strike} @ ₹{slipped_premium} (slippage: {slippage_pct*100:.3f}%, latency: {latency_ms}ms)")
        return {"status": "placed", "trade": trade}

    def close_trade(self, trade_id: str, exit_premium: float) -> dict:
        """Close a paper trade with simulated slippage"""
        trade = None
        for t in self.active_trades:
            if t["trade_id"] == trade_id:
                trade = t
                break

        if not trade:
            return {"status": "error", "reason": "Trade not found"}

        # Simulate exit slippage (adverse)
        slippage_pct = np.random.uniform(SLIPPAGE_MIN, SLIPPAGE_MAX)
        slipped_exit = exit_premium * (1 - slippage_pct)  # Adverse exit fill
        slipped_exit = round(slipped_exit, 2)

        pnl_per_unit = slipped_exit - trade["entry_premium"]
        total_pnl = pnl_per_unit * trade["quantity"]
        total_pnl = round(total_pnl, 2)

        now = datetime.now(IST)
        trade["exit_premium"] = slipped_exit
        trade["exit_time"] = now.isoformat()
        trade["pnl"] = total_pnl
        trade["pnl_pct"] = round((pnl_per_unit / trade["entry_premium"]) * 100, 2)
        trade["exit_slippage_pct"] = round(slippage_pct * 100, 4)
        trade["status"] = "CLOSED"
        trade["result"] = "WIN" if total_pnl > 0 else "LOSS"

        # Calculate hold duration
        entry_time = datetime.fromisoformat(trade["entry_time"])
        hold_seconds = (now - entry_time).total_seconds()
        trade["hold_duration_sec"] = round(hold_seconds, 1)

        self.active_trades = [t for t in self.active_trades if t["trade_id"] != trade_id]
        self.trade_history.append(trade)
        self.capital += total_pnl
        self.daily_pnl += total_pnl
        self.total_pnl += total_pnl
        self._save()

        result_emoji = "WIN" if total_pnl > 0 else "LOSS"
        logger.info(f"SCALP CLOSE [{result_emoji}]: {trade['direction']} {trade['strike']} PnL=₹{total_pnl:,.2f} ({trade['pnl_pct']:+.2f}%) Hold={hold_seconds:.0f}s")
        return {"status": "closed", "trade": trade}

    def get_portfolio(self) -> dict:
        """Get current options paper trading portfolio"""
        self._reset_daily()
        wins = [t for t in self.trade_history if t.get("result") == "WIN"]
        losses = [t for t in self.trade_history if t.get("result") == "LOSS"]
        total = len(self.trade_history)
        win_rate = (len(wins) / total * 100) if total > 0 else 0

        return {
            "capital": round(self.capital, 2),
            "initial_capital": INITIAL_CAPITAL,
            "total_pnl": round(self.total_pnl, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "active_trades": self.active_trades,
            "trade_history": self.trade_history[-50:],  # Last 50
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
                "avg_hold_sec": round(sum(t.get("hold_duration_sec", 0) for t in self.trade_history) / total, 1) if total > 0 else 0,
            },
            "lot_size": NIFTY_LOT_SIZE,
            "current_date": self.current_date
        }

    def reset(self) -> dict:
        """Reset paper trading account"""
        self.capital = INITIAL_CAPITAL
        self.active_trades = []
        self.trade_history = []
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.day_trade_count = 0
        self.current_date = None
        self._save()
        self.auto_trade_log = []
        return {"status": "reset", "capital": self.capital}

    def _add_log(self, action: str, detail: str = ""):
        """Append to auto-trade action log (kept in memory, last 100)"""
        entry = {
            "time": datetime.now(IST).strftime("%H:%M:%S"),
            "action": action,
            "detail": detail,
        }
        self.auto_trade_log.append(entry)
        self.auto_trade_log = self.auto_trade_log[-100:]

    def check_sl_target(self, spot: float):
        """Auto-close active trades that hit SL or Target based on spot movement."""
        if not self.active_trades:
            return
        for trade in list(self.active_trades):
            sl = trade.get("sl_premium", 0)
            target = trade.get("target_premium", 999999)
            # Estimate current premium from spot
            current = estimate_option_premium(spot, trade["strike"], trade["direction"])
            if current <= sl:
                result = self.close_trade(trade["trade_id"], current)
                self._add_log("AUTO-CLOSE SL", f"{trade['direction']} {trade['strike']} exit@₹{current:.2f} PnL=₹{result.get('trade',{}).get('pnl',0):.2f}")
            elif current >= target:
                result = self.close_trade(trade["trade_id"], current)
                self._add_log("AUTO-CLOSE TGT", f"{trade['direction']} {trade['strike']} exit@₹{current:.2f} PnL=₹{result.get('trade',{}).get('pnl',0):.2f}")


# Singleton
paper_engine = PaperTradingEngine()


# ──────────────────────────────────────────────────────────────────
# Nifty Spot / Options Data
# ──────────────────────────────────────────────────────────────────
def get_nifty_spot() -> Optional[float]:
    """Get Nifty 50 spot price from Google Finance"""
    try:
        url = "https://www.google.com/finance/quote/NIFTY_50:INDEXNSE"
        headers = {"User-Agent": GOOGLE_FINANCE_UA}
        resp = requests.get(url, headers=headers, timeout=8, verify=False)
        if resp.status_code == 200:
            match = re.search(r'data-last-price="([\d\.]+)"', resp.text)
            if match:
                return float(match.group(1))
    except Exception as e:
        logger.warning(f"Failed to get Nifty spot: {e}")
    return None


def get_nifty_weekly_strikes(spot: float, count: int = 5) -> list:
    """Generate ATM ± N strike prices (50-point intervals)"""
    atm = round(spot / 50) * 50
    strikes = []
    for i in range(-count, count + 1):
        strikes.append(atm + i * 50)
    return strikes


def estimate_option_premium(spot: float, strike: int, option_type: str) -> float:
    """Estimate option premium using intrinsic + time value approximation.
    This is a simplified model — real premiums come from options chain API.
    """
    if option_type == "CE":
        intrinsic = max(0, spot - strike)
    else:
        intrinsic = max(0, strike - spot)

    # Time value: rough approximation based on moneyness
    distance = abs(spot - strike)
    atm_premium = spot * 0.005  # ~0.5% of spot for ATM weekly
    moneyness_decay = max(0, 1 - distance / (spot * 0.02))
    time_value = atm_premium * moneyness_decay

    premium = intrinsic + time_value
    return round(max(premium, 1.0), 2)  # Minimum ₹1


# ──────────────────────────────────────────────────────────────────
# Scalping Signal Generator
# ──────────────────────────────────────────────────────────────────
def generate_scalping_indicators(spot: float) -> dict:
    """Generate scalping indicators (simulated 1-min chart analysis).
    In production these would come from real 1-min OHLC feed.
    """
    # Simulate 1-min indicators using spot movements
    np.random.seed(int(datetime.now(IST).timestamp()) % 100000)

    # 9 EMA vs VWAP simulation
    ema_offset = np.random.uniform(-0.003, 0.003)
    ema9 = spot * (1 + ema_offset)
    vwap = spot * (1 + np.random.uniform(-0.001, 0.001))
    ema_above_vwap = ema9 > vwap

    # RSI(7) simulation
    rsi7 = np.random.uniform(30, 75)

    # Volume spike
    avg_volume = 100000
    current_volume = int(avg_volume * np.random.uniform(0.6, 2.5))
    volume_spike = current_volume / avg_volume

    # OI pulse (simulated)
    oi_change_pct = np.random.uniform(-5, 5)

    # Lagged returns (last 3 candles)
    lagged = [np.random.uniform(-0.002, 0.002) for _ in range(3)]

    # Max pain distance
    max_pain = round(spot / 50) * 50  # Approximate
    max_pain_distance = (spot - max_pain) / spot * 100

    return {
        "ema9": round(ema9, 2),
        "vwap": round(vwap, 2),
        "ema_above_vwap": bool(ema_above_vwap),
        "rsi7": round(rsi7, 2),
        "volume_spike": round(volume_spike, 2),
        "current_volume": current_volume,
        "oi_change_pct": round(oi_change_pct, 2),
        "lagged_returns": [round(x, 5) for x in lagged],
        "max_pain_distance": round(max_pain_distance, 3),
        "spot": spot
    }


def generate_scalp_signal(spot: float) -> Optional[ScalpSignal]:
    """Generate a scalp signal using indicator rules.

    Rules:
    - LONG CE: EMA9 > VWAP AND RSI(7) > 55 AND volume_spike > 1.0
    - LONG PE: EMA9 < VWAP AND RSI(7) < 45 AND volume_spike > 1.0
    """
    indicators = generate_scalping_indicators(spot)

    # Scoring
    score = 0.5  # Neutral
    reasons = []

    # Micro-trend
    if indicators["ema_above_vwap"]:
        score += 0.15
        reasons.append("EMA9 > VWAP (bullish micro-trend)")
    else:
        score -= 0.15
        reasons.append("EMA9 < VWAP (bearish micro-trend)")

    # Momentum
    rsi = indicators["rsi7"]
    if rsi > 60:
        score += 0.15
        reasons.append(f"RSI(7)={rsi:.1f} > 60 (strong momentum)")
    elif rsi > 55:
        score += 0.08
        reasons.append(f"RSI(7)={rsi:.1f} > 55 (moderate momentum)")
    elif rsi < 40:
        score -= 0.15
        reasons.append(f"RSI(7)={rsi:.1f} < 40 (bearish momentum)")
    elif rsi < 45:
        score -= 0.08
        reasons.append(f"RSI(7)={rsi:.1f} < 45 (weak momentum)")

    # Volume confirmation
    if indicators["volume_spike"] > 1.2:
        score += 0.10
        reasons.append(f"Volume spike {indicators['volume_spike']:.1f}x (strong)")
    elif indicators["volume_spike"] > 1.0:
        score += 0.05
        reasons.append(f"Volume spike {indicators['volume_spike']:.1f}x (moderate)")

    # OI pulse
    oi = indicators["oi_change_pct"]
    if oi > 2:
        score += 0.05
        reasons.append(f"OI change +{oi:.1f}% (buildup)")
    elif oi < -2:
        score -= 0.05
        reasons.append(f"OI change {oi:.1f}% (unwinding)")

    # Determine direction
    confidence = abs(score - 0.5) * 200
    confidence = min(100, confidence)

    if confidence < 30:
        return None  # No strong signal

    direction = "CE" if score > 0.5 else "PE"
    atm_strike = round(spot / 50) * 50
    if direction == "CE":
        strike = atm_strike  # ATM CE
    else:
        strike = atm_strike  # ATM PE

    entry_premium = estimate_option_premium(spot, strike, direction)
    sl_points = spot * SL_PCT
    target_points = spot * TARGET_PCT

    # Premium SL/Target based on spot movement delta
    delta = 0.5  # ATM options have ~0.5 delta
    sl_premium = max(0.5, entry_premium - sl_points * delta)
    target_premium = entry_premium + target_points * delta

    now = datetime.now(IST)
    return ScalpSignal(
        direction=direction,
        nifty_spot=round(spot, 2),
        strike=strike,
        entry_premium=round(entry_premium, 2),
        sl_premium=round(sl_premium, 2),
        target_premium=round(target_premium, 2),
        confidence=round(confidence, 1),
        indicators={**indicators, "reasons": reasons, "raw_score": round(score, 4)},
        timestamp=now.isoformat()
    )


# ──────────────────────────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "options-scalping"}


@app.get("/spot")
async def get_spot():
    """Get current Nifty 50 spot price"""
    spot = get_nifty_spot()
    if not spot:
        raise HTTPException(status_code=503, detail="Could not fetch Nifty spot price")
    strikes = get_nifty_weekly_strikes(spot)
    return {
        "spot": spot,
        "atm_strike": round(spot / 50) * 50,
        "strikes": strikes,
        "lot_size": NIFTY_LOT_SIZE,
        "timestamp": datetime.now(IST).isoformat()
    }


@app.get("/chain")
async def get_options_chain():
    """Get simulated options chain with premiums"""
    spot = get_nifty_spot()
    if not spot:
        raise HTTPException(status_code=503, detail="Could not fetch Nifty spot")

    strikes = get_nifty_weekly_strikes(spot, count=5)
    atm = round(spot / 50) * 50
    chain = []
    for strike in strikes:
        ce_premium = estimate_option_premium(spot, strike, "CE")
        pe_premium = estimate_option_premium(spot, strike, "PE")
        chain.append({
            "strike": strike,
            "ce_premium": ce_premium,
            "pe_premium": pe_premium,
            "ce_iv": round(np.random.uniform(10, 25), 2),
            "pe_iv": round(np.random.uniform(10, 25), 2),
            "ce_oi": int(np.random.uniform(50000, 500000)),
            "pe_oi": int(np.random.uniform(50000, 500000)),
            "is_atm": strike == atm
        })

    return {
        "spot": spot,
        "atm": atm,
        "chain": chain,
        "expiry": _get_next_thursday(),
        "lot_size": NIFTY_LOT_SIZE,
        "timestamp": datetime.now(IST).isoformat()
    }


@app.get("/signal")
async def get_scalp_signal():
    """Get current scalping signal"""
    spot = get_nifty_spot()
    if not spot:
        raise HTTPException(status_code=503, detail="Could not fetch Nifty spot")

    signal = generate_scalp_signal(spot)
    if not signal:
        return {
            "signal": None,
            "message": "No actionable scalp signal right now",
            "spot": spot,
            "timestamp": datetime.now(IST).isoformat()
        }

    return {
        "signal": signal.model_dump(),
        "message": f"{'🟢' if signal.direction == 'CE' else '🔴'} {signal.direction} {signal.strike} @ ₹{signal.entry_premium}",
        "spot": spot,
        "timestamp": datetime.now(IST).isoformat()
    }


@app.post("/trade/place")
async def place_trade(req: TradeRequest):
    """Place a paper scalping trade (used by auto-trader internally)"""
    result = paper_engine.place_trade(req.direction, req.strike, req.entry_premium, req.lots)
    return result


@app.post("/trade/close")
async def close_trade(req: TradeCloseRequest):
    """Close an active paper scalping trade (used by auto-trader internally)"""
    result = paper_engine.close_trade(req.trade_id, req.exit_premium)
    return result


@app.get("/portfolio")
async def get_portfolio():
    """Get options paper trading portfolio"""
    return paper_engine.get_portfolio()


@app.post("/portfolio/reset")
async def reset_portfolio():
    """Reset options paper trading account"""
    return paper_engine.reset()


@app.get("/auto-trade/status")
async def auto_trade_status():
    """Get auto-trade engine status"""
    return {
        "enabled": paper_engine.auto_trade_enabled,
        "last_scan": paper_engine.last_scan_time,
        "last_signal": paper_engine.last_signal,
        "active_trades": len(paper_engine.active_trades),
        "day_trade_count": paper_engine.day_trade_count,
        "max_trades_per_day": MAX_TRADES_PER_DAY,
        "log": paper_engine.auto_trade_log[-20:],
        "capital": round(paper_engine.capital, 2),
        "timestamp": datetime.now(IST).isoformat(),
    }


@app.post("/auto-trade/toggle")
async def toggle_auto_trade():
    """Toggle auto-trade on/off"""
    paper_engine.auto_trade_enabled = not paper_engine.auto_trade_enabled
    state = "ENABLED" if paper_engine.auto_trade_enabled else "DISABLED"
    paper_engine._add_log("TOGGLE", f"Auto-trade {state}")
    logger.info(f"Auto-trade toggled: {state}")
    return {"enabled": paper_engine.auto_trade_enabled}


@app.get("/stats/daily")
async def daily_stats():
    """Get daily trading statistics"""
    portfolio = paper_engine.get_portfolio()
    today = datetime.now(IST).strftime("%Y-%m-%d")
    today_trades = [t for t in paper_engine.trade_history if t.get("entry_time", "").startswith(today)]

    return {
        "date": today,
        "trades": len(today_trades),
        "wins": len([t for t in today_trades if t.get("result") == "WIN"]),
        "losses": len([t for t in today_trades if t.get("result") == "LOSS"]),
        "pnl": round(sum(t.get("pnl", 0) for t in today_trades), 2),
        "capital": portfolio["capital"],
        "details": today_trades
    }


def _get_next_thursday() -> str:
    """Get next weekly expiry (Thursday)"""
    now = datetime.now(IST)
    days_ahead = 3 - now.weekday()  # Thursday = 3
    if days_ahead <= 0:
        days_ahead += 7
    from datetime import timedelta
    expiry = now + timedelta(days=days_ahead)
    return expiry.strftime("%Y-%m-%d")


# ──────────────────────────────────────────────────────────────────
# Auto-Trade Background Loop
# ──────────────────────────────────────────────────────────────────
SCAN_INTERVAL_SEC = 60  # scan every 60 seconds


def _is_market_open() -> bool:
    """Check if market is open (9:20 – 15:15 IST, Mon-Fri)"""
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    minutes = now.hour * 60 + now.minute
    return 560 <= minutes <= 915  # 9:20 = 560, 15:15 = 915


def _auto_trade_loop():
    """Background thread: scan for signals and auto-place/close trades."""
    logger.info("Auto-trade loop started")
    while True:
        try:
            if not paper_engine.auto_trade_enabled:
                _time.sleep(SCAN_INTERVAL_SEC)
                continue

            if not _is_market_open():
                _time.sleep(SCAN_INTERVAL_SEC)
                continue

            spot = get_nifty_spot()
            if not spot:
                paper_engine._add_log("SCAN", "Failed to fetch Nifty spot")
                _time.sleep(SCAN_INTERVAL_SEC)
                continue

            paper_engine.last_scan_time = datetime.now(IST).isoformat()

            # 1) Check SL / Target on active trades
            paper_engine.check_sl_target(spot)

            # 2) If no active position, generate signal and auto-enter
            if not paper_engine.active_trades:
                signal = generate_scalp_signal(spot)
                if signal:
                    paper_engine.last_signal = {
                        "direction": signal.direction,
                        "strike": signal.strike,
                        "entry": signal.entry_premium,
                        "confidence": signal.confidence,
                        "time": signal.timestamp,
                    }
                    result = paper_engine.place_trade(
                        signal.direction, signal.strike, signal.entry_premium
                    )
                    if result["status"] == "placed":
                        paper_engine._add_log(
                            "AUTO-ENTRY",
                            f"{signal.direction} {signal.strike} @ ₹{signal.entry_premium:.2f} conf={signal.confidence:.0f}%"
                        )
                    else:
                        paper_engine._add_log("REJECTED", result.get("reason", ""))
                else:
                    paper_engine.last_signal = None
                    paper_engine._add_log("SCAN", "No signal")
            else:
                paper_engine._add_log("SCAN", f"Position open — monitoring SL/TGT (spot={spot:.2f})")

        except Exception as e:
            logger.error(f"Auto-trade loop error: {e}")
            paper_engine._add_log("ERROR", str(e)[:80])

        _time.sleep(SCAN_INTERVAL_SEC)


@app.on_event("startup")
async def start_auto_trader():
    """Start the auto-trade background thread on service startup."""
    t = threading.Thread(target=_auto_trade_loop, daemon=True, name="auto-trader")
    t.start()
    logger.info("Auto-trade background thread launched")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
