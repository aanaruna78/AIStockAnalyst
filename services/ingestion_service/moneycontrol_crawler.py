from base_crawler import BaseCrawler
import logging
import httpx
import re

logger = logging.getLogger("MoneycontrolCrawler")

# Common Moneycontrol name → NSE symbol mappings for names that don't trivially normalize
MC_SYMBOL_MAP = {
    "HDFC BANK": "HDFCBANK",
    "ICICI BANK": "ICICIBANK",
    "AXIS BANK": "AXISBANK",
    "STATE BANK": "SBIN",
    "SBI": "SBIN",
    "KOTAK MAHINDRA": "KOTAKBANK",
    "KOTAK BANK": "KOTAKBANK",
    "INDUSIND BANK": "INDUSINDBK",
    "BAJAJ FINANCE": "BAJFINANCE",
    "BAJAJ FINSERV": "BAJAJFINSV",
    "MAHINDRA & MAHINDRA": "M&M",
    "M&M": "M&M",
    "TATA MOTORS": "TATAMOTORS",
    "TATA STEEL": "TATASTEEL",
    "TATA POWER": "TATAPOWER",
    "TATA CONSULTANCY": "TCS",
    "TCS": "TCS",
    "RELIANCE": "RELIANCE",
    "INFOSYS": "INFY",
    "WIPRO": "WIPRO",
    "HCL TECH": "HCLTECH",
    "HCL TECHNOLOGIES": "HCLTECH",
    "TECH MAHINDRA": "TECHM",
    "L&T": "LT",
    "LARSEN": "LT",
    "ADANI PORTS": "ADANIPORTS",
    "ADANI ENTERPRISES": "ADANIENT",
    "POWER GRID": "POWERGRID",
    "NTPC": "NTPC",
    "SUN PHARMA": "SUNPHARMA",
    "DR REDDY": "DRREDDY",
    "DIVI'S LAB": "DIVISLAB",
    "DIVIS LAB": "DIVISLAB",
    "ULTRA CEMENT": "ULTRACEMCO",
    "ULTRATECH CEMENT": "ULTRACEMCO",
    "ASIAN PAINTS": "ASIANPAINT",
    "BRITANNIA": "BRITANNIA",
    "NESTLE": "NESTLEIND",
    "HINDALCO": "HINDALCO",
    "JSW STEEL": "JSWSTEEL",
    "MARUTI": "MARUTI",
    "HERO MOTO": "HEROMOTOCO",
    "EICHER MOTORS": "EICHERMOT",
    "BHARTI AIRTEL": "BHARTIARTL",
    "ITC": "ITC",
    "COAL INDIA": "COALINDIA",
    "GRASIM": "GRASIM",
    "CIPLA": "CIPLA",
    "APOLLO HOSPITALS": "APOLLOHOSP",
    "ZOMATO": "ETERNAL",
}

class MoneycontrolCrawler(BaseCrawler):
    def __init__(self, source_id: str, base_url: str, rate_limit: int, robots_url: str = None):
        super().__init__(source_id, base_url, rate_limit, robots_url)

    def _resolve_symbol(self, stock_name: str, stock_short: str) -> str:
        """Resolve Moneycontrol stock name to NSE symbol using mapping + heuristics."""
        # Try the short name first (most reliable)
        if stock_short:
            short_upper = stock_short.upper().strip()
            # Direct mapping check
            if short_upper in MC_SYMBOL_MAP:
                return MC_SYMBOL_MAP[short_upper]
            # If short name looks like a clean ticker already (no spaces), use it
            if " " not in short_upper and len(short_upper) <= 15:
                return short_upper
        
        # Try full name mapping
        if stock_name:
            name_upper = stock_name.upper().strip()
            # Check against mapping (exact and prefix)
            for mc_name, nse_sym in MC_SYMBOL_MAP.items():
                if mc_name in name_upper or name_upper.startswith(mc_name):
                    return nse_sym

            # Fallback: remove common suffixes and spaces
            cleaned = re.sub(r'\b(LIMITED|LTD|CORPORATION|CORP|INDUSTRIES|IND)\b', '', name_upper)
            cleaned = re.sub(r'[^A-Z0-9&]', '', cleaned).strip()
            if cleaned:
                return cleaned
        
        return "UNKNOWN"

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
                
                # Resolve to NSE symbol using mapping + heuristics
                symbol = self._resolve_symbol(stock_name, stock_short)

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
