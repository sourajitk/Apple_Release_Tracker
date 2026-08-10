import logging
import sys

from config import Config
from database import Database
from monitor import ReleaseMonitor
from bot import TelegramBotService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Main application entry point."""
    logger.info("Starting Apple OS Release Tracker Bot...")

    errors = Config.validate()
    if errors:
        for err in errors:
            logger.error("Configuration Error: %s", err)
        sys.exit(1)

    db = Database(Config.DATABASE_PATH)

    monitor = ReleaseMonitor(
        target_os=Config.TARGET_OS,
        include_dev=Config.INCLUDE_DEV_BETAS,
        include_public=Config.INCLUDE_PUBLIC_BETAS,
        include_stable=Config.INCLUDE_STABLE
    )

    bot_service = TelegramBotService(Config, db, monitor)
    app = bot_service.setup_app()

    logger.info("Bot service initialized. Starting Telegram polling loop...")
    app.run_polling()


if __name__ == "__main__":
    main()
