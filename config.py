import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Polling frequency in seconds (default 300s = 5 min)
    CHECK_INTERVAL_SECONDS: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
    
    # Database path
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/releases.db")
    
    # Target OS platforms to monitor (comma-separated: iOS, macOS, iPadOS, watchOS, visionOS, tvOS, Xcode)
    _target_os_raw: str = os.getenv("TARGET_OS", "iOS, macOS")
    TARGET_OS: set[str] = {item.strip().lower() for item in _target_os_raw.split(",") if item.strip()}
    
    # Release channel filters
    INCLUDE_DEV_BETAS: bool = os.getenv("INCLUDE_DEV_BETAS", "true").lower() in ("true", "1", "yes")
    INCLUDE_PUBLIC_BETAS: bool = os.getenv("INCLUDE_PUBLIC_BETAS", "true").lower() in ("true", "1", "yes")
    INCLUDE_STABLE: bool = os.getenv("INCLUDE_STABLE", "true").lower() in ("true", "1", "yes")

    @classmethod
    def validate(cls) -> list[str]:
        """Validates configuration parameters and returns a list of warnings or errors."""
        errors = []
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is missing! Set it in your environment or .env file.")
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID is missing! Set it to your Telegram chat/channel ID to receive automatic alerts.")
        return errors

    @classmethod
    def ensure_data_dir(cls):
        """Ensures the parent directory for the database file exists."""
        db_path = Path(cls.DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
