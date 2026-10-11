from __future__ import annotations

from typing import Any, Dict, List, Optional

import discord

from .knowledge import KnowledgeStore, SearchHit


OLIVE = discord.Color.from_rgb(91, 108, 73)
AMBER = discord.Color.from_rgb(176, 132, 69)
STEEL = discord.Color.from_rgb(82, 104, 119)
RED = discord.Color.from_rgb(145, 65, 60)


def _clip(value: Any, limit: int = 1024) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _website(config: Any) -> Optional[str]:
    return getattr(config, "web_base_url", "") or None


def base_embed(
    title: str,
    description: str = "",
    color: discord.Color = OLIVE,
) -> discord.Embed:
    embed = discord.Embed(
        title=_clip(title, 256),
        description=_clip(description, 4096),
        color=color,
    )
    embed.set_footer(text="SV13 // Survivor Database • Live field intelligence")
    return embed


def item_embed(
    record: Dict[str, Any],
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    name = store.display_name("item", record) or "Unknown Item"
    desc = (
        record.get("longDescription")
        or record.get("description")
        or "No field notes available."
    )
    embed = base_embed(f"📦 SURVIVOR DATABASE // {name}", desc)

    embed.add_field(
        name="Category",
        value=_clip(store.friendly_label(record.get("categoryName")) or "Unclassified"),
        inline=True,
    )
    embed.add_field(name="Weight", value=f"{float(record.get('weight', 0)):g}", inline=True)
    embed.add_field(name="Stack", value=str(record.get("stackSize", 1)), inline=True)
    embed.add_field(
        name="Rarity",
        value=_clip(store.rarity_label(record.get("rarityName"))),
        inline=True,
    )

    recipe = store.recipe_for_item(int(record.get("id", 0)))
    if recipe and recipe.get("hasIngredients"):
        embed.add_field(
            name="Crafting",
            value=f"Craftable • `/recipe {name}`",
            inline=True,
        )
    elif recipe:
        embed.add_field(
            name="Crafting",
            value="Crafting data exists, but ingredients are not confirmed.",
            inline=True,
        )

    if _website(config):
        embed.url = _website(config)
    return embed


def recipe_embed(
    record: Dict[str, Any],
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    name = store.display_name("recipe", record) or "Unknown Recipe"
    embed = base_embed(
        f"🛠️ FIELD MANUAL // CRAFT {name}",
        "Current crafting requirements from the Survivor Database.",
    )

    reqs = record.get("requirements") or []
    if reqs:
        lines = [
            f"• **{store.friendly_label(r.get('itemName')) or 'Unknown Item'}** × {r.get('amount', 0)}"
            + ("" if r.get("resolved") else " ⚠️")
            for r in reqs
        ]
        embed.add_field(
            name="Requirements",
            value=_clip("\n".join(lines)),
            inline=False,
        )
    else:
        embed.add_field(
            name="Requirements",
            value="No confirmed ingredients.",
            inline=False,
        )

    embed.add_field(
        name="Station",
        value=store.friendly_label(record.get("requiredStation")) or "Generic",
        inline=True,
    )
    embed.add_field(
        name="Time",
        value=f"{float(record.get('craftDuration', 0)):g}s",
        inline=True,
    )
    embed.add_field(
        name="Output",
        value=f"× {record.get('craftAmount', 1)}",
        inline=True,
    )
    level = int(record.get("craftLevel", 0) or 0)
    if level > 0:
        embed.add_field(name="Level", value=str(level), inline=True)
    return embed


def building_embed(
    record: Dict[str, Any],
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    name = store.display_name("building", record) or "Unknown Buildable"
    desc = record.get("description") or "Construction definition."
    embed = base_embed(
        f"🏗️ CONSTRUCTION MANUAL // {name}",
        desc,
        color=AMBER,
    )

    embed.add_field(
        name="Type",
        value=store.building_context(record),
        inline=False,
    )

    reqs = record.get("requirements") or []
    if reqs:
        lines = [
            f"• **{store.friendly_label(r.get('buildMaterialName')) or 'Unknown Material'}** × {r.get('requiredAmount', 0)}"
            + ("" if r.get("resolved") else " ⚠️")
            for r in reqs
        ]
        embed.add_field(
            name="Materials",
            value=_clip("\n".join(lines)),
            inline=False,
        )
    else:
        embed.add_field(
            name="Materials",
            value="No construction requirements listed.",
            inline=False,
        )

    gate = record.get("assemblyGate") or {}
    if gate.get("found"):
        tool = (
            store.friendly_label(
                gate.get("requiredToolDisplayName") or gate.get("requiredToolName")
            )
            or "Tool"
        )
        value = f"**{tool}** • {float(gate.get('assemblyDuration', 0)):g}s"
        if gate.get("useToolDurability"):
            value += " • uses tool durability"
        embed.add_field(name="Assembly", value=_clip(value), inline=False)

    category = store.friendly_label(record.get("categoryName"))
    if category and category.lower() not in store.building_context(record).lower():
        embed.add_field(name="Category", value=category, inline=True)
    return embed


def crop_embed(
    record: Dict[str, Any],
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    name = store.display_name("crop", record) or "Unknown Crop"
    embed = base_embed(f"🌱 GROWER'S FIELD NOTE // {name}", color=OLIVE)

    embed.add_field(
        name="Seed",
        value=store.friendly_label(record.get("seedItemName")) or "Unknown",
        inline=True,
    )
    embed.add_field(
        name="Produce",
        value=store.friendly_label(record.get("produceItemName")) or "Unknown",
        inline=True,
    )
    embed.add_field(
        name="Yield",
        value=f"{record.get('minYield', 0)}–{record.get('maxYield', 0)}",
        inline=True,
    )
    embed.add_field(
        name="Stage Time",
        value=f"{float(record.get('hoursPerStage', 0)):g} h",
        inline=True,
    )
    embed.add_field(
        name="Water / Stage",
        value=str(record.get("waterPerStage", 0)),
        inline=True,
    )
    embed.add_field(
        name="Rot After Mature",
        value=f"{float(record.get('hoursUntilRotAfterMature', 0)):g} h",
        inline=True,
    )
    embed.add_field(
        name="Temperature",
        value=(
            f"Cold slow: {float(record.get('coldSlowTempC', 0)):g}°C\n"
            f"Cold kill: {float(record.get('coldKillTempC', 0)):g}°C\n"
            f"Heat kill: {float(record.get('heatKillTempC', 0)):g}°C"
        ),
        inline=False,
    )
    return embed


def fishing_embed(
    record: Dict[str, Any],
    kind: str,
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    if kind == "bait":
        name = store.display_name("bait", record) or "Unknown Bait"
        embed = base_embed(
            f"🎣 FIELD GUIDE // BAIT: {name}",
            record.get("description") or "",
            color=STEEL,
        )
        embed.add_field(
            name="Tier",
            value=store.friendly_label(record.get("baitTier")) or "Unknown",
            inline=True,
        )
        linked = record.get("linkedItems") or []
        if linked:
            embed.add_field(
                name="Linked Items",
                value=_clip(
                    "\n".join(
                        f"• {store.friendly_label(r.get('name') or r.get('id'))}"
                        for r in linked
                    )
                ),
                inline=False,
            )
    else:
        name = store.display_name("fishing", record) or "Unknown Catch"
        embed = base_embed(
            f"🎣 FIELD GUIDE // CATCH: {name}",
            record.get("description") or "",
            color=STEEL,
        )
        embed.add_field(
            name="Tier",
            value=store.friendly_label(record.get("lootTier")) or "Unknown",
            inline=True,
        )
        embed.add_field(
            name="Type",
            value=store.friendly_label(record.get("lootType")) or "Unknown",
            inline=True,
        )
        min_weight = float(record.get("minWeight", 0))
        max_weight = float(record.get("maxWeight", 0))
        if min_weight or max_weight:
            embed.add_field(
                name="Weight",
                value=f"{min_weight:g}–{max_weight:g}",
                inline=True,
            )
    return embed


def document_embed(
    record: Dict[str, Any],
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    title = store.display_name("document", record) or "Recovered Document"
    pages = record.get("pages") or []
    text = pages[0] if pages else "No transcript exported."
    embed = base_embed(
        f"📄 RECOVERED INTEL // {title}",
        _clip(text, 3500),
        color=STEEL,
    )
    embed.add_field(
        name="Type",
        value=store.friendly_label(record.get("documentType")) or "Unknown",
        inline=True,
    )
    if int(record.get("xpReward", 0) or 0) > 0:
        embed.add_field(name="XP", value=str(record.get("xpReward", 0)), inline=True)
    return embed


def level_embed(
    record: Dict[str, Any],
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    name = store.display_name("level", record) or "Unknown Area"
    embed = base_embed(
        f"🗺️ AREA INTEL // {name}",
        record.get("description") or "",
        color=STEEL,
    )
    scene = store.friendly_label(record.get("sceneName"))
    if scene and scene.lower() != name.lower():
        embed.add_field(name="Scene", value=scene, inline=True)
    return embed


def hit_embed(
    hit: SearchHit,
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    if hit.kind == "item":
        return item_embed(hit.record, store, config)
    if hit.kind == "recipe":
        return recipe_embed(hit.record, store, config)
    if hit.kind == "building":
        return building_embed(hit.record, store, config)
    if hit.kind == "crop":
        return crop_embed(hit.record, store, config)
    if hit.kind in {"bait", "fishing"}:
        return fishing_embed(hit.record, hit.kind, store, config)
    if hit.kind == "document":
        return document_embed(hit.record, store, config)
    if hit.kind == "level":
        return level_embed(hit.record, store, config)
    return base_embed(f"SV13 // {hit.name}")


def search_results_embed(query: str, hits: List[SearchHit]) -> discord.Embed:
    embed = base_embed(f"🔎 SURVIVOR DATABASE // SEARCH: {query}")
    if not hits:
        embed.description = "No public database matches found."
        return embed

    lines = []
    icons = {
        "item": "📦",
        "recipe": "🛠️",
        "building": "🏗️",
        "crop": "🌱",
        "bait": "🎣",
        "fishing": "🎣",
        "document": "📄",
        "level": "🗺️",
    }
    command = {
        "item": "item",
        "recipe": "recipe",
        "building": "building",
        "crop": "crop",
        "bait": "fishing",
        "fishing": "fishing",
        "document": "codex",
        "level": "map",
    }
    for hit in hits:
        lines.append(
            f"{icons.get(hit.kind, '•')} **{hit.name}** — `{hit.kind}`\n"
            f"↳ `/{command.get(hit.kind, 'search')} {hit.name[:70]}`"
        )
    embed.description = _clip("\n\n".join(lines), 4000)
    return embed


def status_embed(store: KnowledgeStore) -> discord.Embed:
    raw = store.counts()
    public = store.public_counts()
    embed = base_embed("📡 SV13 // KNOWLEDGE UPLINK STATUS")
    embed.add_field(
        name="Package",
        value=store.package_version or "Unknown",
        inline=False,
    )
    embed.add_field(
        name="Raw Unity Package",
        value=(
            f"{raw['items']} items • {raw['recipes']} recipes • "
            f"{raw['buildables']} buildables\n"
            f"{raw['crops']} crops • {raw['documents']} documents • "
            f"{raw['levels']} maps / levels"
        ),
        inline=False,
    )
    embed.add_field(
        name="Public Database",
        value=(
            f"{public['items']} items • {public['recipes']} recipes • "
            f"{public['buildables']} buildables\n"
            f"{public['crops']} crops • {public['documents']} documents • "
            f"{public['levels']} maps / levels"
        ),
        inline=False,
    )
    embed.add_field(
        name="Validation",
        value=f"Warnings: {raw['validationWarnings']} • Errors: {raw['validationErrors']}",
        inline=False,
    )
    return embed


def sync_embed(store: KnowledgeStore, changed_files: List[str]) -> discord.Embed:
    raw = store.counts()
    public = store.public_counts()
    embed = base_embed(
        "📡 INTEL UPLINK // KNOWLEDGE PACKAGE UPDATED",
        color=AMBER,
    )
    embed.add_field(
        name="Package",
        value=store.package_version or "Unknown",
        inline=False,
    )
    embed.add_field(
        name="Changed Data",
        value=_clip(", ".join(changed_files) if changed_files else "Package metadata/version"),
        inline=False,
    )
    embed.add_field(
        name="Public Database",
        value=(
            f"{public['items']} items • {public['recipes']} recipes • "
            f"{public['buildables']} buildables • {public['crops']} crops"
        ),
        inline=False,
    )
    embed.add_field(
        name="Raw Unity Package",
        value=(
            f"{raw['items']} items • {raw['recipes']} recipes • "
            f"{raw['buildables']} buildables • {raw['crops']} crops"
        ),
        inline=False,
    )
    embed.add_field(
        name="Audit",
        value=f"{raw['validationWarnings']} warnings • {raw['validationErrors']} errors",
        inline=False,
    )
    return embed


def guide_embed(topic: str, store: KnowledgeStore) -> discord.Embed:
    topic = topic.lower()
    guides = {
        "crafting": (
            "🛠️ FIELD MANUAL // CRAFTING",
            "Use `/recipe` and start typing the name. Discord will offer current recipe choices automatically.",
        ),
        "building": (
            "🏗️ FIELD MANUAL // CONSTRUCTION",
            "Use `/building` and start typing to browse current construction entries and cabin upgrades.",
        ),
        "farming": (
            "🌱 FIELD MANUAL // FARMING",
            "Use `/crop` and start typing for seed, yield, water and temperature information.",
        ),
        "fishing": (
            "🎣 FIELD MANUAL // FISHING",
            "Use `/fishing` and start typing to browse current bait and catch intel.",
        ),
        "maps": (
            "🗺️ FIELD MANUAL // AREA INTEL",
            "Use `/map` and start typing to browse current areas.",
        ),
        "codex": (
            "📄 FIELD MANUAL // RECOVERED INTEL",
            "Use `/codex` and start typing to browse recovered documents.",
        ),
        "search": (
            "🔎 SURVIVOR DATABASE // SEARCH",
            "Use `/search` and start typing. Results and direct lookups are private to you so command use does not flood public channels.",
        ),
    }
    title, body = guides.get(topic, guides["search"])
    embed = base_embed(title, body)
    counts = store.counts()
    embed.add_field(
        name="Current Uplink",
        value=(
            f"{counts['items']} items • {counts['recipes']} recipes • "
            f"{counts['buildables']} buildables • {counts['documents']} recovered documents"
        ),
        inline=False,
    )
    return embed
