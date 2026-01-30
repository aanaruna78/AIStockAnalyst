import logging
import json
import httpx
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any
from base_crawler import BaseCrawler

logger = logging.getLogger("TickerTapeCrawler")

class TickerTapeCrawler(BaseCrawler):
    def __init__(self, source_id: str, base_url: str = "https://www.tickertape.in", rate_limit: int = 1, robots_url: Optional[str] = None):
        super().__init__(source_id, base_url, rate_limit, robots_url)
        self.search_api = "https://api.tickertape.in/search?text={}"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.tickertape.in/",
            "Origin": "https://www.tickertape.in",
            "Upgrade-Insecure-Requests": "1"
        }

    async def search_stock(self, symbol: str) -> Optional[str]:
        """
        Resolves a stock symbol (e.g., 'RELIANCE') to its TickerTape URL slug.
        Returns the full URL or None if not found.
        """
        try:
            url = self.search_api.format(symbol)
            async with httpx.AsyncClient(verify=False, headers=self.headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    # Look for exact match first
                    stocks = data.get("data", {}).get("stocks", [])
                    for stock in stocks:
                        if stock.get("ticker", "").upper() == symbol.upper():
                            return self.base_url + stock.get("slug")
                    
                    # Fallback to first stock result
                    if stocks:
                        return self.base_url + stocks[0].get("slug")
                        
            return None
        except Exception as e:
            logger.error(f"Error searching for stock {symbol}: {e}")
            return None

    async def crawl_stock(self, symbol: str, stock_name: str = "") -> Dict[str, Any]:
        """
        Crawls the TickerTape page for a specific stock and extracts fundamentals via Next.js hydration data.
        """
        stock_url = await self.search_api_lookup(symbol) if not symbol.startswith("http") else symbol
        
        # Fallback: Construct URL if search failed and we have a name
        if not stock_url and stock_name:
            import re
            # Clean name base
            # "Jio Financial Services Limited" -> "jio financial services limited"
            base_name = re.sub(r'[^a-zA-Z0-9\s]', '', stock_name).lower()
            
            # Variants to try
            variants = []
            variants.append(base_name.replace(" ", "-")) # jio-financial-services-limited
            if "limited" in base_name:
                variants.append(base_name.replace(" limited", "").replace(" ", "-")) # jio-financial-services
            if "ltd" in base_name:
                variants.append(base_name.replace(" ltd", "").replace(" ", "-"))

            for variant in variants:
                constructed_url = f"{self.base_url}/stocks/{variant}-{symbol.upper()}"
                logger.info(f"Trying constructed URL: {constructed_url}")
                if await self.verify_url(constructed_url):
                     stock_url = constructed_url
                     break

        if not stock_url:
            logger.warning(f"Could not resolve URL for {symbol}")
            return {}

        logger.info(f"Crawling {stock_url} for {symbol}")
        html = await self.fetch(stock_url)
        if not html:
            return {}

        soup = BeautifulSoup(html, "html.parser")
        data = {
            "symbol": symbol,
            "url": stock_url,
            "metrics": {},
            "checklist": {},
            "forecast": {}
        }

        try:
            # Parse Next.js Data Blob
            next_data = soup.find("script", id="__NEXT_DATA__")
            if not next_data:
                logger.warning("No __NEXT_DATA__ found, layout might have changed.")
                return data

            json_data = json.loads(next_data.string)
            props = json_data.get("props", {}).get("pageProps", {})
            
            # 1. Price
            quote = props.get("securityQuote", {})
            if quote:
                data["current_price"] = quote.get("price")
            
            # 2. Key Metrics
            security_info = props.get("securityInfo", {})
            ratios = security_info.get("ratios", {})
            
            # Confirmed keys from inspection
            data["metrics"]["pe_ratio"] = ratios.get("ttmPe")
            data["metrics"]["pb_ratio"] = ratios.get("pbr")
            data["metrics"]["div_yield"] = ratios.get("divYield")
            data["metrics"]["sector_pe"] = ratios.get("indpe")
            data["metrics"]["sector_pb"] = ratios.get("indpb")
            data["metrics"]["sector_div_yield"] = ratios.get("inddy")
            
            # 3. Investment Checklist (Scorecard)
            # Located in 'scorecard' which is a LIST of dicts
            scorecard = props.get("scorecard", [])
            for item in scorecard:
                if isinstance(item, dict):
                    title = item.get("name", "").lower().replace(" ", "_").replace("vs_fd_rates", "profitability")
                    tag = item.get("tag", "")
                    if title:
                        data["checklist"][title] = tag

            # 4. Forecast
            # Placeholder for future implementation if key is found

            # 5. Financial Statements
            # Extracting latest 3 years of consolidated data
            data["financials"] = {
                "income_statement": [],
                "balance_sheet": [],
                "cash_flow": []
            }
            
            # Helper to extract latest N records
            def get_latest(key, limit=3):
                records = props.get(key, [])
                if not records:
                    return []
                # Sort by endDate descending just in case, though usually sorted ascending
                # TickerTape array seems to be ascending (2016, 2017...)
                # So we take the last N
                return records[-limit:]

            data["financials"]["income_statement"] = get_latest("income-normal-annual")
            data["financials"]["balance_sheet"] = get_latest("balancesheet-normal-annual")
            data["financials"]["cash_flow"] = get_latest("cashflow-normal-annual")

        except Exception as e:
            logger.error(f"Parsing error for {symbol}: {e}")

        return data

    async def verify_url(self, url: str) -> bool:
        try:
             async with httpx.AsyncClient(verify=False, headers=self.headers, follow_redirects=True) as client:
                 resp = await client.head(url)
                 return resp.status_code == 200
        except: return False

    # Helper for pipeline
    async def search_api_lookup(self, symbol):
        return await self.search_stock(symbol)
