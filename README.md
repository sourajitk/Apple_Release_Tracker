# Apple iOS & macOS Release Tracker Telegram Bot

A Python-based Telegram bot designed to detect and alert you instantly when new **iOS** and **macOS** Developer Betas, Public Betas, and Official releases land.

Built with `python-telegram-bot` and containerized with **Docker** & **Docker Compose**.

---

## Features

- **Instant Release Detection**: Automatically monitors official Apple Developer Release feeds and IPSW feeds.
- **Target Platforms**: Filters for iOS & macOS releases (with customizable support for iPadOS, watchOS, visionOS, tvOS, and Xcode).
- **Channel Identification**: Detects Developer Betas, Public Betas, Release Candidates (RC), and Stable releases.
- **Build Numbers**: Extracts build tags (e.g. `22C5125e`) and direct links to Apple release notes & downloads.
- **Multi-Chat Subscriptions**: Broadcasts to configured channel IDs and any user/group that runs `/start` or `/subscribe`.
- **Persistent SQLite State**: Prevents duplicate notifications even across container restarts.
- **Docker Ready**: Production container setup with non-root security and volume persistence.

---

## Telegram Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message & auto-subscribes current chat to release alerts |
| `/latest` | Displays the 5 most recently detected Apple releases |
| `/check` | Triggers an immediate feed check for new releases |
| `/status` | Shows bot status, uptime, poll interval, subscriber count, and database stats |
| `/subscribe` | Explicitly subscribe current chat to release notifications |
| `/unsubscribe` | Stop receiving release notifications |
| `/help` | List available commands |

---

## Deployment with Docker Compose (Recommended)

### 1. Clone & Set Up Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and insert your Telegram Bot Token from [@BotFather](https://t.me/BotFather):

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=-1001234567890
CHECK_INTERVAL_SECONDS=300
TARGET_OS=iOS, macOS
INCLUDE_DEV_BETAS=true
INCLUDE_PUBLIC_BETAS=true
INCLUDE_STABLE=true
```

### 2. Build and Launch

Run Docker Compose in detached mode:

```bash
docker-compose up -d --build
```

View live bot logs:

```bash
docker-compose logs -f
```

Stop the bot:

```bash
docker-compose down
```

---

## Running Without Docker (Local Python)

### 1. Requirements

- Python 3.10+ installed.

### 2. Installation

```bash
python3 -m venv venv
source venv/bin/venv/activate
pip install -r requirements.txt
```

### 3. Run the Bot

```bash
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN
python3 main.py
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Required | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Optional | Default chat or channel ID to receive alerts |
| `CHECK_INTERVAL_SECONDS` | `300` | Feed polling frequency in seconds (default: 5 min) |
| `TARGET_OS` | `iOS, macOS` | Comma-separated list of target operating systems |
| `INCLUDE_DEV_BETAS` | `true` | Include Developer Beta releases |
| `INCLUDE_PUBLIC_BETAS` | `true` | Include Public Beta releases |
| `INCLUDE_STABLE` | `true` | Include Stable / Official releases |
| `DATABASE_PATH` | `data/releases.db` | SQLite database file location |

---

## License

MIT License. Feel free to modify and adapt for your workflow!
