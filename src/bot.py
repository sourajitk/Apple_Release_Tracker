import email.utils
import html
import logging
from datetime import datetime, timezone, timedelta
from typing import Set

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ChatMemberHandler,
    ContextTypes
)

from config import Config
from database import Database
from models import ReleaseItem
from monitor import ReleaseMonitor

logger = logging.getLogger(__name__)


def is_recent_release(pub_date_str: str, max_age_days: float = 3.0) -> bool:
    """Checks if a publication date string is within max_age_days from now to prevent posting historical entries."""
    if not pub_date_str:
        return True
    try:
        dt = email.utils.parsedate_to_datetime(pub_date_str)
        now = datetime.now(timezone.utc)
        age = now - dt
        return age <= timedelta(days=max_age_days)
    except Exception:
        return True


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

    build_info = f"\n<b>Build Number:</b> <code>{html.escape(item.build)}</code>" if item.build else ""
    pub_date_info = f"\n<b>Published:</b> {html.escape(item.pub_date)}" if item.pub_date else ""

    message = (
        f"🚀 <b>New Apple Release Detected!</b>\n\n"
        f"{os_emoji} <b>{html.escape(item.title)}</b>\n"
        f"<b>Channel:</b> {html.escape(item.release_type)}\n"
        f"<b>Platform:</b> {html.escape(item.os_type)}"
        f"{build_info}"
        f"{pub_date_info}\n\n"
        f"🔗 <a href='{html.escape(item.link)}'>View Apple Release Notes / Downloads</a>"
    )
    return message


