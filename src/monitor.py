import logging
from typing import List, Set

from models import ReleaseItem
from parser import ReleaseParser
from scraper import AppleDevScraper

logger = logging.getLogger(__name__)


class ReleaseMonitor:
    """Orchestrates scraping, parsing, and filtering Apple OS releases."""

    def __init__(
        self,
        target_os: Set[str],
        include_dev: bool = True,
        include_public: bool = True,
        include_stable: bool = True
    ):
        self.target_os = {os_name.lower() for os_name in target_os}
        self.include_dev = include_dev
        self.include_public = include_public
        self.include_stable = include_stable

        self.scraper = AppleDevScraper()
        self.parser = ReleaseParser()

    def is_matching_release(self, os_type: str, release_type: str) -> bool:
        """Evaluates whether a release matches configured target platforms and channel filters."""
        if os_type.lower() not in self.target_os:
            return False

        if release_type == "Developer Beta" and not self.include_dev:
            return False
        if release_type == "Public Beta" and not self.include_public:
            return False
        if release_type in ("Official Release", "Release Candidate") and not self.include_stable:
            return False

        return True

    async def check_all_feeds(self) -> List[ReleaseItem]:
        """Polls developer.apple.com feeds, parses entries, and returns deduplicated matching releases."""
        raw_items: List[dict] = []

        # 1. Fetch RSS feed items
        rss_items = await self.scraper.fetch_rss_feed()
        raw_items.extend(rss_items)

        # 2. Fetch HTML releases page items for instant zero-delay detection
        html_items = await self.scraper.fetch_html_feed()
        raw_items.extend(html_items)

        # Parse, filter, and deduplicate
        seen_ids: Set[str] = set()
        matched_releases: List[ReleaseItem] = []

        for item in raw_items:
            item_id = item["id"]
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            title = item["title"]
            os_type, version, build, release_type = self.parser.parse_title(title)

            if self.is_matching_release(os_type, release_type):
                matched_releases.append(
                    ReleaseItem(
                        id=item_id,
                        title=title,
                        os_type=os_type,
                        version=version,
                        build=build,
                        release_type=release_type,
                        link=item["link"],
                        pub_date=item["pub_date"]
                    )
                )

        return matched_releases
