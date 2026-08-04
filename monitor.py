import re
import logging
from dataclasses import dataclass
from typing import List, Optional
import httpx
import feedparser

logger = logging.getLogger(__name__)

APPLE_DEVELOPER_RSS = "https://developer.apple.com/news/releases/rss/releases.rss"

@dataclass
class ReleaseItem:
    id: str
    title: str
    os_type: str
    version: str
    build: Optional[str]
    release_type: str  # Developer Beta, Public Beta, Release Candidate, Official Release
    link: str
    pub_date: str

class ReleaseMonitor:
    def __init__(self, target_os: set[str], include_dev: bool = True, include_public: bool = True, include_stable: bool = True):
        self.target_os = {os_name.lower() for os_name in target_os}
        self.include_dev = include_dev
        self.include_public = include_public
        self.include_stable = include_stable

    def parse_title(self, title: str) -> tuple[str, str, Optional[str], str]:
        """
        Parses a release title to extract: (os_type, version, build, release_type)
        Example titles:
        - "iOS 18.2 beta 2 (22C5125e)"
        - "macOS 15.1 Beta (24B5009l)"
        - "iOS 18.2 Public Beta"
        - "macOS 15.0 (24A335)"
        """
        # Detect OS Type
        os_type = "Unknown"
        os_match = re.search(r'\b(iOS|macOS|iPadOS|watchOS|visionOS|tvOS|Xcode|audioOS)\b', title, re.IGNORECASE)
        if os_match:
            # Standardize casing (e.g. iOS, macOS, iPadOS)
            matched_raw = os_match.group(1).lower()
            mapping = {
                "ios": "iOS",
                "macos": "macOS",
                "ipados": "iPadOS",
                "watchos": "watchOS",
                "visionos": "visionOS",
                "tvos": "tvOS",
                "xcode": "Xcode",
                "audioos": "audioOS"
            }
            os_type = mapping.get(matched_raw, os_match.group(1))

        # Detect Release Type
        lower_title = title.lower()
        if "public beta" in lower_title:
            release_type = "Public Beta"
        elif "beta" in lower_title:
            release_type = "Developer Beta"
        elif "release candidate" in lower_title or " rc" in lower_title:
            release_type = "Release Candidate"
        else:
            release_type = "Official Release"

        # Extract Build Number (e.g. 22C5125e inside parentheses)
        build_match = re.search(r'\(([A-Za-z0-9]+)\)', title)
        build = build_match.group(1) if build_match else None

        # Extract Version Number (e.g. 18.2, 15.1, 26.6)
        version_match = re.search(r'\b\d+(?:\.\d+)*(?:\s+beta\s+\d+)?\b', title, re.IGNORECASE)
        version = version_match.group(0) if version_match else ""

        return os_type, version, build, release_type

    def is_matching_release(self, os_type: str, release_type: str) -> bool:
        """Filters releases based on target OS and enabled channels."""
        if os_type.lower() not in self.target_os:
            return False

        if release_type == "Developer Beta" and not self.include_dev:
            return False
        if release_type == "Public Beta" and not self.include_public:
            return False
        if release_type in ("Official Release", "Release Candidate") and not self.include_stable:
            return False

        return True

    async def fetch_rss_feed(self, url: str) -> List[ReleaseItem]:
        """Fetches and parses an RSS feed using httpx and feedparser."""
        items: List[ReleaseItem] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                feed_data = feedparser.parse(response.content)

                for entry in feed_data.entries:
                    title = entry.get("title", "").strip()
                    if not title:
                        continue

                    guid = entry.get("id") or entry.get("guid") or entry.get("link") or title
                    link = entry.get("link", "https://developer.apple.com/news/releases/")
                    pub_date = entry.get("published", entry.get("updated", ""))

                    os_type, version, build, release_type = self.parse_title(title)

                    if self.is_matching_release(os_type, release_type):
                        items.append(
                            ReleaseItem(
                                id=str(guid),
                                title=title,
                                os_type=os_type,
                                version=version,
                                build=build,
                                release_type=release_type,
                                link=link,
                                pub_date=pub_date
                            )
                        )
        except Exception as e:
            logger.error("Error fetching RSS feed %s: %s", url, e)

        return items

    async def check_all_feeds(self) -> List[ReleaseItem]:
        """Checks configured release feeds and returns matching releases."""
        # Primary Feed: Apple Developer Releases
        releases = await self.fetch_rss_feed(APPLE_DEVELOPER_RSS)
        
        # Deduplicate by GUID / ID
        seen_ids = set()
        unique_releases: List[ReleaseItem] = []
        for rel in releases:
            if rel.id not in seen_ids:
                seen_ids.add(rel.id)
                unique_releases.append(rel)

        return unique_releases
