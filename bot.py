import logging
import html
from datetime import datetime
from typing import List
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    JobQueue
)
from config import Config
from database import Database
from monitor import ReleaseMonitor, ReleaseItem

logger = logging.getLogger(__name__)

def format_release_message(item: ReleaseItem) -> str:
    """Formats a release item into clean HTML for Telegram messages."""
    os_emoji = {
        "iOS": "📱",
        "macOS": "💻",
        "iPadOS": "📱",
        "watchOS": "⌚️",
        "visionOS": "🥽",
        "tvOS": "📺",
        "Xcode": "🛠"
    }.get(item.os_type, "🚀")

    title_escaped = html.escape(item.title)
    link_escaped = html.escape(item.link)
    os_escaped = html.escape(item.os_type)
    rel_type_escaped = html.escape(item.release_type)
    pub_date_escaped = html.escape(item.pub_date) if item.pub_date else "Just now"

    msg = [
        f"🚨 <b>New Apple Release Detected!</b>\n",
        f"{os_emoji} <b>{title_escaped}</b>",
        f"🏷 <b>Channel:</b> <i>{rel_type_escaped}</i>",
        f"🖥 <b>Platform:</b> {os_escaped}"
    ]

    if item.build:
        build_escaped = html.escape(item.build)
        msg.append(f"🔢 <b>Build Number:</b> <code>{build_escaped}</code>")

    if item.pub_date:
        msg.append(f"📅 <b>Published:</b> {pub_date_escaped}")

    if item.link:
        msg.append(f"\n🔗 <a href='{link_escaped}'>View Apple Release Notes / Downloads</a>")

    return "\n".join(msg)

