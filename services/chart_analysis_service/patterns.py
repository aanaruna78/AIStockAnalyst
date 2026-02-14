"""
Pattern Detection Module
========================
Candlestick pattern recognition for Indian equity markets.
Detects classic patterns: Doji, Hammer, Engulfing, Morning/Evening Star,
Marubozu, Harami, Three White Soldiers, Three Black Crows, etc.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional


def detect_patterns(df: pd.DataFrame) -> List[Dict]:
    """
    Detect candlestick patterns from OHLC DataFrame.
    Expects columns: open, high, low, close, volume
    Returns list of pattern dicts with name, type (bullish/bearish), strength.
    """
    if len(df) < 3:
        return []

    patterns = []
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    body = c - o
    body_abs = np.abs(body)
    upper_shadow = h - np.maximum(o, c)
    lower_shadow = np.minimum(o, c) - l
    total_range = h - l

    # Prevent division by zero
    total_range = np.where(total_range == 0, 0.0001, total_range)
    body_abs_safe = np.where(body_abs == 0, 0.0001, body_abs)

    i = len(df) - 1  # Analyze latest candle primarily

    # --- Single candle patterns ---

    # Doji: small body relative to range
    if body_abs[i] < total_range[i] * 0.1:
        patterns.append({
            "name": "Doji",
            "type": "neutral",
            "strength": 0.6,
            "description": "Indecision — body is very small relative to range"
        })

    # Hammer: small body at top, long lower shadow
    if (lower_shadow[i] > body_abs[i] * 2 and
            upper_shadow[i] < body_abs[i] * 0.5 and
            body[i] > 0):
        patterns.append({
            "name": "Hammer",
            "type": "bullish",
            "strength": 0.7,
            "description": "Bullish reversal — long lower shadow, small body at top"
        })

    # Inverted Hammer
    if (upper_shadow[i] > body_abs[i] * 2 and
            lower_shadow[i] < body_abs[i] * 0.5 and
            body[i] > 0):
        patterns.append({
            "name": "Inverted Hammer",
            "type": "bullish",
            "strength": 0.6,
            "description": "Potential bullish reversal — long upper shadow"
        })

    # Hanging Man (like hammer but in uptrend)
    if (lower_shadow[i] > body_abs[i] * 2 and
            upper_shadow[i] < body_abs[i] * 0.5 and
            body[i] < 0):
        patterns.append({
            "name": "Hanging Man",
            "type": "bearish",
            "strength": 0.6,
            "description": "Bearish reversal — long lower shadow, body at top"
        })

    # Shooting Star
    if (upper_shadow[i] > body_abs[i] * 2 and
            lower_shadow[i] < body_abs[i] * 0.5 and
            body[i] < 0):
        patterns.append({
            "name": "Shooting Star",
            "type": "bearish",
            "strength": 0.7,
            "description": "Bearish reversal — long upper shadow after uptrend"
        })

    # Marubozu (bullish)
    if (body[i] > 0 and
            upper_shadow[i] < total_range[i] * 0.05 and
            lower_shadow[i] < total_range[i] * 0.05):
        patterns.append({
            "name": "Bullish Marubozu",
            "type": "bullish",
            "strength": 0.8,
            "description": "Strong bullish — no shadows, full range body"
        })

    # Marubozu (bearish)
    if (body[i] < 0 and
            upper_shadow[i] < total_range[i] * 0.05 and
            lower_shadow[i] < total_range[i] * 0.05):
        patterns.append({
            "name": "Bearish Marubozu",
            "type": "bearish",
            "strength": 0.8,
            "description": "Strong bearish — no shadows, full range body"
        })

    # --- Two-candle patterns (latest two) ---
    if i >= 1:
        # Bullish Engulfing
        if (body[i - 1] < 0 and body[i] > 0 and
                o[i] <= c[i - 1] and c[i] >= o[i - 1]):
            patterns.append({
                "name": "Bullish Engulfing",
                "type": "bullish",
                "strength": 0.8,
                "description": "Bullish reversal — green candle engulfs prior red"
            })

        # Bearish Engulfing
        if (body[i - 1] > 0 and body[i] < 0 and
                o[i] >= c[i - 1] and c[i] <= o[i - 1]):
            patterns.append({
                "name": "Bearish Engulfing",
                "type": "bearish",
                "strength": 0.8,
                "description": "Bearish reversal — red candle engulfs prior green"
            })

        # Bullish Harami
        if (body[i - 1] < 0 and body[i] > 0 and
                o[i] > c[i - 1] and c[i] < o[i - 1] and
                body_abs[i] < body_abs[i - 1] * 0.6):
            patterns.append({
                "name": "Bullish Harami",
                "type": "bullish",
                "strength": 0.6,
                "description": "Potential reversal — small green inside prior red"
            })

        # Bearish Harami
        if (body[i - 1] > 0 and body[i] < 0 and
                o[i] < c[i - 1] and c[i] > o[i - 1] and
                body_abs[i] < body_abs[i - 1] * 0.6):
            patterns.append({
                "name": "Bearish Harami",
                "type": "bearish",
                "strength": 0.6,
                "description": "Potential reversal — small red inside prior green"
            })

        # Piercing Line
        if (body[i - 1] < 0 and body[i] > 0 and
                o[i] < l[i - 1] and
                c[i] > (o[i - 1] + c[i - 1]) / 2):
            patterns.append({
                "name": "Piercing Line",
                "type": "bullish",
                "strength": 0.7,
                "description": "Bullish — opens below prior low, closes above midpoint"
            })

        # Dark Cloud Cover
        if (body[i - 1] > 0 and body[i] < 0 and
                o[i] > h[i - 1] and
                c[i] < (o[i - 1] + c[i - 1]) / 2):
            patterns.append({
                "name": "Dark Cloud Cover",
                "type": "bearish",
                "strength": 0.7,
                "description": "Bearish — opens above prior high, closes below midpoint"
            })

    # --- Three-candle patterns ---
    if i >= 2:
        # Three White Soldiers
        if (body[i - 2] > 0 and body[i - 1] > 0 and body[i] > 0 and
                c[i] > c[i - 1] > c[i - 2] and
                o[i] > o[i - 1] > o[i - 2]):
            patterns.append({
                "name": "Three White Soldiers",
                "type": "bullish",
                "strength": 0.9,
                "description": "Strong bullish — three consecutive rising green candles"
            })

        # Three Black Crows
        if (body[i - 2] < 0 and body[i - 1] < 0 and body[i] < 0 and
                c[i] < c[i - 1] < c[i - 2] and
                o[i] < o[i - 1] < o[i - 2]):
            patterns.append({
                "name": "Three Black Crows",
                "type": "bearish",
                "strength": 0.9,
                "description": "Strong bearish — three consecutive falling red candles"
            })

        # Morning Star
        if (body[i - 2] < 0 and
                body_abs[i - 1] < body_abs[i - 2] * 0.3 and
                body[i] > 0 and
                c[i] > (o[i - 2] + c[i - 2]) / 2):
            patterns.append({
                "name": "Morning Star",
                "type": "bullish",
                "strength": 0.85,
                "description": "Bullish reversal — red, small body, green recovery"
            })

        # Evening Star
        if (body[i - 2] > 0 and
                body_abs[i - 1] < body_abs[i - 2] * 0.3 and
                body[i] < 0 and
                c[i] < (o[i - 2] + c[i - 2]) / 2):
            patterns.append({
                "name": "Evening Star",
                "type": "bearish",
                "strength": 0.85,
                "description": "Bearish reversal — green, small body, red drop"
            })

    return patterns


def compute_support_resistance(df: pd.DataFrame, window: int = 20) -> Dict:
    """
    Identify support and resistance levels using pivot points
    and recent swing highs/lows.
    """
    if len(df) < window:
        return {"support": [], "resistance": []}

    highs = df["high"].values[-window:]
    lows = df["low"].values[-window:]
    close = df["close"].values[-1]

    # Find local extrema
    supports = []
    resistances = []

    for j in range(2, len(highs) - 2):
        # Local high (resistance)
        if highs[j] > highs[j - 1] and highs[j] > highs[j - 2] and \
           highs[j] > highs[j + 1] and highs[j] > highs[j + 2]:
            resistances.append(float(highs[j]))

        # Local low (support)
        if lows[j] < lows[j - 1] and lows[j] < lows[j - 2] and \
           lows[j] < lows[j + 1] and lows[j] < lows[j + 2]:
            supports.append(float(lows[j]))

    # Also add classic pivot points
    h, l, c_val = float(df["high"].iloc[-1]), float(df["low"].iloc[-1]), float(df["close"].iloc[-1])
    pivot = (h + l + c_val) / 3
    r1 = 2 * pivot - l
    s1 = 2 * pivot - h
    r2 = pivot + (h - l)
    s2 = pivot - (h - l)

    supports.extend([s1, s2])
    resistances.extend([r1, r2])

    # Sort and deduplicate (within 0.5% proximity)
    supports = sorted(set([round(s, 2) for s in supports if s < close]))
    resistances = sorted(set([round(r, 2) for r in resistances if r > close]))

    return {
        "support": supports[-3:] if len(supports) > 3 else supports,  # nearest 3
        "resistance": resistances[:3] if len(resistances) > 3 else resistances,
        "pivot": round(pivot, 2)
    }
