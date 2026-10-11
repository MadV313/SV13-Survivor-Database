from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Sequence

import discord


log = logging.getLogger("sv13bot.forum_tags")

# Discord allows at most 20 available tags per forum and up to 5 tags on one
# forum post. Keep these catalogs compact so owner-created tags can coexist.
MANAGED_FORUM_TAGS: Dict[str, Sequence[str]] = {
    "items": (
        "Start Here",
        "Firearms",
        "Ammo",
        "Magazines",
        "Melee",
        "Tools",
        "Clothing",
        "Armor",
        "Backpacks",
        "Food",
        "Medical",
        "Resources",
        "Seeds",
        "Fishing",
        "Animals",
        "Keys",
        "Quest",
        "Currency",
        "Throwables",
    ),
    "crafting": (
        "Start Here",
        "General",
        "Ammo Reloading",
        "Workbench",
        "Medical",
        "Builder",
        "Food",
        "Weapons",
        "Clothing",
        "Tools",
    ),
    "building": (
        "Start Here",
        "Cabin Upgrade",
        "Construction",
        "Walls",
        "Roofs",
        "Platforms",
        "Doors",
        "Stairs",
        "Workstations",
        "Storage",
        "Shelter",
        "Fire",
        "Defense",
    ),
    "field": (
        "Start Here",
        "Crops",
        "Fishing",
        "Bait",
        "Maps",
        "Codex",
    ),
}


def tag_by_name(forum: discord.ForumChannel, name: str) -> discord.ForumTag | None:
    wanted = name.casefold()
    for tag in forum.available_tags:
        if tag.name.casefold() == wanted:
            return tag
    return None


def resolve_tags(
    forum: discord.ForumChannel,
    names: Iterable[str],
) -> List[discord.ForumTag]:
    resolved: List[discord.ForumTag] = []
    seen_ids = set()

    for name in names:
        tag = tag_by_name(forum, name)
        if tag is None or tag.id in seen_ids:
            continue
        resolved.append(tag)
        seen_ids.add(tag.id)
        if len(resolved) >= 5:
            break

    return resolved


async def ensure_managed_forum_tags(
    forum: discord.ForumChannel,
    channel_key: str,
) -> discord.ForumChannel:
    desired_names = MANAGED_FORUM_TAGS.get(channel_key, ())
    if not desired_names:
        return forum

    # Preserve every existing tag, including owner-created tags. Add all missing
    # managed tags in one channel edit so the local ForumChannel object is
    # refreshed with the IDs Discord assigned to the new tags.
    next_tags = list(forum.available_tags)
    existing_names = {tag.name.casefold() for tag in next_tags}
    changed = False

    for name in desired_names:
        if name.casefold() in existing_names:
            continue
        if len(next_tags) >= 20:
            log.warning(
                "Forum %s (%s) reached the 20-tag limit before managed tag %r "
                "could be added.",
                forum.name,
                forum.id,
                name,
            )
            break

        next_tags.append(discord.ForumTag(name=name[:20]))
        existing_names.add(name.casefold())
        changed = True

    if not changed:
        return forum

    try:
        updated = await forum.edit(
            available_tags=next_tags,
            reason="SV13 Survivor Database managed forum tags",
        )
        return updated if isinstance(updated, discord.ForumChannel) else forum
    except (discord.Forbidden, discord.HTTPException):
        log.exception(
            "Could not reconcile managed forum tags in %s (%s)",
            forum.name,
            forum.id,
        )
        return forum
