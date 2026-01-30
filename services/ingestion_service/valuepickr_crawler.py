from base_crawler import BaseCrawler
from bs4 import BeautifulSoup
import logging
from typing import Optional

logger = logging.getLogger("ValuePickrCrawler")

class ValuePickrCrawler(BaseCrawler):
    def __init__(self, source_id: str, base_url: str, rate_limit: int, robots_url: Optional[str] = None):
        super().__init__(source_id, base_url, rate_limit, robots_url)

    async def crawl_thread(self, thread_url: str):
        html = await self.fetch(thread_url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, "lxml")
        posts = []
        # ValuePickr uses discourse, posts are usually in .topic-post
        post_elements = soup.select(".topic-post")
        for post in post_elements:
            content = post.select_one(".cooked")
            if content:
                posts.append(content.get_text(separator=" ", strip=True))
        
        return posts
