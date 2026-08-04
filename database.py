import sqlite3
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creates required SQLite tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Seen releases table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_releases (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    os_type TEXT NOT NULL,
                    build TEXT,
                    release_type TEXT,
                    link TEXT,
                    pub_date TEXT,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Subscribed chats table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    chat_id TEXT PRIMARY KEY,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info("Database initialized at %s", self.db_path)

    def is_release_seen(self, release_id: str) -> bool:
        """Check if a release ID has already been recorded."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_releases WHERE id = ?", (release_id,))
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
        """Records a new release in the database. Returns True if inserted, False if already exists."""
        if self.is_release_seen(release_id):
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO seen_releases (id, title, os_type, build, release_type, link, pub_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (release_id, title, os_type, build or "", release_type or "Unknown", link or "", pub_date or "")
            )
            conn.commit()
            return True

    def get_recent_releases(self, limit: int = 10, os_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch recently detected releases."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if os_filter:
                cursor.execute(
                    "SELECT * FROM seen_releases WHERE LOWER(os_type) = LOWER(?) ORDER BY first_seen_at DESC LIMIT ?",
                    (os_filter, limit)
                )
            else:
                cursor.execute("SELECT * FROM seen_releases ORDER BY first_seen_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def add_subscriber(self, chat_id: str) -> bool:
        """Add a Telegram chat ID to the subscribers list."""
        chat_id_str = str(chat_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO subscribers (chat_id) VALUES (?)", (chat_id_str,))
            changed = cursor.rowcount > 0
            conn.commit()
            return changed

    def remove_subscriber(self, chat_id: str) -> bool:
        """Remove a Telegram chat ID from the subscribers list."""
        chat_id_str = str(chat_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscribers WHERE chat_id = ?", (chat_id_str,))
            changed = cursor.rowcount > 0
            conn.commit()
            return changed

    def get_subscribers(self) -> List[str]:
        """Get all subscribed chat IDs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id FROM subscribers")
            return [row["chat_id"] for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistics about recorded releases and subscribers."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM seen_releases")
            total_releases = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as total FROM subscribers")
            total_subscribers = cursor.fetchone()["total"]

            cursor.execute("SELECT os_type, COUNT(*) as count FROM seen_releases GROUP BY os_type")
            by_os = {row["os_type"]: row["count"] for row in cursor.fetchall()}

            return {
                "total_releases": total_releases,
                "total_subscribers": total_subscribers,
                "releases_by_os": by_os
            }
