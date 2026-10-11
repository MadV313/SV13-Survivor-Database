from __future__ import annotations

from typing import Dict, Optional, Sequence, Type, TypeVar, Tuple

import discord

from .config import BotConfig
from .embeds import base_embed
from .forum_tags import ensure_managed_forum_tags, resolve_tags
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
            attach_files=True,
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
        "SV13 item database generated from the authoritative game-data package.",
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
        "SV13 construction manual and Player Cabin upgrade records.",
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

    # Reconcile bot-managed forum tags without deleting any owner-created tags.
    items = await ensure_managed_forum_tags(items, "items")
    crafting = await ensure_managed_forum_tags(crafting, "crafting")
    building = await ensure_managed_forum_tags(building, "building")
    field = await ensure_managed_forum_tags(field, "field")

    channels = {
        "terminal": terminal,
        "intel": intel,
        "items": items,
        "crafting": crafting,
        "building": building,
        "field": field,
    }

    await ensure_terminal_message(guild, terminal, config, state)
    await _ensure_text_intro(
        guild,
        intel,
        state,
        "intel_intro_message_id",
        base_embed(
            "📡 SV13 // INTEL UPDATES",
            "This channel is maintained by the Survivor Database. "
            "Knowledge-package refreshes and database update notices appear here automatically.",
        ),
    )

    await _ensure_forum_intro(
        guild,
        items,
        state,
        "items",
        "START HERE // ITEM INDEX",
        base_embed(
            "📦 ITEM INDEX // START HERE",
            "Bot-managed item reference posts live here. "
            "For a private lookup anywhere in the server, use `/item` and start typing a name.",
        ),
        tag_names=("Start Here",),
    )
    await _ensure_forum_intro(
        guild,
        crafting,
        state,
        "crafting",
        "START HERE // CRAFTING MANUAL",
        base_embed(
            "🛠️ CRAFTING MANUAL // START HERE",
            "Recipes published here come from the current SV13 knowledge package. "
            "Use `/recipe` and start typing to browse current choices privately.",
        ),
        tag_names=("Start Here",),
    )
    await _ensure_forum_intro(
        guild,
        building,
        state,
        "building",
        "START HERE // CONSTRUCTION MANUAL",
        base_embed(
            "🏗️ CONSTRUCTION MANUAL // START HERE",
            "Build requirements, assembly information and Player Cabin upgrades are indexed here. "
            "Use `/building` and start typing for a private lookup.",
        ),
        tag_names=("Start Here",),
    )
    await _ensure_forum_intro(
        guild,
        field,
        state,
        "field",
        "START HERE // FIELD MANUAL",
        base_embed(
            "🌲 FIELD MANUAL // START HERE",
            "Farming, fishing, area intel and recovered documents are collected here. "
            "Use `/crop`, `/fishing`, `/map` or `/codex` and start typing to browse.",
        ),
        tag_names=("Start Here",),
    )

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
    await _ensure_text_intro(
        guild,
        terminal,
        state,
        "terminal_message_id",
        _terminal_embed(config),
    )


async def _ensure_text_intro(
    guild: discord.Guild,
    channel: discord.TextChannel,
    state: StateStore,
    meta_key: str,
    embed: discord.Embed,
) -> None:
    existing_id = state.get_meta(guild.id, meta_key)
    if existing_id:
        try:
            msg = await channel.fetch_message(int(existing_id))
            await msg.edit(embed=embed)
            if not msg.pinned:
                await msg.pin(reason="SV13 Survivor Database channel guide")
            return
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
            pass

    msg = await channel.send(embed=embed)
    try:
        await msg.pin(reason="SV13 Survivor Database channel guide")
    except (discord.Forbidden, discord.HTTPException):
        pass
    state.set_meta(guild.id, meta_key, str(msg.id))


async def _ensure_forum_intro(
    guild: discord.Guild,
    forum: discord.ForumChannel,
    state: StateStore,
    key: str,
    title: str,
    embed: discord.Embed,
    tag_names: Sequence[str] = (),
) -> None:
    thread_meta = f"{key}_intro_thread_id"
    message_meta = f"{key}_intro_message_id"
    desired_tags = resolve_tags(forum, tag_names)

    thread_id = state.get_meta(guild.id, thread_meta)
    message_id = state.get_meta(guild.id, message_meta)

    if thread_id and message_id:
        try:
            thread = guild.get_thread(int(thread_id))
            if thread is None:
                fetched = await guild.fetch_channel(int(thread_id))
                thread = fetched if isinstance(fetched, discord.Thread) else None
            if thread is not None:
                edit_kwargs = {}
                if thread.archived:
                    edit_kwargs["archived"] = False
                if {tag.id for tag in thread.applied_tags} != {
                    tag.id for tag in desired_tags
                }:
                    edit_kwargs["applied_tags"] = desired_tags
                if edit_kwargs:
                    thread = await thread.edit(
                        **edit_kwargs,
                        reason="SV13 Survivor Database forum guide repair",
                    )

                message = await thread.fetch_message(int(message_id))
                await message.edit(embed=embed)
                if not message.pinned:
                    await message.pin(reason="SV13 Survivor Database forum guide")
                return
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
            pass

    create_kwargs = {
        "name": title[:100],
        "embed": embed,
        "reason": "SV13 Survivor Database forum guide",
    }
    if desired_tags:
        create_kwargs["applied_tags"] = desired_tags

    result = await forum.create_thread(**create_kwargs)
    thread, message = _unpack_forum_thread(result)
    if thread is None or message is None:
        return

    try:
        await message.pin(reason="SV13 Survivor Database forum guide")
    except (discord.Forbidden, discord.HTTPException):
        pass

    state.set_meta(guild.id, thread_meta, str(thread.id))
    state.set_meta(guild.id, message_meta, str(message.id))


def _unpack_forum_thread(result: object) -> Tuple[Optional[discord.Thread], Optional[discord.Message]]:
    thread = getattr(result, "thread", None)
    message = getattr(result, "message", None)
    if isinstance(thread, discord.Thread) and isinstance(message, discord.Message):
        return thread, message

    if isinstance(result, tuple) and len(result) >= 2:
        maybe_thread, maybe_message = result[0], result[1]
        if isinstance(maybe_thread, discord.Thread) and isinstance(maybe_message, discord.Message):
            return maybe_thread, maybe_message

    return None, None


def _terminal_embed(config: BotConfig) -> discord.Embed:
    embed = base_embed(
        "☢️ SV13 // SURVIVOR DATABASE",
        "A live field manual backed by SV13's current game-data export.\n\n"
        "Player lookups are private to the person using the command, so normal searches do not flood public channels.",
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
        name="How to Search",
        value="Choose a command and start typing. Discord will suggest current database entries automatically.",
        inline=False,
    )
    embed.add_field(
        name="Uplink",
        value="`/sv13status` shows the currently loaded knowledge package.",
        inline=False,
    )
    if config.web_base_url:
        embed.add_field(
            name="Web Field Manual",
            value=config.web_base_url,
            inline=False,
        )
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
