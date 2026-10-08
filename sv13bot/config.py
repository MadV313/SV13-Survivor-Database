from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Optional

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class BotConfig:
    token: str
    guild_id: Optional[int]
    knowledge_dir: Path
    state_db_path: Path

    auto_setup: bool
    auto_sync: bool
    auto_publish: bool
    sync_interval_seconds: int
    auto_publish_batch_size: int

    public_statuses: FrozenSet[str]
    owner_user_id: Optional[int]
    web_base_url: str
    log_level: str

    category_name: str
    terminal_channel_name: str
    intel_channel_name: str
    item_forum_name: str
    crafting_forum_name: str
    building_forum_name: str
    field_forum_name: str

    @classmethod
    def load(cls, require_token: bool = True) -> "BotConfig":
        load_dotenv()

        token = os.getenv("DISCORD_TOKEN", "").strip()
        if require_token and not token:
            raise RuntimeError(
                "DISCORD_TOKEN is missing. Copy .env.example to .env and add the bot token."
            )

        guild_raw = os.getenv("DISCORD_GUILD_ID", "").strip()
        guild_id = int(guild_raw) if guild_raw.isdigit() else None

        knowledge_dir = Path(
            os.getenv("SV13_KNOWLEDGE_DIR", "SV13_Knowledge/Latest")
        ).expanduser()

        state_db_path = Path(
            os.getenv("STATE_DB_PATH", "data/sv13_bot.sqlite3")
        ).expanduser()

        statuses = frozenset(
            s.strip()
            for s in os.getenv(
                "PUBLIC_STATUSES",
                "SV13AuthoredCandidate,ProjectIntegratedCandidate",
            ).split(",")
            if s.strip()
        )

        owner_raw = os.getenv("OWNER_USER_ID", "").strip()
        owner_user_id = int(owner_raw) if owner_raw.isdigit() else None

        return cls(
            token=token,
            guild_id=guild_id,
            knowledge_dir=knowledge_dir,
            state_db_path=state_db_path,
            auto_setup=_as_bool(os.getenv("AUTO_SETUP"), False),
            auto_sync=_as_bool(os.getenv("AUTO_SYNC"), True),
            auto_publish=_as_bool(os.getenv("AUTO_PUBLISH"), False),
            sync_interval_seconds=max(
                60, _as_int(os.getenv("SYNC_INTERVAL_SECONDS"), 300)
            ),
            auto_publish_batch_size=max(
                1, min(100, _as_int(os.getenv("AUTO_PUBLISH_BATCH_SIZE"), 25))
            ),
            public_statuses=statuses,
            owner_user_id=owner_user_id,
            web_base_url=os.getenv("WEB_BASE_URL", "").strip().rstrip("/"),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
            category_name=os.getenv(
                "SV13_CATEGORY_NAME", "SV13 • SURVIVOR DATABASE"
            ).strip(),
            terminal_channel_name=os.getenv(
                "TERMINAL_CHANNEL_NAME", "database-terminal"
            ).strip(),
            intel_channel_name=os.getenv(
                "INTEL_CHANNEL_NAME", "intel-updates"
            ).strip(),
            item_forum_name=os.getenv("ITEM_FORUM_NAME", "item-index").strip(),
            crafting_forum_name=os.getenv(
                "CRAFTING_FORUM_NAME", "crafting-manual"
            ).strip(),
            building_forum_name=os.getenv(
                "BUILDING_FORUM_NAME", "construction-manual"
            ).strip(),
            field_forum_name=os.getenv("FIELD_FORUM_NAME", "field-manual").strip(),
        )
