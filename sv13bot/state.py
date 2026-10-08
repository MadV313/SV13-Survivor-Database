from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


class StateStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS guild_channels (
                    guild_id INTEGER NOT NULL,
                    channel_key TEXT NOT NULL,
                    channel_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, channel_key)
                );

                CREATE TABLE IF NOT EXISTS metadata (
                    guild_id INTEGER NOT NULL,
                    meta_key TEXT NOT NULL,
                    meta_value TEXT NOT NULL,
                    PRIMARY KEY (guild_id, meta_key)
                );

                CREATE TABLE IF NOT EXISTS published_entities (
                    guild_id INTEGER NOT NULL,
                    entity_key TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    channel_id INTEGER NOT NULL,
                    thread_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, entity_key)
                );
                """
            )

    def set_channel(self, guild_id: int, key: str, channel_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO guild_channels(guild_id, channel_key, channel_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, channel_key)
                DO UPDATE SET channel_id=excluded.channel_id
                """,
                (guild_id, key, channel_id),
            )

    def get_channel(self, guild_id: int, key: str) -> Optional[int]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT channel_id FROM guild_channels WHERE guild_id=? AND channel_key=?",
                (guild_id, key),
            ).fetchone()
        return int(row["channel_id"]) if row else None

    def set_meta(self, guild_id: int, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO metadata(guild_id, meta_key, meta_value)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, meta_key)
                DO UPDATE SET meta_value=excluded.meta_value
                """,
                (guild_id, key, value),
            )

    def get_meta(self, guild_id: int, key: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT meta_value FROM metadata WHERE guild_id=? AND meta_key=?",
                (guild_id, key),
            ).fetchone()
        return str(row["meta_value"]) if row else None

    def get_published(self, guild_id: int, entity_key: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM published_entities WHERE guild_id=? AND entity_key=?",
                (guild_id, entity_key),
            ).fetchone()
        return dict(row) if row else None

    def upsert_published(
        self,
        guild_id: int,
        entity_key: str,
        entity_type: str,
        content_hash: str,
        channel_id: int,
        thread_id: int,
        message_id: int,
        payload: Dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO published_entities(
                    guild_id, entity_key, entity_type, content_hash,
                    channel_id, thread_id, message_id, payload_json, updated_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id, entity_key)
                DO UPDATE SET
                    entity_type=excluded.entity_type,
                    content_hash=excluded.content_hash,
                    channel_id=excluded.channel_id,
                    thread_id=excluded.thread_id,
                    message_id=excluded.message_id,
                    payload_json=excluded.payload_json,
                    updated_utc=CURRENT_TIMESTAMP
                """,
                (
                    guild_id,
                    entity_key,
                    entity_type,
                    content_hash,
                    channel_id,
                    thread_id,
                    message_id,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                ),
            )
