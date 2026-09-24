import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiohttp
import discord

from db import Database, GuildConfig
from images import build_cover
from twitch_api import TwitchClient, parse_iso

MARKER_RE = re.compile(r"\[twitch-segment:([^\]]+)\]")
DEFAULT_DURATION = timedelta(hours=2)


@dataclass
class SyncResult:
    created: int = 0
    skipped: int = 0
    pruned: int = 0
    channel_not_found: bool = False


def _build_description(segment: dict, channel: str) -> str:
    url = f"https://twitch.tv/{channel}"
    category = (segment.get("category") or {}).get("name")
    lines = []
    if category:
        lines.append(f"Category: {category}")
        lines.append(f"Watch live: {url}")
    return "\n".join(lines)[:1000]


async def sync_guild(
    guild: discord.Guild,
    config: GuildConfig,
    twitch: TwitchClient,
    session: aiohttp.ClientSession,
) -> SyncResult:
    result = SyncResult()
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=config.sync_days)

    broadcaster = await twitch.get_broadcaster(session, config.twitch_channel)
    if not broadcaster:
        result.channel_not_found = True
        return result

    segments = await twitch.get_schedule(session, broadcaster["id"], window_end)

    existing_events = await guild.fetch_scheduled_events()
    existing_by_segment: dict[str, discord.ScheduledEvent] = {}
    for ev in existing_events:
        m = MARKER_RE.search(ev.description or "")
        if m:
            existing_by_segment[m.group(1)] = ev

    cover_cache: dict[str, bytes | None] = {}

    for seg in segments:
        if seg["id"] in existing_by_segment:
            result.skipped += 1
            continue

        start = parse_iso(seg["start_time"])
        if start <= now + timedelta(minutes=1):
            result.skipped += 1
            continue
        end = parse_iso(seg["end_time"]) if seg.get("end_time") else None
        if not end or end <= start:
            end = start + DEFAULT_DURATION

        name = (seg.get("title") or "").strip() or f"{config.twitch_channel} live on Twitch"
        cover = None
        if config.use_images:
            game_id = (seg.get("category") or {}).get("id") or "channel"
            if game_id not in cover_cache:
                box_art_url = None
                if game_id != "channel":
                    box_art_url = await twitch.get_category_art_url(session, game_id)
                cover_cache[game_id] = await build_cover(
                    session,
                    box_art_url,
                    broadcaster.get("offline_image_url"),
                    broadcaster.get("profile_image_url"),
                )
            cover = cover_cache[game_id]

        await guild.create_scheduled_event(
            name=name[:100],
            description=_build_description(seg, config.twitch_channel),
            start_time=start,
            end_time=end,
            entity_type=discord.EntityType.external,
            location=f"https://twitch.tv/{config.twitch_channel}"[:100],
            privacy_level=discord.PrivacyLevel.guild_only,
            image=cover,
        )
        result.created += 1

    if config.prune:
        current_ids = {s["id"] for s in segments}
        for seg_id, ev in existing_by_segment.items():
            in_window = now < ev.start_time < window_end
            if ev.status == discord.EventStatus.scheduled and in_window and seg_id not in current_ids:
                await ev.delete(reason="Twitch segment was cancelled or removed")
                result.pruned += 1

    return result
