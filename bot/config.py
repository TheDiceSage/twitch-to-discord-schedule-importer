"""Loads configuration from environment variables (or a .env file)."""

import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional; env vars can be set directly instead


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing required environment variable: {name}")
    return value


DISCORD_BOT_TOKEN = _require("DISCORD_BOT_TOKEN")
TWITCH_CLIENT_ID = _require("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = _require("TWITCH_CLIENT_SECRET")

# Optional: restrict slash-command sync to one guild for instant testing.
# Leave unset in production (global sync can take up to an hour to propagate).
DEV_GUILD_ID = os.environ.get("DEV_GUILD_ID")
DEV_GUILD_ID = int(DEV_GUILD_ID) if DEV_GUILD_ID else None

# How often the background loop checks every linked server, in minutes.
SYNC_INTERVAL_MINUTES = int(os.environ.get("SYNC_INTERVAL_MINUTES", "30"))

DB_PATH = os.environ.get("DB_PATH", "schedule_sync.db")
