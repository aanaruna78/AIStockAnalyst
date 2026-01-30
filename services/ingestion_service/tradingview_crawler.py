from base_crawler import BaseCrawler
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger("TradingViewCrawler")

class TradingViewCrawler(BaseCrawler):
    def __init__(self, source_id: str, base_url: str, rate_limit: int, robots_url: str):
        super().__init__(source_id, base_url, rate_limit, robots_url)

    async def crawl_ideas(self, symbol: str):
        url = f"{self.base_url}/ideas/{symbol.lower()}/"
        html = await self.fetch(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, "lxml")
        ideas = []
        # TradingView public ideas are usually in .tv-feed-item or similar
        idea_cards = soup.select(".tv-feed-item")
        for card in idea_cards:
            title = card.select_one(".tv-widget-idea__title")
            description = card.select_one(".tv-widget-idea__description-text")
            if title and description:
                ideas.append({
                    "title": title.get_text(strip=True),
                    "body": description.get_text(strip=True)
                })
        
        return ideas
