"""
Twitch schedule -> Discord events bot.

Any server that runs /schedule link gets its Twitch schedule mirrored into
Discord scheduled events, refreshed on a timer in the background.
"""

import asyncio
import logging

import aiohttp
import discord
from discord.ext import commands, tasks

import config
from db import Database
from sync import sync_guild
from twitch_api import TwitchClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

INTENTS = discord.Intents.default()  # no message content needed; slash commands only


class ScheduleSyncBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned, intents=INTENTS)
        self.db = Database(config.DB_PATH)
        self.twitch = TwitchClient(config.TWITCH_CLIENT_ID, config.TWITCH_CLIENT_SECRET)
        self.http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()
        await self.load_extension("cogs.schedule")

        if config.DEV_GUILD_ID:
            guild_obj = discord.Object(id=config.DEV_GUILD_ID)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
            log.info("Slash commands synced instantly to dev guild %s", config.DEV_GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Slash commands synced globally (can take up to an hour to appear)")

        background_sync.start()

    async def close(self):
        background_sync.cancel()
        if self.http_session:
            await self.http_session.close()
        await super().close()


bot = ScheduleSyncBot()


@bot.event
async def on_ready():
    log.info("Logged in as %s (%s)", bot.user, bot.user.id)
    log.info("In %d guild(s), %d linked", len(bot.guilds), len(bot.db.all_guilds()))


@tasks.loop(minutes=config.SYNC_INTERVAL_MINUTES)
async def background_sync():
    for cfg in bot.db.all_guilds():
        guild = bot.get_guild(cfg.guild_id)
        if guild is None:
            continue  # bot was removed from that server
        try:
            result = await sync_guild(guild, cfg, bot.twitch, bot.http_session)
            if result.channel_not_found:
                bot.db.mark_synced(cfg.guild_id, error=f"Twitch channel '{cfg.twitch_channel}' not found")
                log.warning("Guild %s: Twitch channel '%s' not found", cfg.guild_id, cfg.twitch_channel)
            else:
                bot.db.mark_synced(cfg.guild_id)
                if result.created or result.pruned:
                    log.info(
                        "Guild %s: %d created, %d skipped, %d pruned",
                        cfg.guild_id, result.created, result.skipped, result.pruned,
                    )
        except discord.Forbidden:
            bot.db.mark_synced(cfg.guild_id, error="Missing 'Manage Events' permission")
            log.warning("Guild %s: missing Manage Events permission", cfg.guild_id)
        except Exception as exc:  # one guild's failure shouldn't stop the rest
            bot.db.mark_synced(cfg.guild_id, error=str(exc)[:200])
            log.exception("Guild %s: sync failed", cfg.guild_id)


@background_sync.before_loop
async def before_background_sync():
    await bot.wait_until_ready()


if __name__ == "__main__":
    bot.run(config.DISCORD_BOT_TOKEN, log_handler=None)
