import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id      INTEGER PRIMARY KEY,
    twitch_channel TEXT NOT NULL,
    sync_days     INTEGER NOT NULL DEFAULT 30,
    use_images    INTEGER NOT NULL DEFAULT 1,
    prune         INTEGER NOT NULL DEFAULT 1,
    added_by      INTEGER,
    created_at    TEXT NOT NULL,
    last_synced_at TEXT,
    last_error    TEXT
);
"""


@dataclass
class GuildConfig:
    guild_id: int
    twitch_channel: str
    sync_days: int
    use_images: bool
    prune: bool
    added_by: Optional[int]
    created_at: str
    last_synced_at: Optional[str]
    last_error: Optional[str]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "GuildConfig":
        return cls(
            guild_id=row["guild_id"],
            twitch_channel=row["twitch_channel"],
            sync_days=row["sync_days"],
            use_images=bool(row["use_images"]),
            prune=bool(row["prune"]),
            added_by=row["added_by"],
            created_at=row["created_at"],
            last_synced_at=row["last_synced_at"],
            last_error=row["last_error"],
        )


class Database:
    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert_guild(
        self,
        guild_id: int,
        twitch_channel: str,
        sync_days: int,
        use_images: bool,
        prune: bool,
        added_by: int,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO guild_config
                    (guild_id, twitch_channel, sync_days, use_images, prune, added_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    twitch_channel = excluded.twitch_channel,
                    sync_days = excluded.sync_days,
                    use_images = excluded.use_images,
                    prune = excluded.prune
                """,
                (
                    guild_id,
                    twitch_channel,
                    sync_days,
                    int(use_images),
                    int(prune),
                    added_by,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def remove_guild(self, guild_id: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM guild_config WHERE guild_id = ?", (guild_id,))
            return cur.rowcount > 0

    def get_guild(self, guild_id: int) -> Optional[GuildConfig]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
            ).fetchone()
            return GuildConfig.from_row(row) if row else None

    def all_guilds(self) -> list[GuildConfig]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM guild_config").fetchall()
            return [GuildConfig.from_row(r) for r in rows]

    def mark_synced(self, guild_id: int, error: Optional[str] = None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE guild_config SET last_synced_at = ?, last_error = ? WHERE guild_id = ?",
                (datetime.now(timezone.utc).isoformat(), error, guild_id),
            )
