from base_crawler import BaseCrawler
from bs4 import BeautifulSoup
import logging
import re

logger = logging.getLogger("FivePaisaCrawler")

class FivePaisaCrawler(BaseCrawler):
    def __init__(self, source_id: str, base_url: str, rate_limit: int, robots_url: str = None):
        super().__init__(source_id, base_url, rate_limit, robots_url)

    async def crawl_recommendations(self):
        html = await self.fetch(self.base_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "lxml")
        recommendations = []
        
        # Based on inspection, recommendations are in table#stock-table
        table = soup.select_one("table#stock-table")
        if not table:
            # Fallback to any table if ID not found
            table = soup.find("table")
            
        if not table:
            logger.warning("No table found on 5paisa recommendation page")
            return []

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 6:
                continue
                
            # Column 6 has the Buy button with the symbol in data-redirect-path
            buy_btn = cells[5].find("a", class_="stock-buy-btn")
            symbol = None
            if buy_btn and buy_btn.get("data-redirect-path"):
                redirect_path = buy_btn["data-redirect-path"]
                # Extract symbol parameter: ...&symbol=BHEL
                match = re.search(r"symbol=([^&]+)", redirect_path)
                if match:
                    symbol = match.group(1).upper()
            
            if not symbol:
                # Fallback to column 1 text if button logic fails
                symbol_text = cells[0].get_text(strip=True)
                # Simple heuristic: often symbols are in parentheses or first word
                symbol = symbol_text.split()[0].upper()

            try:
                entry = float(cells[1].get_text(strip=True))
                sl = float(cells[2].get_text(strip=True))
                target1 = float(cells[3].get_text(strip=True))
                target2 = float(cells[4].get_text(strip=True))
                action = cells[5].get_text(strip=True)
            except (ValueError, IndexError) as e:
                logger.debug(f"Skipping row due to parsing error: {e}")
                continue

            recommendations.append({
                "symbol": symbol,
                "entry": entry,
                "sl": sl,
                "target1": target1,
                "target2": target2,
                "action": action,
                "content": f"5paisa recommends {action} for {symbol}. Entry: {entry}, SL: {sl}, Target 1: {target1}, Target 2: {target2}."
            })
            
        return recommendations
