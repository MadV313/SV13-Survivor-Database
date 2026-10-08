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


def _optional_int_env(name: str) -> Optional[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise RuntimeError(f"{name} must contain only digits when set.")
    return int(raw)


@dataclass(frozen=True)
class BotConfig:
    token: str
    guild_id: Optional[int]

    knowledge_dir: Path
    knowledge_base_url: str
    knowledge_cache_dir: Path
    knowledge_http_timeout_seconds: int
    state_db_path: Path

    auto_setup: bool
    auto_sync: bool
    auto_publish: bool
    sync_interval_seconds: int
    auto_publish_batch_size: int
    auto_publish_max_batches: int

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
                "DISCORD_TOKEN is missing. Copy .env.example to .env locally, "
                "or set DISCORD_TOKEN in the deployment environment."
            )

        guild_id = _optional_int_env("DISCORD_GUILD_ID")
        owner_user_id = _optional_int_env("OWNER_USER_ID")

        knowledge_dir = Path(
            os.getenv("SV13_KNOWLEDGE_DIR", "SV13_Knowledge/Latest")
        ).expanduser()

        knowledge_base_url = (
            os.getenv("SV13_KNOWLEDGE_BASE_URL", "").strip().rstrip("/")
        )
        knowledge_cache_dir = Path(
            os.getenv("SV13_KNOWLEDGE_CACHE_DIR", "data/knowledge-cache")
        ).expanduser()

        explicit_state = os.getenv("STATE_DB_PATH", "").strip()
        if explicit_state:
            state_db_path = Path(explicit_state).expanduser()
        else:
            railway_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
            if railway_mount:
                state_db_path = Path(railway_mount) / "sv13_bot.sqlite3"
            else:
                state_db_path = Path("data/sv13_bot.sqlite3")

        statuses = frozenset(
            s.strip()
            for s in os.getenv(
                "PUBLIC_STATUSES",
                "SV13AuthoredCandidate,ProjectIntegratedCandidate",
            ).split(",")
            if s.strip()
        )
        if not statuses:
            raise RuntimeError("PUBLIC_STATUSES must contain at least one status.")

        return cls(
            token=token,
            guild_id=guild_id,
            knowledge_dir=knowledge_dir,
            knowledge_base_url=knowledge_base_url,
            knowledge_cache_dir=knowledge_cache_dir,
            knowledge_http_timeout_seconds=max(
                5, min(120, _as_int(os.getenv("KNOWLEDGE_HTTP_TIMEOUT_SECONDS"), 20))
            ),
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
            auto_publish_max_batches=max(
                1, min(100, _as_int(os.getenv("AUTO_PUBLISH_MAX_BATCHES"), 20))
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
