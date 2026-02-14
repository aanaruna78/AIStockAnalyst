import yfinance as yf
import pandas as pd
import math

tickers = ["ITC.NS", "JIOFIN.NS", "TRENT.NS", "RELIANCE.NS"]
print(f"Testing tickers: {tickers}")

for sym in tickers:
    print(f"\n--- Testing {sym} ---")
    t = yf.Ticker(sym)
    
    # 1. Test fast_info
    try:
        fi = t.fast_info
        print(f"fast_info keys: {list(fi.keys())}")
        print(f"fast_info lastPrice: {fi.get('lastPrice')}")
        print(f"fast_info last_price: {fi.get('last_price')}")
    except Exception as e:
        print(f"fast_info error: {e}")

    # 2. Test info (slow)
    try:
        inf = t.info
        print(f"info currentPrice: {inf.get('currentPrice')}")
        print(f"info regularMarketPrice: {inf.get('regularMarketPrice')}")
    except Exception as e:
        print(f"info error: {e}")

    # 3. Test history (known bug area)
    try:
        h = t.history(period="1d", interval="1m")
        if not h.empty:
            print(f"history last close: {h['Close'].iloc[-1]}")
        else:
            print("history empty")
    except Exception as e:
        print(f"history error: {e}")
