from base_crawler import BaseCrawler
from bs4 import BeautifulSoup
import logging
import re
from datetime import datetime

logger = logging.getLogger("TrendlyneCrawler")

class TrendlyneCrawler(BaseCrawler):
    def __init__(self, source_id: str, base_url: str, rate_limit: int, robots_url: str = None):
        super().__init__(source_id, base_url, rate_limit, robots_url)
        # Trendlyne might require specific headers to mimic a browser
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Upgrade-Insecure-Requests": "1"
        }

    async def crawl_recommendations(self):
        # Override fetch to include headers helper if needed, 
        # but BaseCrawler uses self.ua.random which is usually enough. 
        # We might need to inject extra headers if BaseCrawler allows, 
        # or just rely on User-Agent. The test showed User-Agent + others worked.
        # Let's try to just use fetch which sets User-Agent. 
        # If it fails, we might need to modify BaseCrawler or overload fetch here.
        # For now, let's assume BaseCrawler's httpx call is sufficient, 
        # but let's pass headers if we can. 
        # BaseCrawler.fetch doesn't accept extra headers argument easily without modification.
        # However, the verify script used specific headers. 
        # Let's override fetch logic slightly or just try default first.
        # Actually, let's just implement a custom fetch here to be safe and use tested headers.
        
        import httpx
        import time
        
        url = self.base_url
        
        # Rate limiting logic from BaseCrawler
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
           import asyncio
           await asyncio.sleep(self.rate_limit - elapsed)

        headers = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        
        html = None
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers, timeout=15.0)
                self.last_request_time = time.time()
                if response.status_code == 200:
                    html = response.text
                else:
                    logger.error(f"Failed to fetch Trendlyne: {response.status_code}")
                    return []
            except Exception as e:
                logger.error(f"Error fetching Trendlyne: {e}")
                return []

        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            logger.warning("No table found on Trendlyne research page")
            return []

        recommendations = []
        rows = table.find_all("tr")
        
        # Skip header row (usually index 0)
        # We need to identify valid data rows.
        for row in rows:
            cells = row.find_all("td")
            if not cells:
                continue
                
            # Expected structure based on test:
            # 0: checkbox/empty
            # 1: Date '27 Jan 2026'
            # 2: Stock 'DCB Bank'
            # 3: Author 'IDBI CapitalTarget'
            # 4: LTP '199.62'
            # 5: Target '220.00'
            # 6: Price at reco
            # 7: Upside
            # 8: Type 'Buy'
            
            if len(cells) < 9:
                continue
                
            try:
                date_text = cells[1].get_text(strip=True)
                stock_name = cells[2].get_text(strip=True)
                
                # Clean Author: "IDBI CapitalTarget" -> "IDBI Capital"
                author_text = cells[3].get_text(strip=True)
                analyst = author_text.replace("Target", "").strip()
                
                target_text = cells[5].get_text(strip=True)
                target = float(target_text) if target_text else 0.0
                
                action = cells[8].get_text(strip=True).upper()
                
                # Symbol mapping is tricky since we only have name.
                # We'll use the name as symbol for now, ingestion pipeline usually tries to map it via NSE CSV later
                # or we can rely on fuzzy match in batch job.
                # Ideally, we extract symbol if available in links.
                # Check column 2 link
                symbol = stock_name.upper() # Default
                link = cells[2].find("a")
                if link and link.get("href"):
                    # href might be /equity/500112/SBIN/state-bank-of-india/
                    # Extract SBIN
                    href = link.get("href")
                    parts = href.split("/")
                    if len(parts) > 3:
                        # parts[3] might be symbol if url structure matches
                        candidate = parts[3] 
                        if candidate.isupper(): 
                             symbol = candidate
                        elif parts[2].isdigit(): # /equity/500112/SBIN/...
                             symbol = parts[3]

                recommendations.append({
                    "symbol": symbol,
                    "action": action,
                    "analyst": analyst,
                    "target": target,
                    "date": date_text,
                    "content": f"Trendlyne report: {analyst} recommends {action} on {stock_name} with target {target}. Date: {date_text}."
                })
                
            except Exception as e:
                logger.debug(f"Row parsing error: {e}")
                continue
                
        return recommendations
