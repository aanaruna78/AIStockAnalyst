from base_crawler import BaseCrawler
import logging
import httpx

logger = logging.getLogger("MoneycontrolCrawler")

class MoneycontrolCrawler(BaseCrawler):
    def __init__(self, source_id: str, base_url: str, rate_limit: int, robots_url: str = None):
        super().__init__(source_id, base_url, rate_limit, robots_url)

    async def crawl_recommendations(self):
        # Use the JSON API identified in analysis
        api_url = "https://api.moneycontrol.com/mcapi/v1/broker-research/stock-ideas?start=0&limit=50&deviceType=W"
        
        json_data = None
        try:
            headers = {"User-Agent": self.ua.random}
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, headers=headers, timeout=10.0)
                if response.status_code == 200:
                    json_data = response.json()
        except Exception as e:
            logger.error(f"Error fetching Moneycontrol API: {e}")
            return []

        if not json_data or "data" not in json_data:
            logger.warning("Invalid JSON response from Moneycontrol API")
            return []
        
        recommendations = []
        for item in json_data["data"]:
            try:
                # 1. Stock & Symbol (Moneycontrol stkname is full name)
                stock_name = item.get("stkname", "")
                stock_short = item.get("stockShortName", "")
                
                # Safe symbol extraction
                if stock_short:
                    symbol = stock_short.upper().replace(" ", "")
                elif stock_name:
                    name_parts = stock_name.upper().split()
                    symbol = name_parts[0] if name_parts else "UNKNOWN"
                else:
                    symbol = "UNKNOWN"

                # 2. Action
                action = item.get("recommend_flag", "NEUTRAL").upper()

                # 3. Analyst
                analyst = item.get("organization", "Unknown Analyst")

                # 4. Target
                target = 0.0
                try:
                    target = float(item.get("target_price", 0))
                except (ValueError, TypeError):
                    pass

                # 5. Date
                date_txt = item.get("recommend_date", "Recently")

                recommendations.append({
                    "symbol": symbol,
                    "action": action,
                    "analyst": analyst,
                    "target": target,
                    "date": date_txt,
                    "content": item.get("heading") or f"Moneycontrol reports {action} for {stock_name} by {analyst} on {date_txt} with target {target}."
                })
            except Exception as e:
                logger.error(f"Error processing Moneycontrol API item: {e}")
                continue
            
        return recommendations
