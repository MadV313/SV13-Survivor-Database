from __future__ import annotations

from typing import Dict, Optional, Type, TypeVar

import discord

from .config import BotConfig
from .embeds import base_embed
from .state import StateStore


TChannel = TypeVar("TChannel", bound=discord.abc.GuildChannel)


async def ensure_discord_structure(
    guild: discord.Guild,
    config: BotConfig,
    state: StateStore,
) -> Dict[str, discord.abc.GuildChannel]:
    me = guild.me

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            create_public_threads=False,
            create_private_threads=False,
            send_messages_in_threads=False,
        )
    }
    if me is not None:
        overwrites[me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            read_message_history=True,
            manage_messages=True,
            manage_threads=True,
            create_public_threads=True,
            create_private_threads=True,
            send_messages_in_threads=True,
        )

    category = await _ensure_category(guild, config.category_name, state)

    terminal = await _ensure_text(
        guild,
        "terminal",
        config.terminal_channel_name,
        category,
        overwrites,
        "SV13 Survivor Database terminal. Bot-managed reference channel.",
        state,
    )
    intel = await _ensure_text(
        guild,
        "intel",
        config.intel_channel_name,
        category,
        overwrites,
        "Automatic Unity knowledge-package sync and field-intelligence updates.",
        state,
    )
    items = await _ensure_forum(
        guild,
        "items",
        config.item_forum_name,
        category,
        overwrites,
        "SV13 item database generated from the authoritative Unity knowledge package.",
        state,
    )
    crafting = await _ensure_forum(
        guild,
        "crafting",
        config.crafting_forum_name,
        category,
        overwrites,
        "SV13 crafting field manual generated from current recipe data.",
        state,
    )
    building = await _ensure_forum(
        guild,
        "building",
        config.building_forum_name,
        category,
        overwrites,
        "SV13 construction manual generated from buildable definitions.",
        state,
    )
    field = await _ensure_forum(
        guild,
        "field",
        config.field_forum_name,
        category,
        overwrites,
        "SV13 farming, fishing, map and recovered-document field guides.",
        state,
    )

    channels = {
        "terminal": terminal,
        "intel": intel,
        "items": items,
        "crafting": crafting,
        "building": building,
        "field": field,
    }

    await ensure_terminal_message(guild, terminal, config, state)
    return channels


async def _ensure_category(
    guild: discord.Guild,
    name: str,
    state: StateStore,
) -> discord.CategoryChannel:
    stored_id = state.get_channel(guild.id, "category")
    if stored_id:
        existing = guild.get_channel(stored_id)
        if isinstance(existing, discord.CategoryChannel):
            if existing.name != name:
                await existing.edit(
                    name=name,
                    reason="SV13 Survivor Database setup repair",
                )
            return existing

    category = discord.utils.get(guild.categories, name=name)
    if category is None:
        category = await guild.create_category(
            name,
            reason="SV13 Survivor Database automatic setup",
        )

    state.set_channel(guild.id, "category", category.id)
    return category


async def ensure_terminal_message(
    guild: discord.Guild,
    terminal: discord.TextChannel,
    config: BotConfig,
    state: StateStore,
) -> None:
    existing_id = state.get_meta(guild.id, "terminal_message_id")
    if existing_id:
        try:
            msg = await terminal.fetch_message(int(existing_id))
            await msg.edit(embed=_terminal_embed(config))
            return
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
            pass

    msg = await terminal.send(embed=_terminal_embed(config))
    try:
        await msg.pin(reason="SV13 Survivor Database terminal")
    except (discord.Forbidden, discord.HTTPException):
        pass
    state.set_meta(guild.id, "terminal_message_id", str(msg.id))


def _terminal_embed(config: BotConfig) -> discord.Embed:
    embed = base_embed(
        "☢️ SV13 // SURVIVOR DATABASE",
        "A live field manual backed by SV13's Unity knowledge export.\n\n"
        "Search the database from anywhere in the server with slash commands.",
    )
    embed.add_field(
        name="General Search",
        value="`/search` • `/guide`",
        inline=False,
    )
    embed.add_field(
        name="Direct Intel",
        value="`/item` • `/recipe` • `/building` • `/crop` • `/fishing` • `/map` • `/codex`",
        inline=False,
    )
    embed.add_field(
        name="Uplink",
        value="`/sv13status` shows the currently loaded Unity knowledge package.",
        inline=False,
    )
    if config.web_base_url:
        embed.add_field(name="Web Field Manual", value=config.web_base_url, inline=False)
    return embed


async def get_configured_channel(
    guild: discord.Guild,
    state: StateStore,
    key: str,
) -> Optional[discord.abc.GuildChannel]:
    channel_id = state.get_channel(guild.id, key)
    if not channel_id:
        return None
    return guild.get_channel(channel_id)


async def _ensure_text(
    guild: discord.Guild,
    key: str,
    name: str,
    category: discord.CategoryChannel,
    overwrites: Dict[discord.abc.Snowflake, discord.PermissionOverwrite],
    topic: str,
    state: StateStore,
) -> discord.TextChannel:
    existing = _stored_channel(guild, state, key, discord.TextChannel)
    if existing is None:
        existing = discord.utils.get(category.text_channels, name=name)

    if existing is None:
        existing = await guild.create_text_channel(
            name,
            category=category,
            topic=topic,
            overwrites=overwrites,
            reason="SV13 Survivor Database automatic setup",
        )
    else:
        await existing.edit(
            name=name,
            category=category,
            topic=topic,
            overwrites=overwrites,
            reason="SV13 Survivor Database setup repair",
        )

    state.set_channel(guild.id, key, existing.id)
    return existing


async def _ensure_forum(
    guild: discord.Guild,
    key: str,
    name: str,
    category: discord.CategoryChannel,
    overwrites: Dict[discord.abc.Snowflake, discord.PermissionOverwrite],
    topic: str,
    state: StateStore,
) -> discord.ForumChannel:
    existing = _stored_channel(guild, state, key, discord.ForumChannel)
    if existing is None:
        existing = discord.utils.get(category.channels, name=name)
        if existing is not None and not isinstance(existing, discord.ForumChannel):
            existing = None

    if existing is None:
        existing = await guild.create_forum(
            name,
            category=category,
            topic=topic,
            overwrites=overwrites,
            reason="SV13 Survivor Database automatic setup",
        )
    else:
        await existing.edit(
            name=name,
            category=category,
            topic=topic,
            overwrites=overwrites,
            reason="SV13 Survivor Database setup repair",
        )

    state.set_channel(guild.id, key, existing.id)
    return existing


def _stored_channel(
    guild: discord.Guild,
    state: StateStore,
    key: str,
    expected_type: Type[TChannel],
) -> Optional[TChannel]:
    channel_id = state.get_channel(guild.id, key)
    if not channel_id:
        return None
    channel = guild.get_channel(channel_id)
    return channel if isinstance(channel, expected_type) else None
