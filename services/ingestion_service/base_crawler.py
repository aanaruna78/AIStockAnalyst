import httpx
import asyncio
from typing import Optional
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
import time
from fake_useragent import UserAgent
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BaseCrawler")

class BaseCrawler:
    def __init__(self, source_id: str, base_url: str, rate_limit: int, robots_url: Optional[str] = None):
        self.source_id = source_id
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.robots_url = robots_url
        self.rp = None
        self.ua = UserAgent()
        self.last_request_time = 0
        
        if self.robots_url:
            self.rp = RobotFileParser()
            self.rp.set_url(self.robots_url)
            try:
                self.rp.read()
            except Exception as e:
                logger.error(f"Failed to read robots.txt for {self.source_id}: {e}")

    def is_allowed(self, url: str) -> bool:
        if not self.rp:
            return True
        return self.rp.can_fetch("SignalForgeBot", url)

    async def fetch(self, url: str) -> Optional[str]:
        if not self.is_allowed(url):
            logger.warning(f"Crawling disallowed by robots.txt: {url}")
            return None

        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)

        headers = {"User-Agent": self.ua.random}
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers, timeout=10.0)
                self.last_request_time = time.time()
                response.raise_for_status()
                return response.text
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                return None

    def extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        # Remove scripts, styles, ads if common selectors are known
        for script_or_style in soup(["script", "style", "header", "footer", "nav"]):
            script_or_style.decompose()
        return soup.get_text(separator=" ", strip=True)
