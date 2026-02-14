"""
Chart Analysis Service
======================
Monitors OHLC chart data and produces technical signals based on:
  1. Candlestick pattern recognition (Doji, Engulfing, Stars, etc.)
  2. Multi-indicator technical analysis (RSI, MACD, Bollinger, VWAP, ADX)
  3. Support / Resistance level detection
  4. Composite scoring → actionable chart-based signal

Fetches OHLC data from market-data-service and provides endpoints
that the recommendation engine or intraday agent can call.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

from patterns import detect_patterns, compute_support_resistance

# ─── Configuration ───────────────────────────────────────────────
MARKET_DATA_URL = os.getenv("MARKET_DATA_URL", "http://market-data-service:8000")

app = FastAPI(title="Chart Analysis Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ─── Technical Indicator Calculations ────────────────────────────

def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_macd(series: pd.Series) -> Dict:
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd": round(float(macd_line.iloc[-1]), 4),
        "signal": round(float(signal_line.iloc[-1]), 4),
        "histogram": round(float(histogram.iloc[-1]), 4),
        "crossover": "bullish" if histogram.iloc[-1] > 0 and histogram.iloc[-2] <= 0 else
                     "bearish" if histogram.iloc[-1] < 0 and histogram.iloc[-2] >= 0 else "none"
    }


def compute_bollinger(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict:
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    current = float(series.iloc[-1])
    bandwidth = float((upper.iloc[-1] - lower.iloc[-1]) / sma.iloc[-1] * 100)
    pct_b = float((current - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1]))
    return {
        "upper": round(float(upper.iloc[-1]), 2),
        "middle": round(float(sma.iloc[-1]), 2),
        "lower": round(float(lower.iloc[-1]), 2),
        "bandwidth": round(bandwidth, 2),
        "percent_b": round(pct_b, 4),
        "position": "above_upper" if current > float(upper.iloc[-1]) else
                    "below_lower" if current < float(lower.iloc[-1]) else "within"
    }


def compute_vwap(df: pd.DataFrame) -> float:
    """Volume-Weighted Average Price."""
    if "volume" not in df.columns or df["volume"].sum() == 0:
        return float(df["close"].iloc[-1])
    tp = (df["high"] + df["low"] + df["close"]) / 3
    return float((tp * df["volume"]).sum() / df["volume"].sum())


def compute_adx(df: pd.DataFrame, period: int = 14) -> Dict:
    """Average Directional Index for trend strength."""
    if len(df) < period * 2:
        return {"adx": 0, "plus_di": 0, "minus_di": 0, "trend_strength": "weak"}

    h, l, c = df["high"], df["low"], df["close"]
    plus_dm = h.diff()
    minus_dm = -l.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(window=period).mean()

    adx_val = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0
    strength = "strong" if adx_val > 25 else "moderate" if adx_val > 20 else "weak"

    return {
        "adx": round(adx_val, 2),
        "plus_di": round(float(plus_di.iloc[-1]), 2) if not pd.isna(plus_di.iloc[-1]) else 0,
        "minus_di": round(float(minus_di.iloc[-1]), 2) if not pd.isna(minus_di.iloc[-1]) else 0,
        "trend_strength": strength
    }


def compute_ema(series: pd.Series, span: int) -> float:
    return float(series.ewm(span=span, adjust=False).mean().iloc[-1])


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs()
    ], axis=1).max(axis=1)
    return float(tr.rolling(window=period).mean().iloc[-1])


# ─── Composite Signal Scoring ────────────────────────────────────

def compute_chart_signal(df: pd.DataFrame) -> Dict:
    """
    Aggregate all technical analysis into a single composite signal.
    Returns signal: STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
    with a numeric score 0-100 and breakdown.
    """
    close = df["close"]
    current_price = float(close.iloc[-1])
    scores = {}

    # 1. RSI Score (0-100 → mapped to -1 to +1)
    rsi = compute_rsi(close)
    rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
    if rsi_val < 30:
        rsi_score = 0.7  # Oversold = bullish opportunity
    elif rsi_val < 40:
        rsi_score = 0.3
    elif rsi_val > 70:
        rsi_score = -0.7  # Overbought = bearish
    elif rsi_val > 60:
        rsi_score = -0.3
    else:
        rsi_score = 0.0
    scores["rsi"] = {"value": round(rsi_val, 2), "score": rsi_score}

    # 2. MACD Score
    macd = compute_macd(close)
    if macd["crossover"] == "bullish":
        macd_score = 0.8
    elif macd["crossover"] == "bearish":
        macd_score = -0.8
    elif macd["histogram"] > 0:
        macd_score = 0.3
    elif macd["histogram"] < 0:
        macd_score = -0.3
    else:
        macd_score = 0.0
    scores["macd"] = {**macd, "score": macd_score}

    # 3. Bollinger Band Score
    bb = compute_bollinger(close)
    if bb["position"] == "below_lower":
        bb_score = 0.6  # Oversold / reversal
    elif bb["position"] == "above_upper":
        bb_score = -0.6  # Overbought
    else:
        bb_score = (0.5 - bb["percent_b"]) * 0.4  # slight mean-reversion tendency
    scores["bollinger"] = {**bb, "score": round(bb_score, 4)}

    # 4. VWAP Score
    vwap = compute_vwap(df)
    vwap_diff = (current_price - vwap) / vwap * 100
    if vwap_diff > 1:
        vwap_score = -0.3  # Above VWAP = potentially stretched
    elif vwap_diff < -1:
        vwap_score = 0.3  # Below VWAP = value
    else:
        vwap_score = 0.0
    scores["vwap"] = {"value": round(vwap, 2), "diff_pct": round(vwap_diff, 2), "score": vwap_score}

    # 5. ADX / Trend Score
    adx = compute_adx(df)
    if adx["trend_strength"] == "strong":
        # Strong trend — go with +DI/-DI direction
        trend_score = 0.5 if adx["plus_di"] > adx["minus_di"] else -0.5
    else:
        trend_score = 0.0  # No strong trend
    scores["adx"] = {**adx, "score": trend_score}

    # 6. Moving Average Score (EMA 9 vs 21 vs 50)
    ema9 = compute_ema(close, 9)
    ema21 = compute_ema(close, 21)
    ema50 = compute_ema(close, 50) if len(close) >= 50 else ema21
    if ema9 > ema21 > ema50:
        ma_score = 0.7  # Bullish alignment
    elif ema9 < ema21 < ema50:
        ma_score = -0.7  # Bearish alignment
    elif ema9 > ema21:
        ma_score = 0.3
    elif ema9 < ema21:
        ma_score = -0.3
    else:
        ma_score = 0.0
    scores["moving_averages"] = {
        "ema9": round(ema9, 2), "ema21": round(ema21, 2),
        "ema50": round(ema50, 2), "score": ma_score
    }

    # 7. Pattern Score
    patterns = detect_patterns(df)
    pattern_score = 0.0
    for p in patterns:
        if p["type"] == "bullish":
            pattern_score += p["strength"] * 0.3
        elif p["type"] == "bearish":
            pattern_score -= p["strength"] * 0.3
    pattern_score = max(-1, min(1, pattern_score))
    scores["patterns"] = {"detected": patterns, "score": round(pattern_score, 4)}

    # 8. Support / Resistance
    sr = compute_support_resistance(df)
    scores["support_resistance"] = sr

    # ─── Weighted composite ──────────────────────────────────────
    weights = {
        "rsi": 0.15,
        "macd": 0.20,
        "bollinger": 0.10,
        "vwap": 0.10,
        "adx": 0.10,
        "moving_averages": 0.20,
        "patterns": 0.15,
    }

    composite = sum(scores[k]["score"] * weights[k] for k in weights)

    # Scale composite (-1..+1) → signal score (0..100)
    signal_score = round((composite + 1) * 50, 2)

    # Determine signal label
    if signal_score >= 70:
        signal = "STRONG_BUY"
    elif signal_score >= 58:
        signal = "BUY"
    elif signal_score <= 30:
        signal = "STRONG_SELL"
    elif signal_score <= 42:
        signal = "SELL"
    else:
        signal = "NEUTRAL"

    # ATR for volatility context
    atr = compute_atr(df)

    return {
        "symbol": "",
        "signal": signal,
        "score": signal_score,
        "composite_raw": round(composite, 4),
        "current_price": current_price,
        "atr": round(atr, 2),
        "breakdown": scores,
        "analyzed_at": datetime.utcnow().isoformat()
    }


# ─── Data Fetching ───────────────────────────────────────────────

async def fetch_ohlc(symbol: str, interval: str = "1d", limit: int = 100) -> Optional[pd.DataFrame]:
    """Fetch OHLC data from market-data-service."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{MARKET_DATA_URL}/ohlc/{symbol}",
                params={"interval": interval, "limit": limit}
            )
            if resp.status_code == 200:
                data = resp.json()
                # Handle different response formats
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                elif isinstance(data, dict) and "data" in data:
                    df = pd.DataFrame(data["data"])
                elif isinstance(data, dict) and "candles" in data:
                    df = pd.DataFrame(data["candles"])
                else:
                    return None

                # Normalize column names
                col_map = {}
                for col in df.columns:
                    cl = col.lower()
                    if cl in ("open", "high", "low", "close", "volume"):
                        col_map[col] = cl
                    elif "open" in cl:
                        col_map[col] = "open"
                    elif "high" in cl:
                        col_map[col] = "high"
                    elif "low" in cl:
                        col_map[col] = "low"
                    elif "close" in cl:
                        col_map[col] = "close"
                    elif "vol" in cl:
                        col_map[col] = "volume"

                df = df.rename(columns=col_map)
                required = {"open", "high", "low", "close"}
                if not required.issubset(df.columns):
                    return None

                for col in ["open", "high", "low", "close"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                if "volume" in df.columns:
                    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
                else:
                    df["volume"] = 0

                df = df.dropna(subset=["open", "high", "low", "close"])
                return df if len(df) >= 5 else None
    except Exception as e:
        print(f"[ChartAnalysis] Error fetching OHLC for {symbol}: {e}")
    return None


# ─── API Endpoints ───────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "chart-analysis"}


@app.get("/analyze/{symbol}")
async def analyze_symbol(symbol: str, interval: str = "1d", limit: int = 100):
    """
    Full chart analysis for a symbol.
    Returns patterns, indicators, support/resistance, and composite signal.
    """
    df = await fetch_ohlc(symbol, interval, limit)
    if df is None:
        raise HTTPException(404, f"Could not fetch OHLC data for {symbol}")

    result = compute_chart_signal(df)
    result["symbol"] = symbol
    result["interval"] = interval
    result["candles_analyzed"] = len(df)
    return result


@app.get("/patterns/{symbol}")
async def get_patterns(symbol: str, interval: str = "1d", limit: int = 50):
    """Just candlestick patterns for a symbol."""
    df = await fetch_ohlc(symbol, interval, limit)
    if df is None:
        raise HTTPException(404, f"Could not fetch OHLC data for {symbol}")

    patterns = detect_patterns(df)
    sr = compute_support_resistance(df)
    return {
        "symbol": symbol,
        "patterns": patterns,
        "support_resistance": sr,
        "current_price": float(df["close"].iloc[-1])
    }


@app.post("/analyze-batch")
async def analyze_batch(symbols: List[str]):
    """Analyze multiple symbols at once (max 20)."""
    symbols = symbols[:20]
    results = []

    for symbol in symbols:
        try:
            df = await fetch_ohlc(symbol, "1d", 100)
            if df is not None:
                result = compute_chart_signal(df)
                result["symbol"] = symbol
                results.append(result)
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})

    return {"results": results, "count": len(results)}


@app.get("/indicators/{symbol}")
async def get_indicators(symbol: str, interval: str = "1d", limit: int = 100):
    """Get raw indicator values for a symbol."""
    df = await fetch_ohlc(symbol, interval, limit)
    if df is None:
        raise HTTPException(404, f"Could not fetch OHLC data for {symbol}")

    close = df["close"]
    rsi = compute_rsi(close)
    macd = compute_macd(close)
    bb = compute_bollinger(close)
    vwap = compute_vwap(df)
    adx = compute_adx(df)
    atr = compute_atr(df)

    return {
        "symbol": symbol,
        "current_price": float(close.iloc[-1]),
        "rsi": round(float(rsi.iloc[-1]), 2) if not pd.isna(rsi.iloc[-1]) else None,
        "macd": macd,
        "bollinger": bb,
        "vwap": round(vwap, 2),
        "adx": adx,
        "atr": round(atr, 2),
        "ema9": round(compute_ema(close, 9), 2),
        "ema21": round(compute_ema(close, 21), 2),
        "ema50": round(compute_ema(close, 50), 2) if len(close) >= 50 else None,
        "interval": interval
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
