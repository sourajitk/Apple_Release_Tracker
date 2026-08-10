import logging
import re
from typing import List, Dict, Any
import httpx
import feedparser

logger = logging.getLogger(__name__)


class AppleDevScraper:
    """Scrapes release announcements directly from developer.apple.com feeds."""

    APPLE_DEVELOPER_RSS = "https://developer.apple.com/news/releases/rss/releases.rss"
    APPLE_DEVELOPER_HTML = "https://developer.apple.com/news/releases/"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def fetch_rss_feed(self) -> List[Dict[str, Any]]:
        """Fetches and parses the official Apple Developer RSS release feed."""
        raw_items: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(self.APPLE_DEVELOPER_RSS, headers=self.headers)
                response.raise_for_status()

                feed = feedparser.parse(response.content)
                for entry in feed.entries:
                    title = getattr(entry, 'title', '').strip()
                    if not title:
                        continue

                    guid = getattr(entry, 'id', getattr(entry, 'link', title))
                    link = getattr(entry, 'link', 'https://developer.apple.com/news/releases/')
                    pub_date = getattr(entry, 'published', '')

                    raw_items.append({
                        "id": guid,
                        "title": title,
                        "link": link,
                        "pub_date": pub_date
                    })
        except Exception as e:
            logger.error("Error fetching RSS feed %s: %s", self.APPLE_DEVELOPER_RSS, e)

        return raw_items

    async def fetch_html_feed(self) -> List[Dict[str, Any]]:
        """Scrapes the live HTML news releases page for zero-delay instant detection."""
        raw_items: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(self.APPLE_DEVELOPER_HTML, headers=self.headers)
                response.raise_for_status()

                matches = re.findall(
                    r'data-href=[\"\'](https://developer\.apple\.com/news/releases/\?id=[^\"\']+)[\"\'][^>]*data-title=[\"\']([^\"\']+)[\"\']',
                    response.text
                )
                for link, raw_title in matches:
                    title = raw_title.replace(" - Releases - Apple Developer", "").strip()
                    if not title:
                        continue

                    raw_items.append({
                        "id": link,
                        "title": title,
                        "link": link,
                        "pub_date": ""
                    })
        except Exception as e:
            logger.error("Error fetching HTML feed %s: %s", self.APPLE_DEVELOPER_HTML, e)

        return raw_items
