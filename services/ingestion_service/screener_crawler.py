
import logging
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
from base_crawler import BaseCrawler

logger = logging.getLogger("ScreenerCrawler")

class ScreenerCrawler(BaseCrawler):
    def __init__(self, source_id: str, base_url: str = "https://www.screener.in", rate_limit: int = 1):
        super().__init__(source_id, base_url, rate_limit)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }

    SYMBOL_OVERRIDES = {
        "ZOMATO": "ETERNAL"
    }

    async def crawl_stock(self, symbol: str) -> Dict[str, Any]:
        """
        Crawls Screener.in for a given stock symbol.
        Extracts 'Top Ratios' (Fundamentals) and 'Pros/Cons'.
        """
        # Handle symbol overrides (e.g., ZOMATO -> ETERNAL)
        crawler_symbol = self.SYMBOL_OVERRIDES.get(symbol, symbol)
        
        url = f"{self.base_url}/company/{crawler_symbol}/"
        logger.info(f"Crawling {url}...")
        
        html = await self.fetch(url)
        if not html:
            logger.warning(f"Failed to fetch content for {symbol}")
            return {}

        soup = BeautifulSoup(html, "html.parser")
        data = {
            "symbol": symbol,
            "url": url,
            "fundamentals": {},
            "pros": [],
            "cons": []
        }

        try:
            # 1. Extract Top Ratios (Fundamentals)
            # These are usually in a list with class 'company-ratios' or similar structure
            # Looking for <li class="flex flex-space-between">...
            #   <span class="name">ROCE</span>
            #   <span class="nowrap value"><span class="number">12.5</span> %</span>
            
            ratios_ul = soup.find("ul", id="top-ratios")
            
            if ratios_ul:
                for li in ratios_ul.find_all("li"):
                    name_span = li.find("span", class_="name")
                    value_span = li.find("span", class_="value")
                    
                    if name_span and value_span:
                        key = name_span.get_text(strip=True).replace(" ", "_").lower()
                        # Extract number only, handle commas
                        raw_val = value_span.find("span", class_="number")
                        if raw_val:
                            try:
                                val_text = raw_val.get_text(strip=True).replace(",", "")
                                data["fundamentals"][key] = float(val_text)
                            except ValueError:
                                data["fundamentals"][key] = raw_val.get_text(strip=True)

            # 2. Extract Pros and Cons
            # Usually in a section class="pros-cons"
            pros_section = soup.find("div", class_="pros")
            if pros_section:
                for li in pros_section.find_all("li"):
                    data["pros"].append(li.get_text(strip=True))
            
            cons_section = soup.find("div", class_="cons")
            if cons_section:
                for li in cons_section.find_all("li"):
                    data["cons"].append(li.get_text(strip=True))

        except Exception as e:
            logger.error(f"Error parsing Screener data for {symbol}: {e}")

        return data
