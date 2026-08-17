import logging
import os
import sqlite3
from typing import Dict, List, Set, Any, Optional

logger = logging.getLogger(__name__)


class Database:
    """Manages SQLite persistence for seen releases and subscriber chat IDs."""

    def __init__(self, db_path: str = "data/releases.db"):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        """Creates the parent directory for SQLite database if missing."""
        dir_name = os.path.dirname(self.db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a database connection with dictionary row formatting."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes database schema tables for seen releases and subscribers with automatic migration."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Migrate legacy columns if present
            cursor.execute("PRAGMA table_info(seen_releases)")
            cols = [row[1] for row in cursor.fetchall()]
            if cols and "id" in cols and "release_id" not in cols:
                logger.info("Migrating seen_releases schema: renaming column 'id' to 'release_id'")
                cursor.execute("ALTER TABLE seen_releases RENAME COLUMN id TO release_id")
                conn.commit()

            if cols and "first_seen_at" in cols and "created_at" not in cols:
                logger.info("Migrating seen_releases schema: renaming column 'first_seen_at' to 'created_at'")
                cursor.execute("ALTER TABLE seen_releases RENAME COLUMN first_seen_at TO created_at")
                conn.commit()
            elif cols and "created_at" not in cols and "first_seen_at" not in cols:
                logger.info("Migrating seen_releases schema: adding column 'created_at'")
                cursor.execute("ALTER TABLE seen_releases ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                conn.commit()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_releases (
                    release_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    os_type TEXT NOT NULL,
                    build TEXT,
                    release_type TEXT,
                    link TEXT,
                    pub_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    chat_id TEXT PRIMARY KEY,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def is_release_seen(self, release_id: str) -> bool:
        """Checks if a release ID is already recorded in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_releases WHERE release_id = ?", (release_id,))
            return cursor.fetchone() is not None

    def add_seen_release(
        self,
        release_id: str,
        title: str,
        os_type: str,
        build: Optional[str] = None,
        release_type: Optional[str] = None,
        link: Optional[str] = None,
        pub_date: Optional[str] = None
    ) -> bool:
        """Inserts a new release into database. Returns True if inserted, False if already seen."""
        if self.is_release_seen(release_id):
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO seen_releases (release_id, title, os_type, build, release_type, link, pub_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (release_id, title, os_type, build, release_type, link, pub_date))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_recent_releases(self, target_os: Optional[Set[str]] = None, limit_per_os: int = 2) -> List[Dict[str, Any]]:
        """Returns recent releases partitioned per target OS platform."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                WITH RankedReleases AS (
                    SELECT 
                        release_id, title, os_type, build, release_type, link, pub_date, created_at, rowid,
                        ROW_NUMBER() OVER (PARTITION BY LOWER(os_type) ORDER BY rowid DESC) as rank
                    FROM seen_releases
                )
                SELECT release_id, title, os_type, build, release_type, link, pub_date, created_at
                FROM RankedReleases
                WHERE rank <= ?
            """
            params: List[Any] = [limit_per_os]

            if target_os:
                target_os_lower = [o.lower() for o in target_os]
                placeholders = ",".join(["?"] * len(target_os_lower))
                query += f" AND LOWER(os_type) IN ({placeholders})"
                params.extend(target_os_lower)

            query += " ORDER BY rowid DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def add_subscriber(self, chat_id: str) -> bool:
        """Adds a subscriber chat_id. Returns True if added, False if already subscribed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO subscribers (chat_id) VALUES (?)", (str(chat_id),))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def remove_subscriber(self, chat_id: str) -> bool:
        """Removes a subscriber chat_id. Returns True if removed, False if not present."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscribers WHERE chat_id = ?", (str(chat_id),))
            conn.commit()
            return cursor.rowcount > 0

    def get_subscribers(self) -> List[str]:
        """Returns a list of all subscriber chat IDs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id FROM subscribers")
            rows = cursor.fetchall()
            return [row["chat_id"] for row in rows]

    def get_stats(self) -> Dict[str, int]:
        """Returns general statistics on total recorded releases and subscribers."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM seen_releases")
            total_releases = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM subscribers")
            total_subscribers = cursor.fetchone()["cnt"]

            return {
                "total_releases": total_releases,
                "total_subscribers": total_subscribers
            }
