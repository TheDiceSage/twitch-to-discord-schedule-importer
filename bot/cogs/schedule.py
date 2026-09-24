import discord
from discord import app_commands
from discord.ext import commands

from sync import sync_guild


class ScheduleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    schedule_group = app_commands.Group(
        name="schedule",
        description="Sync a Twitch schedule to this server's events",
        default_permissions=discord.Permissions(manage_events=True),
    )

    @schedule_group.command(name="link", description="Link a Twitch channel and sync its schedule here")
    @app_commands.describe(
        twitch_channel="Your Twitch login name, e.g. 'mychannel'",
        days_ahead="How many days ahead to sync (default 30)",
        cover_images="Attach a cover image to each event (default on)",
        prune="Remove events whose Twitch segment was cancelled (default on)",
    )
    async def link(
        self,
        interaction: discord.Interaction,
        twitch_channel: str,
        days_ahead: app_commands.Range[int, 1, 90] = 30,
        cover_images: bool = True,
        prune: bool = True,
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)
        twitch_channel = twitch_channel.strip().lstrip("@")

        broadcaster = await self.bot.twitch.get_broadcaster(self.bot.http_session, twitch_channel)
        if not broadcaster:
            await interaction.followup.send(
                f"Couldn't find a Twitch channel named **{twitch_channel}**. Double check the login name."
            )
            return

        self.bot.db.upsert_guild(
            guild_id=interaction.guild_id,
            twitch_channel=twitch_channel,
            sync_days=days_ahead,
            use_images=cover_images,
            prune=prune,
            added_by=interaction.user.id,
        )

        await interaction.followup.send(
            f"Linked **{broadcaster['display_name']}**. Running the first sync now, this can take a moment "
            f"if cover images are on..."
        )

        config = self.bot.db.get_guild(interaction.guild_id)
        try:
            result = await sync_guild(interaction.guild, config, self.bot.twitch, self.bot.http_session)
            self.bot.db.mark_synced(interaction.guild_id)
            await interaction.followup.send(
                f"Done: {result.created} event(s) created, {result.skipped} already existed."
            )
        except discord.Forbidden:
            self.bot.db.mark_synced(interaction.guild_id, error="Missing 'Manage Events' permission")
            await interaction.followup.send(
                "I'm missing the **Manage Events** permission in this server. "
                "Ask an admin to grant it, then run `/schedule sync`."
            )

    @schedule_group.command(name="unlink", description="Stop syncing and forget this server's linked channel")
    async def unlink(self, interaction: discord.Interaction):
        removed = self.bot.db.remove_guild(interaction.guild_id)
        msg = (
            "Unlinked. Events already created in this server are left as-is."
            if removed
            else "This server isn't linked to a Twitch channel."
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @schedule_group.command(name="status", description="Show this server's current sync settings")
    async def status(self, interaction: discord.Interaction):
        config = self.bot.db.get_guild(interaction.guild_id)
        if not config:
            await interaction.response.send_message(
                "No channel linked yet. Use `/schedule link` to get started.", ephemeral=True
            )
            return

        embed = discord.Embed(title="Twitch \u2192 Discord schedule sync", color=discord.Color.blurple())
        embed.add_field(name="Twitch channel", value=config.twitch_channel, inline=True)
        embed.add_field(name="Sync window", value=f"{config.sync_days} days", inline=True)
        embed.add_field(name="Cover images", value="On" if config.use_images else "Off", inline=True)
        embed.add_field(name="Prune cancelled", value="On" if config.prune else "Off", inline=True)
        embed.add_field(name="Last synced", value=config.last_synced_at or "Never", inline=False)
        if config.last_error:
            embed.add_field(name="Last error", value=config.last_error, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @schedule_group.command(name="sync", description="Sync this server's schedule right now")
    async def sync_now(self, interaction: discord.Interaction):
        config = self.bot.db.get_guild(interaction.guild_id)
        if not config:
            await interaction.response.send_message(
                "No channel linked yet. Use `/schedule link` first.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            result = await sync_guild(interaction.guild, config, self.bot.twitch, self.bot.http_session)
            self.bot.db.mark_synced(interaction.guild_id)
            if result.channel_not_found:
                await interaction.followup.send(f"Twitch channel **{config.twitch_channel}** not found.")
                return
            await interaction.followup.send(
                f"Synced: {result.created} created, {result.skipped} skipped, {result.pruned} pruned."
            )
        except discord.Forbidden:
            self.bot.db.mark_synced(interaction.guild_id, error="Missing 'Manage Events' permission")
            await interaction.followup.send("I'm missing the **Manage Events** permission in this server.")


async def setup(bot: commands.Bot):
    await bot.add_cog(ScheduleCog(bot))
