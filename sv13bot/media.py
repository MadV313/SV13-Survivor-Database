from __future__ import annotations

from typing import Any, Dict, Optional

import discord

from .knowledge import KnowledgeStore


def attach_record_thumbnail(
    embed: discord.Embed,
    store: KnowledgeStore,
    kind: str,
    record: Dict[str, Any],
) -> Optional[discord.File]:
    path = store.media_path_for(kind, record)
    if path is None:
        return None

    file_name = path.name
    embed.set_thumbnail(url=f"attachment://{file_name}")
    return discord.File(str(path), filename=file_name)
