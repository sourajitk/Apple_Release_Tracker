import sys
import unittest
import os
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
import email.utils

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from config import Config
from models import ReleaseItem
from parser import ReleaseParser
from monitor import ReleaseMonitor
from database import Database
from bot import format_release_message, is_recent_release


class TestReleaseParser(unittest.TestCase):
    def test_parse_developer_beta(self):
        os_type, version, build, rel_type = ReleaseParser.parse_title("iOS 27.0 beta 4 (24A5390f)")
        self.assertEqual(os_type, "iOS")
        self.assertEqual(build, "24A5390f")
        self.assertEqual(rel_type, "Developer Beta")

    def test_parse_public_beta(self):
        os_type, version, build, rel_type = ReleaseParser.parse_title("iOS 18.2 Public Beta 2")
        self.assertEqual(os_type, "iOS")
        self.assertEqual(rel_type, "Public Beta")

    def test_parse_release_candidate(self):
        os_type, version, build, rel_type = ReleaseParser.parse_title("iOS 26.5 RC 2 (23F77)")
        self.assertEqual(os_type, "iOS")
        self.assertEqual(build, "23F77")
        self.assertEqual(rel_type, "Release Candidate")

    def test_parse_official_release(self):
        os_type, version, build, rel_type = ReleaseParser.parse_title("macOS 26.6 (25G72)")
        self.assertEqual(os_type, "macOS")
        self.assertEqual(build, "25G72")
        self.assertEqual(rel_type, "Official Release")


class TestReleaseMonitorFiltering(unittest.TestCase):
    def setUp(self):
        self.monitor = ReleaseMonitor(
            target_os={"ios", "macos"},
            include_dev=True,
            include_public=True,
            include_stable=True
        )

    def test_os_filtering(self):
        self.assertTrue(self.monitor.is_matching_release("iOS", "Developer Beta"))
        self.assertTrue(self.monitor.is_matching_release("macOS", "Official Release"))
        self.assertFalse(self.monitor.is_matching_release("watchOS", "Official Release"))
        self.assertFalse(self.monitor.is_matching_release("tvOS", "Developer Beta"))

    def test_channel_filtering(self):
        stable_only_monitor = ReleaseMonitor(
            target_os={"ios"},
            include_dev=False,
            include_public=False,
            include_stable=True
        )
        self.assertTrue(stable_only_monitor.is_matching_release("iOS", "Official Release"))
        self.assertTrue(stable_only_monitor.is_matching_release("iOS", "Release Candidate"))
        self.assertFalse(stable_only_monitor.is_matching_release("iOS", "Developer Beta"))


class TestDatabaseLayer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_releases.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_add_and_check_seen_release(self):
        release_id = "test-id-123"
        self.assertFalse(self.db.is_release_seen(release_id))

        inserted = self.db.add_seen_release(
            release_id=release_id,
            title="iOS 27.0 beta 4",
            os_type="iOS",
            build="24A5390f",
            release_type="Developer Beta",
            link="https://developer.apple.com/",
            pub_date="Mon, 20 Jul 2026 10:00:00 PDT"
        )
        self.assertTrue(inserted)
        self.assertTrue(self.db.is_release_seen(release_id))

        duplicate_inserted = self.db.add_seen_release(
            release_id=release_id,
            title="iOS 27.0 beta 4",
            os_type="iOS"
        )
        self.assertFalse(duplicate_inserted)

    def test_get_recent_releases_partitioning(self):
        self.db.add_seen_release("id-1", "iOS 26.6", "iOS")
        self.db.add_seen_release("id-2", "macOS 26.6", "macOS")
        self.db.add_seen_release("id-3", "watchOS 26.6", "watchOS")
        self.db.add_seen_release("id-4", "tvOS 26.6", "tvOS")

        recent = self.db.get_recent_releases(target_os={"ios", "macos"}, limit_per_os=2)
        os_types = {r["os_type"] for r in recent}

        self.assertIn("iOS", os_types)
        self.assertIn("macOS", os_types)
        self.assertNotIn("watchOS", os_types)
        self.assertNotIn("tvOS", os_types)

    def test_subscriber_management(self):
        chat_id = "-100123456789"
        self.assertTrue(self.db.add_subscriber(chat_id))
        self.assertIn(chat_id, self.db.get_subscribers())
        self.assertFalse(self.db.add_subscriber(chat_id))
        self.assertTrue(self.db.remove_subscriber(chat_id))
        self.assertNotIn(chat_id, self.db.get_subscribers())


class TestBotServiceHelpers(unittest.TestCase):
    def test_is_recent_release(self):
        now_utc = datetime.now(timezone.utc)
        recent_date_str = email.utils.format_datetime(now_utc - timedelta(hours=5))
        old_date_str = email.utils.format_datetime(now_utc - timedelta(days=10))

        self.assertTrue(is_recent_release(recent_date_str, max_age_days=3.0))
        self.assertFalse(is_recent_release(old_date_str, max_age_days=3.0))

    def test_format_release_message(self):
        item = ReleaseItem(
            id="test-1",
            title="iOS 27.0 beta 4 (24A5390f)",
            os_type="iOS",
            version="27.0 beta 4",
            build="24A5390f",
            release_type="Developer Beta",
            link="https://developer.apple.com/",
            pub_date="Mon, 20 Jul 2026 10:00:00 PDT"
        )
        msg = format_release_message(item)
        self.assertIn("New Apple Release Detected!", msg)
        self.assertIn("iOS 27.0 beta 4", msg)
        self.assertIn("24A5390f", msg)
        self.assertIn("Developer Beta", msg)


if __name__ == "__main__":
    unittest.main()
