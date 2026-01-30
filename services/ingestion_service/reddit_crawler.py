from base_crawler import BaseCrawler
from bs4 import BeautifulSoup
import logging
from typing import Optional

logger = logging.getLogger("RedditCrawler")

class RedditCrawler(BaseCrawler):
    def __init__(self, source_id: str, base_url: str, rate_limit: int, robots_url: Optional[str] = None):
        # Reddit robots.txt is complex, usually we'd use an API but this is for public HTML
        super().__init__(source_id, base_url, rate_limit, robots_url)

    async def crawl_subreddit(self, subreddit_url: str):
        # Appending .rss or just using public HTML (simple approach here)
        html = await self.fetch(subreddit_url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, "lxml")
        threads = []
        # Reddit (new UI) post selectors
        post_elements = soup.select("shreddit-post")
        for post in post_elements:
            # Try attribute first
            title = post.get("post-title")
            if not title:
                # Try internal link
                title_link = post.select_one('a[id^="post-title-"]')
                if title_link:
                    title = title_link.get_text(strip=True)
            
            content = post.get_text(separator=" ", strip=True) 
            if title:
                threads.append({
                    "title": title,
                    "content": content
                })
        
        return threads
