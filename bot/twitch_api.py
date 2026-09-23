"""
Thin wrapper around the Twitch Helix API.

Uses a single app-access token (client-credentials grant) shared across all
guilds, since reading a public channel's schedule doesn't require the
streamer to authorize anything. The token is cached in memory and refreshed
shortly before it expires.
"""

import time
from datetime import datetime, timezone
from typing import Optional

import aiohttp

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
API_BASE = "https://api.twitch.tv/helix"


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class TwitchClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expires_at: float = 0

    async def _headers(self, session: aiohttp.ClientSession) -> dict:
        if not self._token or time.monotonic() >= self._token_expires_at:
            async with session.post(
                TOKEN_URL,
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            ) as resp:
                resp.raise_for_status()
                body = await resp.json()
            self._token = body["access_token"]
            self._token_expires_at = time.monotonic() + body.get("expires_in", 3600) - 60
        return {"Client-ID": self.client_id, "Authorization": f"Bearer {self._token}"}

    async def get_broadcaster(self, session: aiohttp.ClientSession, login: str) -> Optional[dict]:
        headers = await self._headers(session)
        async with session.get(
            f"{API_BASE}/users", headers=headers, params={"login": login.lower()}
        ) as resp:
            resp.raise_for_status()
            data = (await resp.json()).get("data", [])
        return data[0] if data else None

    async def get_schedule(
        self, session: aiohttp.ClientSession, broadcaster_id: str, window_end: datetime
    ) -> list[dict]:
        headers = await self._headers(session)
        segments, cursor = [], None
        while True:
            params = {"broadcaster_id": broadcaster_id, "first": 25}
            if cursor:
                params["after"] = cursor
            async with session.get(
                f"{API_BASE}/schedule", headers=headers, params=params
            ) as resp:
                if resp.status == 404:  # channel has no schedule set up
                    return []
                resp.raise_for_status()
                body = await resp.json()

            data = body.get("data", {})
            page = data.get("segments") or []
            for seg in page:
                if seg.get("canceled_until"):
                    continue
                if parse_iso(seg["start_time"]) >= window_end:
                    continue
                segments.append(seg)

            cursor = (body.get("pagination") or {}).get("cursor")
            if not cursor or not page or parse_iso(page[-1]["start_time"]) >= window_end:
                break
        return segments

    async def get_category_art_url(
        self, session: aiohttp.ClientSession, game_id: str, size: str = "285x380"
    ) -> Optional[str]:
        headers = await self._headers(session)
        async with session.get(
            f"{API_BASE}/games", headers=headers, params={"id": game_id}
        ) as resp:
            resp.raise_for_status()
            data = (await resp.json()).get("data", [])
        if not data or not data[0].get("box_art_url"):
            return None
        return data[0]["box_art_url"].replace("{width}x{height}", size)
