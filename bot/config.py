import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass 


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing required environment variable: {name}")
    return value


DISCORD_BOT_TOKEN = _require("DISCORD_BOT_TOKEN")
TWITCH_CLIENT_ID = _require("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = _require("TWITCH_CLIENT_SECRET")

DEV_GUILD_ID = os.environ.get("DEV_GUILD_ID")
DEV_GUILD_ID = int(DEV_GUILD_ID) if DEV_GUILD_ID else None

SYNC_INTERVAL_MINUTES = int(os.environ.get("SYNC_INTERVAL_MINUTES", "30"))

DB_PATH = os.environ.get("DB_PATH", "schedule_sync.db")