class TelegramBotService:
    def __init__(self, config: Config, db: Database, monitor: ReleaseMonitor):
        self.config = config
        self.db = db
        self.monitor = monitor
        self.start_time = datetime.now()
        self.app: Application = None

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start command."""
        chat_id = str(update.effective_chat.id)
        self.db.add_subscriber(chat_id)
        
        target_os_str = ", ".join(sorted(list(self.config.TARGET_OS))).upper()
        welcome_text = (
            "<b>👋 Welcome to the Apple Release Tracker Bot!</b>\n\n"
            f"You have been subscribed to automated notifications for <b>{html.escape(target_os_str)}</b> releases.\n\n"
            "<b>Available Commands:</b>\n"
            "• /latest - View recently detected releases\n"
            "• /check - Trigger a manual check right now\n"
            "• /status - View bot status and subscription info\n"
            "• /subscribe - Ensure your chat is subscribed\n"
            "• /unsubscribe - Stop receiving notifications\n"
            "• /help - Display this help message"
        )
        await update.message.reply_html(welcome_text)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /help command."""
        help_text = (
            "<b>ℹ️ Apple Release Tracker Bot Commands</b>\n\n"
            "• /latest - View recently detected releases\n"
            "• /check - Force check feeds for new releases\n"
            "• /status - Show bot uptime and release stats\n"
            "• /subscribe - Subscribe to release notifications\n"
            "• /unsubscribe - Unsubscribe from release notifications"
        )
        await update.message.reply_html(help_text)

    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /subscribe command."""
        chat_id = str(update.effective_chat.id)
        if self.db.add_subscriber(chat_id):
            await update.message.reply_html("✅ <b>Subscribed!</b> You will receive alerts when new iOS/macOS releases land.")
        else:
            await update.message.reply_html("ℹ️ You are already subscribed to release alerts.")

    async def cmd_unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /unsubscribe command."""
        chat_id = str(update.effective_chat.id)
        if self.db.remove_subscriber(chat_id):
            await update.message.reply_html("🔕 <b>Unsubscribed!</b> You will no longer receive release alerts.")
        else:
            await update.message.reply_html("ℹ️ You were not subscribed.")

    async def cmd_latest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /latest command."""
        recent = self.db.get_recent_releases(limit=5)
        if not recent:
            await update.message.reply_html("ℹ️ No releases recorded yet. Run /check to fetch live feeds.")
            return

        lines = ["<b>📋 Recently Detected Releases:</b>\n"]
        for r in recent:
            os_emoji = {"iOS": "📱", "macOS": "💻", "iPadOS": "📱"}.get(r["os_type"], "🚀")
            build_str = f" (Build: {r['build']})" if r.get('build') else ""
            lines.append(f"{os_emoji} <b>{html.escape(r['title'])}</b>{build_str}\n  <i>{html.escape(r['release_type'])}</i> • {html.escape(r['pub_date'] or '')}\n")

        await update.message.reply_html("\n".join(lines), disable_web_page_preview=True)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /status command."""
        stats = self.db.get_stats()
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0] # Remove microseconds

        target_os_str = ", ".join(sorted(list(self.config.TARGET_OS))).upper()
        
        status_text = (
            "<b>📊 Bot Status</b>\n\n"
            f"⏱ <b>Uptime:</b> {uptime_str}\n"
            f"🔄 <b>Poll Interval:</b> {self.config.CHECK_INTERVAL_SECONDS} seconds\n"
            f"🎯 <b>Monitored OS:</b> {html.escape(target_os_str)}\n"
            f"👥 <b>Subscribers:</b> {stats['total_subscribers']}\n"
            f"📦 <b>Total Recorded Releases:</b> {stats['total_releases']}\n"
        )
        await update.message.reply_html(status_text)

    async def cmd_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /check command (manual force poll)."""
        await update.message.reply_html("🔍 Checking Apple Developer & Beta feeds...")
        new_count = await self.run_check_and_notify(broadcast=True)
        if new_count == 0:
            await update.message.reply_html("✅ Feeds checked. No new releases detected.")
        else:
            await update.message.reply_html(f"🎉 Check complete! Found and notified <b>{new_count}</b> new release(s).")

    async def run_check_and_notify(self, broadcast: bool = True) -> int:
        """Polls feeds, records new releases, and broadcasts notifications. Returns count of new releases."""
        new_releases = 0
        fetched_items = await self.monitor.check_all_feeds()
        
        # Get all subscriber chat IDs
        subscribers = set(self.db.get_subscribers())
        if self.config.TELEGRAM_CHAT_ID:
            subscribers.add(str(self.config.TELEGRAM_CHAT_ID))

        for item in fetched_items:
            # Try inserting into DB
            is_new = self.db.add_seen_release(
                release_id=item.id,
                title=item.title,
                os_type=item.os_type,
                build=item.build,
                release_type=item.release_type,
                link=item.link,
                pub_date=item.pub_date
            )

            if is_new:
                new_releases += 1
                logger.info("New release detected: %s (%s)", item.title, item.release_type)

                if broadcast and self.app and subscribers:
                    msg_text = format_release_message(item)
                    for chat_id in subscribers:
                        try:
                            await self.app.bot.send_message(
                                chat_id=chat_id,
                                text=msg_text,
                                parse_mode="HTML",
                                disable_web_page_preview=False
                            )
                        except Exception as e:
                            logger.error("Failed to send notification to chat_id %s: %s", chat_id, e)

        return new_releases

    async def _scheduled_poll_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Job Queue callback for scheduled polling."""
        try:
            await self.run_check_and_notify(broadcast=True)
        except Exception as e:
            logger.error("Error in scheduled release check job: %s", e)

    def setup_app(self) -> Application:
        """Initializes and configures the Telegram Application."""
        builder = Application.builder().token(self.config.TELEGRAM_BOT_TOKEN)
        self.app = builder.build()

        # Register Command Handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("subscribe", self.cmd_subscribe))
        self.app.add_handler(CommandHandler("unsubscribe", self.cmd_unsubscribe))
        self.app.add_handler(CommandHandler("latest", self.cmd_latest))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("check", self.cmd_check))

        # Register Scheduled Polling Job
        job_queue = self.app.job_queue
        if job_queue:
            job_queue.run_repeating(
                self._scheduled_poll_job,
                interval=self.config.CHECK_INTERVAL_SECONDS,
                first=10 # First run after 10 seconds
            )

        return self.app
