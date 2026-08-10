import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from config import Config
from monitor import ReleaseMonitor
from database import Database

async def test_detection():
    print("=" * 70)
    print(" 🧪 APPLE OS RELEASE DETECTION TEST (DRY RUN)")
    print("=" * 70)
    print(f"Monitored OS Platforms: {', '.join(Config.TARGET_OS).upper()}")
    print(f"Filters -> Dev Betas: {Config.INCLUDE_DEV_BETAS} | Public Betas: {Config.INCLUDE_PUBLIC_BETAS} | Stable: {Config.INCLUDE_STABLE}")
    print("=" * 70 + "\n")

    monitor = ReleaseMonitor(
        target_os=Config.TARGET_OS,
        include_dev=Config.INCLUDE_DEV_BETAS,
        include_public=Config.INCLUDE_PUBLIC_BETAS,
        include_stable=Config.INCLUDE_STABLE
    )

    print("Fetching Apple Developer RSS Feed...")
    items = await monitor.check_all_feeds()
    print(f"✓ Found {len(items)} matching release(s) for your target platforms!\n")

    if not items:
        print("No releases matched your current filters.")
        return

    print("Detected Releases Details:")
    print("-" * 70)

    for idx, item in enumerate(items, 1):
        build_info = f" (Build: {item.build})" if item.build else ""
        print(f"[{idx}] {item.os_type} - {item.title}")
        print(f"    • Release Type : {item.release_type}")
        print(f"    • Build Number : {item.build or 'N/A'}")
        print(f"    • Published    : {item.pub_date or 'N/A'}")
        print(f"    • Link         : {item.link}")
        print("-" * 70)

    print("\nDatabase Status:")
    db = Database(Config.DATABASE_PATH)
    stats = db.get_stats()
    print(f"• Total Recorded Releases in DB: {stats['total_releases']}")
    print(f"• Total Subscribers in DB       : {stats['total_subscribers']} (Channel posting disabled)")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_detection())
