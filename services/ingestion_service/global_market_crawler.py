import logging
import httpx
from typing import Dict, Any, List
import yfinance as yf
from base_crawler import BaseCrawler

logger = logging.getLogger("GlobalMarketCrawler")

class GlobalMarketCrawler(BaseCrawler):
    def __init__(self, source_id: str = "investing_global", base_url: str = "https://in.investing.com", rate_limit: int = 2):
        # We keep base_url for interface compatibility but use yfinance internally
        super().__init__(source_id, base_url, rate_limit)

    async def fetch_sentiment(self) -> Dict[str, Any]:
        """
        Fetches Global Market Indices using yfinance.
        Symbols: 
        - ES=F (S&P 500 Futures)
        - NQ=F (Nasdaq Futures)
        - ^NSEI (Nifty 50)
        """
        logger.info("Fetching Global Sentiment via yfinance...")
        
        indices_map = {
            "S&P 500 Futures": "ES=F",
            "Nasdaq Futures": "NQ=F",
            "Dow Futures": "YM=F",
            "Nifty 50": "^NSEI",
            "USD/INR": "INR=X",
            "India VIX": "^INDIAVIX"
        }
        
        data = {}
        
        try:
            tickers = yf.Tickers(" ".join(indices_map.values()))
            
            for name, symbol in indices_map.items():
                try:
                    ticker = tickers.tickers[symbol]
                    # Try fast_info first
                    change_pct = 0.0
                    
                    if hasattr(ticker, "fast_info"):
                        prev = ticker.fast_info.previous_close
                        last = ticker.fast_info.last_price
                        if prev and last:
                            change_pct = ((last - prev) / prev) * 100
                    
                    # Fallback to history if fast_info fails or is incomplete
                    if change_pct == 0.0:
                        hist = ticker.history(period="2d")
                        if len(hist) >= 2:
                            prev = hist["Close"].iloc[-2]
                            last = hist["Close"].iloc[-1]
                            change_pct = ((last - prev) / prev) * 100
                        elif len(hist) == 1:
                             # Use open as proxy if only 1 day data (e.g. early morning)
                            open_p = hist["Open"].iloc[0]
                            last = hist["Close"].iloc[-1]
                            change_pct = ((last - open_p) / open_p) * 100

                    data[name] = round(change_pct, 2)
                    if name == "India VIX":
                        data["vix_absolute"] = round(last, 2)
                except Exception as e:
                    logger.warning(f"Failed to fetch {name} ({symbol}): {e}")
            
            logger.info(f"Global Indices Data: {data}")
            return self.calculate_sentiment(data)
            
        except Exception as e:
            logger.error(f"Global Crawler Error: {e}")
            return self.get_neutral_sentiment(str(e))

    def calculate_sentiment(self, data: Dict[str, float]) -> Dict[str, Any]:
        if not data:
            return self.get_neutral_sentiment("No data")

        us_500 = data.get("S&P 500 Futures", 0)
        nasdaq = data.get("Nasdaq Futures", 0)
        nifty = data.get("Nifty 50", 0)
        usd_inr = data.get("USD/INR", 0)
        vix_abs = data.get("vix_absolute", 0)
        
        score = 0.0
        details = []

        # Heuristic Logic
        if us_500 < -0.3 or nasdaq < -0.4:
            score -= 0.5
            details.append("US Futures Bearish")
        elif us_500 > 0.3 or nasdaq > 0.4:
            score += 0.4
            details.append("US Futures Bullish")
        
        # Nifty Check
        if nifty < -0.4:
            score -= 0.2
            details.append("Nifty Weak")
        elif nifty > 0.4:
            score += 0.2
            details.append("Nifty Strong")

        # USD/INR Check
        if usd_inr > 0.2:
            score -= 0.1
            details.append("Rupee Weakening")
        elif usd_inr < -0.2:
            score += 0.1
            details.append("Rupee Strengthening")

        score = max(-1.0, min(1.0, score))
        
        summary = f"Global: {'Bullish' if score > 0.3 else 'Bearish' if score < -0.3 else 'Neutral'}. "
        summary += ", ".join(details)
        summary += f" [S&P: {us_500}%, VIX: {vix_abs}]"

        return {
            "global_score": score,
            "global_summary": summary,
            "indices": data,
            "vix": vix_abs
        }

    async def fetch_indices_live(self) -> List[Dict[str, Any]]:
        """Fetches raw live index data for the ticker bar."""
        symbols = {
            "NIFTY 50": "^NSEI",
            "SENSEX": "^BSESN",
            "BANK NIFTY": "^NSEBANK",
            "INDIA VIX": "^INDIAVIX"
        }
        results = []
        try:
            tickers = yf.Tickers(" ".join(symbols.values()))
            for name, sym in symbols.items():
                try:
                    t = tickers.tickers[sym]
                    price = t.fast_info.last_price
                    prev = t.fast_info.previous_close
                    change = price - prev
                    change_pct = (change / prev) * 100
                    results.append({
                        "name": name,
                        "price": round(price, 2),
                        "change": round(change, 2),
                        "change_pct": round(change_pct, 2)
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Error in fetch_indices_live: {e}")
        return results

    async def fetch_market_news(self) -> List[Dict[str, Any]]:
        """Fetches latest market news from yfinance and LiveMint."""
        news_items = []
        
        # 1. Fetch from yfinance (clickable)
        for sym in ["^NSEI", "ES=F"]:
            try:
                ticker = yf.Ticker(sym)
                items = ticker.news
                for item in items[:4]:
                    title = item.get("title")
                    if title:
                        news_items.append({
                            "title": title,
                            "link": item.get("link"),
                            "publisher": item.get("publisher") or "yfinance",
                            "provider": sym,
                            "clickable": True
                        })
            except Exception as e:
                logger.error(f"Error fetching yfinance news for {sym}: {e}")

        # 2. Fetch from LiveMint (non-clickable)
        try:
            livemint_news = await self.fetch_livemint_news()
            news_items.extend(livemint_news)
        except Exception as e:
            logger.error(f"Error fetching LiveMint news: {e}")

        # Deduplicate headlines
        seen = set()
        unique_news = []
        for n in news_items:
            if n["title"] not in seen:
                unique_news.append(n)
                seen.add(n["title"])
        
        return unique_news[:12]

    async def fetch_livemint_news(self) -> List[Dict[str, Any]]:
        """Crawls LiveMint market page for news headlines (non-clickable)."""
        news_items = []
        url = "https://www.livemint.com/market"
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                resp = await client.get(url, headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    
                    # Target Markets News and Stock Market News sections
                    # Based on research, headlines are often in h2 or h3 within these sections
                    # We'll look for common headline patterns
                    headlines = soup.select('.market-news_news_row__R_UDp h2 a, section[class*="stock-market-news"] h2 a, .headline h2 a, .headline h3 a')
                    
                    if not headlines:
                        # Fallback to general h2/h3 if specific classes changed
                        headlines = soup.find_all(['h2', 'h3'], limit=15)

                    for hl in headlines:
                        text = hl.text.strip()
                        if text and len(text) > 10:
                            news_items.append({
                                "title": text,
                                "link": "#",
                                "publisher": "LiveMint",
                                "provider": "LiveMint",
                                "clickable": False
                            })
                            if len(news_items) >= 8:
                                break
        except Exception as e:
            logger.error(f"LiveMint crawl failed: {e}")
            
        return news_items

    async def fetch_adrs(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Fetches price and change% for a list of ADR tickers.
        Returns: {'INFY': {'price': 18.5, 'change_pct': 1.2}, ...}
        """
        if not tickers:
            return {}
            
        logger.info(f"Fetching ADRs: {tickers}")
        results = {}
        
        try:
            # Using yfinance Tickers for batch fetching
            yt = yf.Tickers(" ".join(tickers))
            
            for symbol in tickers:
                try:
                    ticker = yt.tickers[symbol]
                    # Try fast_info
                    price = 0.0
                    prev = 0.0
                    change_pct = 0.0
                    
                    if hasattr(ticker, "fast_info"):
                        price = ticker.fast_info.last_price
                        prev = ticker.fast_info.previous_close
                        
                    # Fallback
                    if price == 0.0 or prev == 0.0:
                         hist = ticker.history(period="2d")
                         if len(hist) >= 2:
                             prev = hist["Close"].iloc[-2]
                             price = hist["Close"].iloc[-1]
                         elif len(hist) == 1:
                             prev = hist["Open"].iloc[0]
                             price = hist["Close"].iloc[-1]

                    if prev > 0:
                        change_pct = ((price - prev) / prev) * 100
                        
                    results[symbol] = {
                        "price": round(price, 2),
                        "change_pct": round(change_pct, 2)
                    }
                except Exception as e:
                    logger.warning(f"Error fetching ADR {symbol}: {e}")
                    results[symbol] = {"price": 0.0, "change_pct": 0.0, "error": str(e)}
                    
        except Exception as e:
            logger.error(f"Batch fetch failed: {e}")
            
        return results

    def get_neutral_sentiment(self, reason: str):
        return {
            "global_score": 0.0,
            "global_summary": f"Global: Neutral ({reason})",
            "indices": {}
        }
