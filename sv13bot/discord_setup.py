from __future__ import annotations

from typing import Dict, Optional

import discord

from .config import BotConfig
from .embeds import base_embed
from .state import StateStore


CHANNEL_KEYS = {
    "terminal": "terminal",
    "intel": "intel",
    "items": "items",
    "crafting": "crafting",
    "building": "building",
    "field": "field",
}


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
            send_messages_in_threads=True,
        )

    category = discord.utils.get(guild.categories, name=config.category_name)
    if category is None:
        category = await guild.create_category(
            config.category_name,
            reason="SV13 Survivor Database automatic setup",
        )

    terminal = await _ensure_text(
        guild,
        config.terminal_channel_name,
        category,
        overwrites,
        "SV13 Survivor Database terminal. Bot-managed reference channel.",
    )
    intel = await _ensure_text(
        guild,
        config.intel_channel_name,
        category,
        overwrites,
        "Automatic Unity knowledge-package sync and field-intelligence updates.",
    )
    items = await _ensure_forum(
        guild,
        config.item_forum_name,
        category,
        overwrites,
        "SV13 item database generated from the authoritative Unity knowledge package.",
    )
    crafting = await _ensure_forum(
        guild,
        config.crafting_forum_name,
        category,
        overwrites,
        "SV13 crafting field manual generated from current recipe data.",
    )
    building = await _ensure_forum(
        guild,
        config.building_forum_name,
        category,
        overwrites,
        "SV13 construction manual generated from buildable definitions.",
    )
    field = await _ensure_forum(
        guild,
        config.field_forum_name,
        category,
        overwrites,
        "SV13 farming, fishing, map and recovered-document field guides.",
    )

    channels = {
        "terminal": terminal,
        "intel": intel,
        "items": items,
        "crafting": crafting,
        "building": building,
        "field": field,
    }

    for key, channel in channels.items():
        state.set_channel(guild.id, key, channel.id)

    await ensure_terminal_message(guild, terminal, config, state)
    return channels


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
        except (discord.NotFound, discord.Forbidden, ValueError):
            pass

    msg = await terminal.send(embed=_terminal_embed(config))
    try:
        await msg.pin(reason="SV13 Survivor Database terminal")
    except discord.Forbidden:
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
    name: str,
    category: discord.CategoryChannel,
    overwrites: Dict[discord.abc.Snowflake, discord.PermissionOverwrite],
    topic: str,
) -> discord.TextChannel:
    existing = discord.utils.get(guild.text_channels, name=name)
    if existing is not None:
        return existing
    return await guild.create_text_channel(
        name,
        category=category,
        topic=topic,
        overwrites=overwrites,
        reason="SV13 Survivor Database automatic setup",
    )


async def _ensure_forum(
    guild: discord.Guild,
    name: str,
    category: discord.CategoryChannel,
    overwrites: Dict[discord.abc.Snowflake, discord.PermissionOverwrite],
    topic: str,
) -> discord.ForumChannel:
    existing = discord.utils.get(guild.forums, name=name)
    if existing is not None:
        return existing
    return await guild.create_forum(
        name,
        category=category,
        topic=topic,
        overwrites=overwrites,
        reason="SV13 Survivor Database automatic setup",
    )
