import re
from typing import Optional, Tuple


class ReleaseParser:
    """Parses release titles to extract OS type, version, build number, and release channel."""

    SUPPORTED_OS_PLATFORMS = ("iOS", "macOS", "iPadOS", "watchOS", "visionOS", "tvOS", "Xcode")

    @classmethod
    def parse_title(cls, title: str) -> Tuple[str, str, Optional[str], str]:
        """
        Extracts (os_type, version, build, release_type) from a title string.
        Examples:
        - "iOS 18.2 beta 2 (22C5125e)" -> ("iOS", "18.2 beta 2", "22C5125e", "Developer Beta")
        - "macOS 15.1 RC (24B82)" -> ("macOS", "15.1 RC", "24B82", "Release Candidate")
        - "watchOS 11.1 (22R582)" -> ("watchOS", "11.1", "22R582", "Official Release")
        """
        clean_title = title.strip()

        os_type = "Unknown"
        for os_name in cls.SUPPORTED_OS_PLATFORMS:
            if os_name.lower() in clean_title.lower():
                os_type = os_name
                break

        build = None
        build_match = re.search(r'\(([^)]+)\)', clean_title)
        if build_match:
            candidate_build = build_match.group(1).strip()
            if candidate_build.isalnum() and len(candidate_build) >= 4:
                build = candidate_build

        release_type = "Official Release"
        title_lower = clean_title.lower()

        if "public beta" in title_lower:
            release_type = "Public Beta"
        elif "beta" in title_lower:
            release_type = "Developer Beta"
        elif "rc" in title_lower or "release candidate" in title_lower:
            release_type = "Release Candidate"

        version_part = re.sub(r'\([^)]*\)', '', clean_title).strip()
        if os_type != "Unknown":
            pattern = re.compile(re.escape(os_type), re.IGNORECASE)
            version_part = pattern.sub('', version_part).strip()

        version = version_part if version_part else "1.0"

        return os_type, version, build, release_type
