from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, Dict, Optional, Tuple

import discord

from .config import BotConfig
from .discord_setup import get_configured_channel
from .embeds import (
    building_embed,
    crop_embed,
    document_embed,
    fishing_embed,
    item_embed,
    level_embed,
    recipe_embed,
)
from .knowledge import KnowledgeStore
from .state import StateStore


class KnowledgePublisher:
    def __init__(
        self,
        config: BotConfig,
        store: KnowledgeStore,
        state: StateStore,
    ):
        self.config = config
        self.store = store
        self.state = state
        self._lock = asyncio.Lock()

    async def publish_changed(
        self,
        guild: discord.Guild,
        scope: str = "all",
        limit: int = 50,
    ) -> Dict[str, int]:
        created = 0
        updated = 0
        unchanged = 0
        skipped = 0

        async with self._lock:
            for kind, record in self.store.public_entities(scope):
                if created + updated >= max(1, limit):
                    break

                channel_key = self._channel_key(kind)
                channel = await get_configured_channel(guild, self.state, channel_key)
                if not isinstance(channel, discord.ForumChannel):
                    skipped += 1
                    continue

                entity_key = self.store.entity_key(kind, record)
                payload = {"kind": kind, "record": record}
                content_hash = hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()

                prior = self.state.get_published(guild.id, entity_key)
                if prior and prior.get("content_hash") == content_hash:
                    unchanged += 1
                    continue

                embed = self._embed(kind, record)
                title = self._thread_title(kind, record)

                if prior:
                    ok = await self._update_existing(guild, prior, title, embed)
                    if ok:
                        self.state.upsert_published(
                            guild.id,
                            entity_key,
                            kind,
                            content_hash,
                            int(prior["channel_id"]),
                            int(prior["thread_id"]),
                            int(prior["message_id"]),
                            payload,
                        )
                        updated += 1
                        await asyncio.sleep(0.35)
                        continue

                result = await channel.create_thread(
                    name=title[:100],
                    embed=embed,
                    reason="SV13 knowledge publisher",
                )
                thread, message = self._unpack_thread_result(result)
                if thread is None or message is None:
                    skipped += 1
                    continue

                self.state.upsert_published(
                    guild.id,
                    entity_key,
                    kind,
                    content_hash,
                    channel.id,
                    thread.id,
                    message.id,
                    payload,
                )
                created += 1
                await asyncio.sleep(0.75)

        return {
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "skipped": skipped,
            "changed": created + updated,
        }

    async def _update_existing(
        self,
        guild: discord.Guild,
        prior: Dict[str, Any],
        title: str,
        embed: discord.Embed,
    ) -> bool:
        try:
            thread = guild.get_thread(int(prior["thread_id"]))
            if thread is None:
                fetched = await guild.fetch_channel(int(prior["thread_id"]))
                thread = fetched if isinstance(fetched, discord.Thread) else None

            if thread is None:
                return False

            if thread.name != title[:100]:
                await thread.edit(name=title[:100], reason="SV13 knowledge refresh")

            message = await thread.fetch_message(int(prior["message_id"]))
            await message.edit(embed=embed)
            return True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
            return False

    @staticmethod
    def _unpack_thread_result(result: Any) -> Tuple[Optional[discord.Thread], Optional[discord.Message]]:
        thread = getattr(result, "thread", None)
        message = getattr(result, "message", None)
        if thread is not None and message is not None:
            return thread, message

        if isinstance(result, tuple) and len(result) >= 2:
            maybe_thread, maybe_message = result[0], result[1]
            if isinstance(maybe_thread, discord.Thread) and isinstance(maybe_message, discord.Message):
                return maybe_thread, maybe_message

        return None, None

    def _embed(self, kind: str, record: Dict[str, Any]) -> discord.Embed:
        if kind == "item":
            return item_embed(record, self.store, self.config)
        if kind == "recipe":
            return recipe_embed(record, self.config)
        if kind == "building":
            return building_embed(record, self.config)
        if kind == "crop":
            return crop_embed(record, self.config)
        if kind in {"bait", "fishing"}:
            return fishing_embed(record, kind, self.config)
        if kind == "document":
            return document_embed(record, self.config)
        if kind == "level":
            return level_embed(record, self.config)
        raise ValueError(f"Unsupported publish kind: {kind}")

    def _thread_title(self, kind: str, record: Dict[str, Any]) -> str:
        prefix = {
            "item": "ITEM",
            "recipe": "CRAFT",
            "building": "BUILD",
            "crop": "GROW",
            "bait": "BAIT",
            "fishing": "CATCH",
            "document": "INTEL",
            "level": "AREA",
        }.get(kind, "SV13")
        return f"{prefix} // {self.store.display_name(kind, record)}"

    @staticmethod
    def _channel_key(kind: str) -> str:
        if kind == "item":
            return "items"
        if kind == "recipe":
            return "crafting"
        if kind == "building":
            return "building"
        return "field"