class TelegramBotService:
    """Service wrapper managing Telegram bot commands, channel alerts, and polling schedules."""

    def __init__(self, config: Config, db: Database, monitor: ReleaseMonitor):
        self.config = config
        self.db = db
        self.monitor = monitor
        self.start_time = datetime.now()
        self.app: Application = None

    async def on_my_chat_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for my_chat_member updates to auto-subscribe channels and groups when bot is added."""
        my_chat_member = update.my_chat_member
        if not my_chat_member:
            return

        new_status = my_chat_member.new_chat_member.status
        chat_id = str(my_chat_member.chat.id)

        if new_status in ("administrator", "member"):
            if self.db.add_subscriber(chat_id):
                logger.info("Auto-subscribed chat_id: %s (%s)", chat_id, my_chat_member.chat.title or "Private")
        elif new_status in ("kicked", "left"):
            if self.db.remove_subscriber(chat_id):
                logger.info("Auto-unsubscribed chat_id: %s", chat_id)

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
            "• /interval <sec> - (Admin) Change poll interval\n"
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
            "• /unsubscribe - Unsubscribe from release notifications\n"
            "• /interval <sec> - Set poll interval (Admin user 518576860 only)"
        )
        await update.message.reply_html(help_text)

    async def cmd_interval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /interval <seconds> command (Admin user 518576860 only)."""
        user_id = update.effective_user.id if update.effective_user else None
        admin_id = getattr(self.config, "ADMIN_USER_ID", 518576860)

        if user_id != admin_id:
            await update.message.reply_html("<b>⛔️ Unauthorized:</b> Only the bot administrator can change the check interval.")
            return

        if not context.args or not context.args[0].isdigit():
            await update.message.reply_html(
                "<b>Usage:</b> <code>/interval &lt;seconds&gt;</code>\n"
                "Example: <code>/interval 300</code> (5 min) or <code>/interval 60</code> (1 min)"
            )
            return

        new_interval = int(context.args[0])
        if new_interval < 10:
            await update.message.reply_html("<b>Error:</b> Minimum check interval is 10 seconds.")
            return

        self.config.CHECK_INTERVAL_SECONDS = new_interval

        job_queue = self.app.job_queue if self.app else None
        if job_queue:
            jobs = job_queue.get_jobs_by_name("release_poll_job")
            for job in jobs:
                job.schedule_removal()

            job_queue.run_repeating(
                self._scheduled_poll_job,
                interval=new_interval,
                first=new_interval,
                name="release_poll_job"
            )

        mins = new_interval / 60.0
        time_fmt = f"{new_interval}s ({mins:.1f} min)" if mins >= 1 else f"{new_interval}s"
        logger.info("Check interval updated to %d seconds by admin %s", new_interval, user_id)
        await update.message.reply_html(f"<b>✅ Check interval updated!</b>\nNew feed polling frequency set to <b>{html.escape(time_fmt)}</b>.")

    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /subscribe command."""
        chat_id = str(update.effective_chat.id)
        if self.db.add_subscriber(chat_id):
            await update.message.reply_html("<b>Subscribed!</b> You will receive alerts when new Apple releases land.")
        else:
            await update.message.reply_html("You are already subscribed to release alerts.")

    async def cmd_unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /unsubscribe command."""
        chat_id = str(update.effective_chat.id)
        if self.db.remove_subscriber(chat_id):
            await update.message.reply_html("<b>Unsubscribed!</b> You will no longer receive release alerts.")
        else:
            await update.message.reply_html("You were not subscribed.")

    async def cmd_latest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /latest command."""
        recent = self.db.get_recent_releases(target_os=self.config.TARGET_OS, limit_per_os=2)
        if not recent:
            await update.message.reply_html("No releases recorded yet for your target OS. Run /check to fetch live feeds.")
            return

        lines = ["<b>Recently Detected Releases:</b>\n"]
        for r in recent:
            os_emoji = {
                "iOS": "📱",
                "macOS": "💻",
                "iPadOS": "📱",
                "watchOS": "⌚️",
                "visionOS": "🥽",
                "tvOS": "📺",
                "Xcode": "🛠"
            }.get(r["os_type"], "🚀")
            build_str = f" (Build: {r['build']})" if r.get('build') else ""
            lines.append(f"{os_emoji} <b>{html.escape(r['title'])}</b>{build_str}\n  <i>{html.escape(r['release_type'])}</i> • {html.escape(r['pub_date'] or '')}\n")

        await update.message.reply_html("\n".join(lines), disable_web_page_preview=True)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /status command."""
        stats = self.db.get_stats()
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]

        target_os_str = ", ".join(sorted(list(self.config.TARGET_OS))).upper()
        status_text = (
            "<b>Bot Status</b>\n\n"
            f"<b>Uptime:</b> {uptime_str}\n"
            f"<b>Poll Interval:</b> {self.config.CHECK_INTERVAL_SECONDS} seconds\n"
            f"<b>Monitored OS:</b> {html.escape(target_os_str)}\n"
            f"<b>Subscribers:</b> {stats['total_subscribers']}\n"
            f"<b>Recorded Releases:</b> {stats['total_releases']}"
        )
        await update.message.reply_html(status_text)

    async def cmd_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /check command (manual force poll)."""
        await update.message.reply_html("Checking Apple Developer & Beta feeds...")
        new_count = await self.run_check_and_notify(broadcast=True)
        if new_count == 0:
            await update.message.reply_html("Feeds checked. No new releases detected.")
        else:
            await update.message.reply_html(f"Check complete! Found and notified <b>{new_count}</b> new release(s).")

    async def run_check_and_notify(self, broadcast: bool = True) -> int:
        """Polls feeds, records new releases, and broadcasts notifications. Returns count of new releases."""
        new_releases = 0
        fetched_items = await self.monitor.check_all_feeds()

        subscribers: Set[str] = set(self.db.get_subscribers())
        if self.config.TELEGRAM_CHAT_ID:
            subscribers.add(str(self.config.TELEGRAM_CHAT_ID))

        for item in reversed(fetched_items):
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

                if broadcast and self.app and subscribers and is_recent_release(item.pub_date, max_age_days=3.0):
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
                            err_msg = str(e).lower()
                            if any(k in err_msg for k in ["forbidden", "chat not found", "bot was kicked", "bot is not a member"]):
                                self.db.remove_subscriber(chat_id)

        return new_releases

    async def _scheduled_poll_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Job Queue callback for scheduled polling."""
        try:
            await self.run_check_and_notify(broadcast=True)
        except Exception as e:
            logger.error("Error in scheduled release check job: %s", e)

    def setup_app(self) -> Application:
        """Initializes and configures the Telegram Application."""
        async def post_init(application: Application):
            logger.info("Performing initial feed scan to populate releases database...")
            try:
                await self.run_check_and_notify(broadcast=True)
            except Exception as e:
                logger.error("Initial feed scan error: %s", e)

        builder = Application.builder().token(self.config.TELEGRAM_BOT_TOKEN).post_init(post_init)
        self.app = builder.build()

        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("subscribe", self.cmd_subscribe))
        self.app.add_handler(CommandHandler("unsubscribe", self.cmd_unsubscribe))
        self.app.add_handler(CommandHandler("latest", self.cmd_latest))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("check", self.cmd_check))
        self.app.add_handler(CommandHandler("interval", self.cmd_interval))

        self.app.add_handler(ChatMemberHandler(self.on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

        job_queue = self.app.job_queue
        if job_queue:
            job_queue.run_repeating(
                self._scheduled_poll_job,
                interval=self.config.CHECK_INTERVAL_SECONDS,
                first=10,
                name="release_poll_job"
            )

        return self.app
