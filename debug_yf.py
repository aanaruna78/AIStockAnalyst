import yfinance as yf
import pandas as pd

tickers = "ITC.NS JIOFIN.NS TRENT.NS RELIANCE.NS"
print(f"Testing tickers: {tickers}")

try:
    data = yf.download(tickers, period="1d", interval="1m", progress=False)
    print("Download complete.")
    print("Columns:", data.columns)
    if 'Close' in data:
        print("Close Data Head:\n", data['Close'].tail())
    else:
        print("No 'Close' column found.")
        print("Data:\n", data)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
