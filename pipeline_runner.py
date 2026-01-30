import asyncio
import csv
import os
import sys
import random
import logging
import ssl

# Add service paths for host-side imports compatibility
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "services/ingestion_service")))

import certifi
import yfinance as yf
from services.ingestion_service.tradingview_crawler import TradingViewCrawler
from services.ingestion_service.tickertape_crawler import TickerTapeCrawler
from services.ingestion_service.screener_crawler import ScreenerCrawler
from services.ingestion_service.global_market_crawler import GlobalMarketCrawler
import httpx
from typing import List, Dict, Any
import json
import os
from shared.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PipelineRunner")

# SSL Fix for Mac
try:
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

# Constants
# Constants from centralized config
STOCKS_FILE = settings.STOCKS_FILE_PATH
# Using API Gateway for centralized access
RECOMMENDATION_API = f"{settings.API_GATEWAY_URL}/api/v1/recommendations/generate"
CRAWLER_DELAY = settings.CRAWLER_DELAY_SECONDS
BATCH_SIZE = settings.PIPELINE_BATCH_SIZE
LOOP_INTERVAL = settings.PIPELINE_LOOP_INTERVAL_SECONDS

class PipelineRunner:
    def __init__(self):
        self.crawler = TradingViewCrawler(
            source_id="tradingview",
            base_url="https://www.tradingview.com",
            rate_limit=1,
            robots_url="https://www.tradingview.com/robots.txt"
        )
        self.tickertape = TickerTapeCrawler(
            source_id="tickertape",
            base_url="https://www.tickertape.in",
            rate_limit=1
        )
        self.screener = ScreenerCrawler(
            source_id="screener",
            base_url="https://www.screener.in",
            rate_limit=1
        )
        self.global_crawler = GlobalMarketCrawler(
            source_id="investing_global",
            base_url="https://in.investing.com",
            rate_limit=2
        )
        self.stocks: List[Dict[str, str]] = []
        self.global_context: Dict[str, Any] = {}
        
        # NSE Symbol -> US ADR Ticker Mapping
        self.adr_mapping = {
            "INFY": "INFY",
            "HDFCBANK": "HDB",
            "ICICIBANK": "IBN",
            "WIPRO": "WIT",
            "DRREDDY": "RDY",
            "MMYT": "MMYT", 
            "SIFY": "SIFY",
            "TATASTEEL": None,
            "RELIANCE": None 
        }

    def load_stocks(self):
        try:
            with open(STOCKS_FILE, mode='r') as f:
                reader = csv.DictReader(f)
                self.stocks = [row for row in reader]
            logger.info(f"Loaded {len(self.stocks)} stocks from {STOCKS_FILE}")
        except FileNotFoundError:
            logger.error(f"Stocks file not found: {STOCKS_FILE}")
            # Fallback for testing
            self.stocks = [{"Symbol": "RELIANCE", "Name": "Reliance Industries"}]

    async def get_real_price(self, symbol: str) -> float:
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            # 1. Try fast_info (object or dict)
            try:
                if hasattr(ticker, 'fast_info') and ticker.fast_info is not None:
                    # Some versions return an object with attributes, some a dictionary
                    if isinstance(ticker.fast_info, dict):
                        price = ticker.fast_info.get('lastPrice') or ticker.fast_info.get('last_price')
                    else:
                        price = getattr(ticker.fast_info, 'last_price', None) or getattr(ticker.fast_info, 'lastPrice', None)
                    
                    if price:
                        return round(float(price), 2)
            except Exception:
                pass
            
            # 2. Fallback to history
            hist = ticker.history(period="1d")
            if hist is not None and not hist.empty and 'Close' in hist.columns:
                return round(float(hist['Close'].iloc[-1]), 2)
            
            # 3. Last ditch fallback to basic info
            if ticker.info and 'currentPrice' in ticker.info:
                return round(float(ticker.info['currentPrice']), 2)
        except Exception as e:
            logger.warning(f"Failed to fetch price for {symbol}: {e}")
        
        # Fallback to random if API fails (mock data for now to keep pipeline flowing)
        return round(random.uniform(100, 3000), 2)

    async def process_stock(self, stock: Dict[str, str], adr_data: Dict[str, Any] = None):
        symbol = stock.get('symbol') or stock.get('Symbol')
        if not symbol:
            logger.error(f"Stock record missing symbol: {stock}")
            return
            
        logger.info(f"Processing {symbol}...")

        # 1. Crawl Sentinel/Idea Data
        # For now, we use crawl_ideas. In a real scenario, we might parse technical widgets.
        ideas = await self.crawler.crawl_ideas(symbol)
        
        # Generate a rationale from ideas or fallback
        rationale = ""
        sentiment_score = 0.0
        
        if ideas:
            # Simple summarization or simple concatenation of top idea
            top_idea = ideas[0]
            rationale = f"**Signal Analysis**\n{top_idea['title']}\n{top_idea['body'][:200]}..."
            # Naive sentiment Analysis
            lower_text = (top_idea['title'] + top_idea['body']).lower()
            if "bull" in lower_text or "long" in lower_text or "buy" in lower_text:
                sentiment_score = 0.8
            elif "bear" in lower_text or "short" in lower_text or "sell" in lower_text:
                sentiment_score = -0.8
        else:
            # Fallback if no ideas found (common for smaller stocks)
            rationale = f"**Signal Analysis**\nAI monitoring active. No sufficient community ideas found recently. Technical scan proceeding."
            sentiment_score = 0.1 # Neutral

        
        
        # 1.5 Crawl TickerTape Fundamentals (Existing)
        stock_name = stock.get("Name", "")
        tt_data = await self.tickertape.crawl_stock(symbol, stock_name=stock_name)
        fundamentals = tt_data.get("metrics", {})
        checklist = tt_data.get("checklist", {})
        financials = tt_data.get("financials", {})
        
        # 1.6 Crawl Screener.in Fundamentals (NEW)
        screener_data = await self.screener.crawl_stock(symbol)
        
        # Get real price early for fallbacks
        price = await self.get_real_price(symbol)
        
        # Fallback: If TickerTape metrics missing, try to fill from Screener
        if not fundamentals:
            sc_funds = screener_data.get("fundamentals", {})
            if sc_funds:
                fundamentals = {}
                # Map Screener keys to TickerTape structure
                if "stock_pe" in sc_funds: fundamentals['pe_ratio'] = sc_funds['stock_pe']
                if "stock_p/e" in sc_funds: fundamentals['pe_ratio'] = sc_funds['stock_p/e']
                if "dividend_yield" in sc_funds: fundamentals['div_yield'] = sc_funds['dividend_yield']
                
                # Calculate PB if possible
                curr_price = tt_data.get("current_price") or price
                book_val = sc_funds.get("book_value")
                if curr_price and book_val:
                    try:
                        fundamentals['pb_ratio'] = float(curr_price) / float(book_val)
                    except: pass
                
                # Assign back so payload has it
                if not tt_data.get("metrics"):
                    tt_data["metrics"] = fundamentals

        # Enrich rationale (TickerTape part)
        if checklist:
            rationale += f"\n\n**TickerTape Fundamentals**\n"
            rationale += f"- Valuation: {checklist.get('valuation', 'N/A')}\n"
            rationale += f"- Profitability: {checklist.get('profitability', 'N/A')}\n"
            rationale += f"- Entry Point: {checklist.get('entry_point', 'N/A')}\n"
            
        if fundamentals:
             pe = fundamentals.get('pe_ratio', 'N/A')
             sector_pe = fundamentals.get('sector_pe', 'N/A')
             rationale += f"- PE Ratio: {pe} (Sector: {sector_pe})\n"
        
        # Ensure price is valid
        if not price and "current_price" in tt_data:
             price = tt_data["current_price"]
        if not price:
             # Try getting from screener
             sc_funds = screener_data.get("fundamentals", {})
             if "current_price" in sc_funds:
                 price = sc_funds["current_price"]

        # 3. Construct Payload
        # We simulate some technicals based on our "sentiment"
        rsi = 65 if sentiment_score > 0 else 35
        
        # Enrich global_analysis with specific ADR data if available
        stock_global_context = self.global_context.copy()
        adr_ticker = self.adr_mapping.get(symbol)
        if adr_ticker and adr_data and adr_ticker in adr_data:
            stock_global_context["adr"] = {
                "ticker": adr_ticker,
                "data": adr_data[adr_ticker]
            }

        payload = {
            "symbol": symbol,
            "current_price": tt_data.get("current_price") or price, 
            "fundamentals": fundamentals,
            "checklist": checklist,
            "financials": financials,
            "screener_analysis": screener_data, 
            "tickertape_analysis": tt_data,
            "global_analysis": stock_global_context, # NEW FIELD
            "atr": price * 0.02, 
            "indicators": {
                "rsi": rsi,
                "macd": "bullish" if sentiment_score > 0 else "bearish"
            },
            "signals": [
                {
                    "source": "tradingview_ideas",
                    "sentiment": sentiment_score,
                    "relevance": 0.9,
                    "raw_text": rationale 
                }
            ]
        }

        # 4. Push to Engine
        async with httpx.AsyncClient(verify=False) as client:
            try:
                # Direct call to engine to avoid auth complexity for internal pipeline
                resp = await client.post(f"{settings.REC_ENGINE_URL}/generate", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    if status == "published":
                        logger.info(f"✅ Published: {symbol}")
                        rec = data.get("recommendation", {})
                        if "score_breakdown" in rec:
                            sb = rec["score_breakdown"]
                            logger.info(f"📊 {symbol} Scores: Sent={int(sb.get('Sentiment',0))}, Tech={int(sb.get('Technical',0))}, AI={int(sb.get('AI Model',0))}")
                    elif status == "suppressed":
                        logger.info(f"Start suppressed: {symbol} (Low Conviction/Duplicate)")
                else:
                    logger.error(f"Failed to publish {symbol}: {resp.text}")
            except Exception as e:
                logger.error(f"API Error for {symbol}: {e}")

    def cleanup_legacy_data(self):
        """
        Removes recommendations for symbols that are no longer in the CSV.
        """
        rec_file = "data/recommendations.json"
        if not os.path.exists(rec_file):
            return

        try:
            # Get valid symbols from loaded stocks
            valid_symbols = {s['Symbol'] for s in self.stocks}
            
            with open(rec_file, "r") as f:
                data = json.load(f)
            
            original_count = len(data)
            # Keep only recommendations where the symbol is in our valid list
            # We check both the key (usually SYMBOL_TIMESTAMP) and the 'symbol' field
            new_data = {
                k: v for k, v in data.items() 
                if v.get('symbol') in valid_symbols
            }
            
            if len(new_data) < original_count:
                removed_count = original_count - len(new_data)
                logger.info(f"Cleanup: Removing {removed_count} legacy recommendations not in CSV.")
                with open(rec_file, "w") as f:
                    json.dump(new_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error during legacy data cleanup: {e}")

    async def run(self):
        # self.load_stocks() - Removed to allow external filtering
        
        while True:
            # Cleanup stale data before starting a new cycle
            if self.stocks:
                self.cleanup_legacy_data()

            logger.info("Starting crawl cycle...")
            
            # 1. Fetch Global Sentiment (Indices)
            try:
                self.global_context = await self.global_crawler.fetch_sentiment()
                logger.info(f"Global Sentiment Score: {self.global_context.get('global_score')}")
            except Exception as e:
                logger.error(f"Failed to fetch global sentiment: {e}")
                self.global_context = {}
            
            # 2. Fetch ADR Data (Batch)
            adr_tickers = [v for k, v in self.adr_mapping.items() if v]
            adr_data = {}
            try:
                if adr_tickers:
                    adr_data = await self.global_crawler.fetch_adrs(adr_tickers)
                    logger.info(f"Fetched {len(adr_data)} ADRs")
            except Exception as e:
                logger.error(f"Failed to fetch ADRs: {e}")
            
            # Process in batches
            for i in range(0, len(self.stocks), BATCH_SIZE):
                batch = self.stocks[i : i + BATCH_SIZE]
                tasks = [self.process_stock(stock, adr_data) for stock in batch]
                
                await asyncio.gather(*tasks)
                
                # Rate limiting sleep
                await asyncio.sleep(CRAWLER_DELAY)
            
            logger.info(f"Cycle complete. Sleeping for {LOOP_INTERVAL} seconds...")
            await asyncio.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, help="Run for specific symbol")
    args = parser.parse_args()

    runner = PipelineRunner()
    runner.load_stocks()
    
    if args.symbol:
        # Filter stocks if symbol provided
        filtered = [s for s in runner.stocks if s['Symbol'].upper() == args.symbol.upper()]
        if filtered:
            runner.stocks = filtered
            logger.info(f"Running targeting mode for {args.symbol}")
        else:
            # If not in CSV, create temporary
            logger.warning(f"{args.symbol} not found in CSV, attempting direct run")
            runner.stocks = [{"Symbol": args.symbol.upper(), "Name": args.symbol.upper()}]
            
    asyncio.run(runner.run())
