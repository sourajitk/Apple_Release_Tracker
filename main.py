import logging
import sys
import asyncio
from config import Config
from database import Database
from monitor import ReleaseMonitor
from bot import TelegramBotService

# Configure logging format
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Apple iOS & macOS Beta Release Telegram Bot...")

    # Ensure configuration data directories exist
    Config.ensure_data_dir()

    # Validate mandatory environment variables
    validation_warnings = Config.validate()
    for warning in validation_warnings:
        logger.warning("CONFIG WARNING: %s", warning)

    if not Config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is required to run the bot. Exiting.")
        sys.exit(1)

    # Initialize Database
    db = Database(Config.DATABASE_PATH)

    # Initialize Release Monitor
    monitor = ReleaseMonitor(
        target_os=Config.TARGET_OS,
        include_dev=Config.INCLUDE_DEV_BETAS,
        include_public=Config.INCLUDE_PUBLIC_BETAS,
        include_stable=Config.INCLUDE_STABLE
    )

    # Initialize Telegram Bot Service
    bot_service = TelegramBotService(config=Config, db=db, monitor=monitor)
    app = bot_service.setup_app()

    # Automatically add TELEGRAM_CHAT_ID to subscribers if specified in config
    if Config.TELEGRAM_CHAT_ID:
        db.add_subscriber(Config.TELEGRAM_CHAT_ID)
        logger.info("Default target chat ID %s added to subscribers.", Config.TELEGRAM_CHAT_ID)

    logger.info(
        "Bot successfully initialized. Monitoring platforms: %s. Polling interval: %ds.",
        ", ".join(Config.TARGET_OS).upper(),
        Config.CHECK_INTERVAL_SECONDS
    )

    # Start Telegram polling
    app.run_polling()

if __name__ == "__main__":
    main()
