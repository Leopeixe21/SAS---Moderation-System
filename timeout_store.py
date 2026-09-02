from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class PendingTimeout:
    guild_id: int
    user_id: int
    expires_at: datetime
    source: str


class TimeoutStore:
    """Armazena timeouts pendentes em um SQLite local."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS timeouts (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                source TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        self.connection.commit()

    @staticmethod
    def _utc_iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    def save(self, guild_id: int, user_id: int, expires_at: datetime, source: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """
            INSERT INTO timeouts
                (guild_id, user_id, expires_at, source, active, created_at, completed_at)
            VALUES (?, ?, ?, ?, 1, ?, NULL)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                expires_at = excluded.expires_at,
                source = excluded.source,
                active = 1,
                created_at = excluded.created_at,
                completed_at = NULL
            """,
            (guild_id, user_id, self._utc_iso(expires_at), source, now),
        )
        self.connection.commit()

    def complete(self, guild_id: int, user_id: int) -> bool:
        cursor = self.connection.execute(
            """
            UPDATE timeouts
            SET active = 0, completed_at = ?
            WHERE guild_id = ? AND user_id = ? AND active = 1
            """,
            (datetime.now(timezone.utc).isoformat(), guild_id, user_id),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def pending(self) -> list[PendingTimeout]:
        rows = self.connection.execute(
            """
            SELECT guild_id, user_id, expires_at, source
            FROM timeouts
            WHERE active = 1
            ORDER BY expires_at
            """
        ).fetchall()
        return [
            PendingTimeout(
                guild_id=int(guild_id),
                user_id=int(user_id),
                expires_at=datetime.fromisoformat(expires_at).astimezone(timezone.utc),
                source=str(source),
            )
            for guild_id, user_id, expires_at, source in rows
        ]

    def is_pending(self, guild_id: int, user_id: int) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM timeouts WHERE guild_id = ? AND user_id = ? AND active = 1",
            (guild_id, user_id),
        ).fetchone()
        return row is not None

    def close(self) -> None:
        self.connection.close()
