from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

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


def _source(record: Dict[str, Any]) -> Dict[str, Any]:
    return record.get("source") or {}


def _status_line(record: Dict[str, Any]) -> str:
    source = _source(record)
    status = str(source.get("contentStatus", "Unreviewed"))
    bucket = str(source.get("sourceBucket", "Unknown"))
    return f"{status} • Source: {bucket}"


def _website(config: Any) -> Optional[str]:
    return getattr(config, "web_base_url", "") or None


def base_embed(title: str, description: str = "", color: discord.Color = OLIVE) -> discord.Embed:
    embed = discord.Embed(title=_clip(title, 256), description=_clip(description, 4096), color=color)
    embed.set_footer(text="SV13 // Survivor Database • Unity-backed field intelligence")
    return embed


def item_embed(record: Dict[str, Any], store: KnowledgeStore, config: Any) -> discord.Embed:
    name = record.get("name", "Unknown Item")
    desc = record.get("longDescription") or record.get("description") or "No field notes available."
    embed = base_embed(f"📦 SURVIVOR DATABASE // {name}", desc)

    embed.add_field(name="Category", value=_clip(record.get("categoryName") or "Unclassified"), inline=True)
    embed.add_field(name="Weight", value=f"{record.get('weight', 0):g}", inline=True)
    embed.add_field(name="Stack", value=str(record.get("stackSize", 1)), inline=True)

    rarity = record.get("rarityName") or "Unknown"
    embed.add_field(name="Rarity", value=_clip(rarity), inline=True)

    recipe = store.recipe_for_item(int(record.get("id", 0)))
    if recipe and recipe.get("hasIngredients"):
        embed.add_field(
            name="Crafting",
            value=f"Craftable • `/recipe {name}`",
            inline=True,
        )
    elif recipe:
        embed.add_field(name="Crafting", value="Recipe data exists, ingredients not confirmed", inline=True)

    data_types = record.get("dataTypes") or []
    if data_types:
        embed.add_field(name="Data", value=_clip(", ".join(data_types)), inline=False)

    embed.add_field(name="Intel Status", value=_status_line(record), inline=False)
    if _website(config):
        embed.url = _website(config)
    return embed


def recipe_embed(record: Dict[str, Any], config: Any) -> discord.Embed:
    name = record.get("resultItemName", "Unknown Recipe")
    embed = base_embed(f"🛠️ FIELD MANUAL // CRAFT {name}", "Crafting data exported directly from SV13.")

    reqs = record.get("requirements") or []
    if reqs:
        lines = [
            f"• **{r.get('itemName') or 'Unknown Item'}** × {r.get('amount', 0)}"
            + ("" if r.get("resolved") else " ⚠️")
            for r in reqs
        ]
        embed.add_field(name="Requirements", value=_clip("\n".join(lines)), inline=False)
    else:
        embed.add_field(name="Requirements", value="No confirmed ingredients exported.", inline=False)

    embed.add_field(name="Station", value=str(record.get("requiredStation") or "Generic"), inline=True)
    embed.add_field(name="Time", value=f"{float(record.get('craftDuration', 0)):g}s", inline=True)
    embed.add_field(name="Output", value=f"× {record.get('craftAmount', 1)}", inline=True)
    embed.add_field(name="Level", value=str(record.get("craftLevel", 0)), inline=True)
    embed.add_field(name="Intel Status", value=_status_line(record), inline=False)
    return embed


def building_embed(record: Dict[str, Any], config: Any) -> discord.Embed:
    name = record.get("name", "Unknown Buildable")
    desc = record.get("description") or "Construction definition."
    embed = base_embed(f"🏗️ CONSTRUCTION MANUAL // {name}", desc, color=AMBER)

    reqs = record.get("requirements") or []
    if reqs:
        lines = [
            f"• **{r.get('buildMaterialName') or 'Unknown Material'}** × {r.get('requiredAmount', 0)}"
            + ("" if r.get("resolved") else " ⚠️")
            for r in reqs
        ]
        embed.add_field(name="Materials", value=_clip("\n".join(lines)), inline=False)
    else:
        embed.add_field(name="Materials", value="No construction requirements exported.", inline=False)

    gate = record.get("assemblyGate") or {}
    if gate.get("found"):
        tool = gate.get("requiredToolDisplayName") or gate.get("requiredToolName") or "Tool"
        value = f"**{tool}** • {float(gate.get('assemblyDuration', 0)):g}s"
        if gate.get("useToolDurability"):
            value += f" • durability wear: {gate.get('toolWearMode') or 'enabled'}"
        embed.add_field(name="Assembly", value=_clip(value), inline=False)

    embed.add_field(
        name="Prefab",
        value="Resolved" if record.get("prefabResolved") else "⚠️ Missing/unresolved",
        inline=True,
    )
    embed.add_field(name="Category", value=str(record.get("categoryName") or "Unclassified"), inline=True)
    embed.add_field(name="Intel Status", value=_status_line(record), inline=False)
    return embed


def crop_embed(record: Dict[str, Any], config: Any) -> discord.Embed:
    name = record.get("cropName") or record.get("name") or "Unknown Crop"
    embed = base_embed(f"🌱 GROWER'S FIELD NOTE // {name}", color=OLIVE)

    embed.add_field(name="Seed", value=str(record.get("seedItemName") or "Unknown"), inline=True)
    embed.add_field(name="Produce", value=str(record.get("produceItemName") or "Unknown"), inline=True)
    embed.add_field(name="Yield", value=f"{record.get('minYield', 0)}–{record.get('maxYield', 0)}", inline=True)
    embed.add_field(name="Stage Time", value=f"{float(record.get('hoursPerStage', 0)):g} h", inline=True)
    embed.add_field(name="Water / Stage", value=str(record.get("waterPerStage", 0)), inline=True)
    embed.add_field(name="Rot After Mature", value=f"{float(record.get('hoursUntilRotAfterMature', 0)):g} h", inline=True)
    embed.add_field(
        name="Temperature",
        value=(
            f"Cold slow: {float(record.get('coldSlowTempC', 0)):g}°C\n"
            f"Cold kill: {float(record.get('coldKillTempC', 0)):g}°C\n"
            f"Heat kill: {float(record.get('heatKillTempC', 0)):g}°C"
        ),
        inline=False,
    )
    embed.add_field(name="Intel Status", value=_status_line(record), inline=False)
    return embed


def fishing_embed(record: Dict[str, Any], kind: str, config: Any) -> discord.Embed:
    if kind == "bait":
        name = record.get("baitName") or record.get("assetName") or "Unknown Bait"
        embed = base_embed(f"🎣 FIELD GUIDE // BAIT: {name}", record.get("description") or "", color=STEEL)
        embed.add_field(name="Tier", value=str(record.get("baitTier") or "Unknown"), inline=True)
        linked = record.get("linkedItems") or []
        if linked:
            embed.add_field(
                name="Linked Items",
                value=_clip("\n".join(f"• {r.get('name') or r.get('id')}" for r in linked)),
                inline=False,
            )
    else:
        name = record.get("lootName") or record.get("assetName") or "Unknown Catch"
        embed = base_embed(f"🎣 FIELD GUIDE // CATCH: {name}", record.get("description") or "", color=STEEL)
        embed.add_field(name="Tier", value=str(record.get("lootTier") or "Unknown"), inline=True)
        embed.add_field(name="Type", value=str(record.get("lootType") or "Unknown"), inline=True)
        embed.add_field(
            name="Weight",
            value=f"{float(record.get('minWeight', 0)):g}–{float(record.get('maxWeight', 0)):g}",
            inline=True,
        )
    embed.add_field(name="Intel Status", value=_status_line(record), inline=False)
    return embed


def document_embed(record: Dict[str, Any], config: Any) -> discord.Embed:
    title = record.get("title") or record.get("id") or "Recovered Document"
    pages = record.get("pages") or []
    text = pages[0] if pages else "No transcript exported."
    embed = base_embed(f"📄 RECOVERED INTEL // {title}", _clip(text, 3500), color=STEEL)
    embed.add_field(name="Document ID", value=str(record.get("id") or "Unknown"), inline=True)
    embed.add_field(name="Type", value=str(record.get("documentType") or "Unknown"), inline=True)
    embed.add_field(name="XP", value=str(record.get("xpReward", 0)), inline=True)
    if record.get("codexEntryId"):
        embed.add_field(name="Codex Entry", value=str(record["codexEntryId"]), inline=False)
    embed.add_field(name="Intel Status", value=_status_line(record), inline=False)
    return embed


def level_embed(record: Dict[str, Any], config: Any) -> discord.Embed:
    name = record.get("name") or record.get("assetName") or "Unknown Area"
    embed = base_embed(f"🗺️ AREA INTEL // {name}", record.get("description") or "", color=STEEL)
    embed.add_field(name="Scene", value=str(record.get("sceneName") or "Unknown"), inline=True)
    embed.add_field(name="Build Index", value=str(record.get("buildIndex", -1)), inline=True)
    embed.add_field(name="Intel Status", value=_status_line(record), inline=False)
    return embed


def hit_embed(hit: SearchHit, store: KnowledgeStore, config: Any) -> discord.Embed:
    if hit.kind == "item":
        return item_embed(hit.record, store, config)
    if hit.kind == "recipe":
        return recipe_embed(hit.record, config)
    if hit.kind == "building":
        return building_embed(hit.record, config)
    if hit.kind == "crop":
        return crop_embed(hit.record, config)
    if hit.kind in {"bait", "fishing"}:
        return fishing_embed(hit.record, hit.kind, config)
    if hit.kind == "document":
        return document_embed(hit.record, config)
    if hit.kind == "level":
        return level_embed(hit.record, config)
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
    counts = store.counts()
    embed = base_embed("📡 SV13 // KNOWLEDGE UPLINK STATUS")
    embed.add_field(name="Package", value=store.package_version or "Unknown", inline=False)
    embed.add_field(name="Items", value=str(counts["items"]), inline=True)
    embed.add_field(name="Recipes", value=str(counts["recipes"]), inline=True)
    embed.add_field(name="Buildables", value=str(counts["buildables"]), inline=True)
    embed.add_field(name="Crops", value=str(counts["crops"]), inline=True)
    embed.add_field(name="Documents", value=str(counts["documents"]), inline=True)
    embed.add_field(name="Maps / Levels", value=str(counts["levels"]), inline=True)
    embed.add_field(
        name="Validation",
        value=f"Warnings: {counts['validationWarnings']} • Errors: {counts['validationErrors']}",
        inline=False,
    )
    return embed


def sync_embed(store: KnowledgeStore, changed_files: List[str]) -> discord.Embed:
    counts = store.counts()
    embed = base_embed("📡 INTEL UPLINK // KNOWLEDGE PACKAGE UPDATED", color=AMBER)
    embed.add_field(name="Package", value=store.package_version or "Unknown", inline=False)
    embed.add_field(
        name="Changed Data",
        value=_clip(", ".join(changed_files) if changed_files else "Forced reload"),
        inline=False,
    )
    embed.add_field(
        name="Database",
        value=(
            f"{counts['items']} items • {counts['recipes']} recipes • "
            f"{counts['buildables']} buildables • {counts['crops']} crops"
        ),
        inline=False,
    )
    embed.add_field(
        name="Audit",
        value=f"{counts['validationWarnings']} warnings • {counts['validationErrors']} errors",
        inline=False,
    )
    return embed


def guide_embed(topic: str, store: KnowledgeStore) -> discord.Embed:
    topic = topic.lower()
    guides = {
        "crafting": (
            "🛠️ FIELD MANUAL // CRAFTING",
            "Use `/recipe <name>` for exact requirements, station, craft time and output. "
            "Use `/search <words> type:recipe` when you only remember part of the name.",
        ),
        "building": (
            "🏗️ FIELD MANUAL // CONSTRUCTION",
            "Use `/building <name>` for material requirements, linked prefab status and assembly-tool data.",
        ),
        "farming": (
            "🌱 FIELD MANUAL // FARMING",
            "Use `/crop <name>` for seed/produce links, stage time, water, yield and temperature limits.",
        ),
        "fishing": (
            "🎣 FIELD MANUAL // FISHING",
            "Use `/fishing <name>` to search bait and catch data exported from SV13.",
        ),
        "maps": (
            "🗺️ FIELD MANUAL // AREA INTEL",
            "Use `/map <name>` to query production-ready level definitions.",
        ),
        "codex": (
            "📄 FIELD MANUAL // RECOVERED INTEL",
            "Use `/codex <name or id>` to search recovered documents and lore records.",
        ),
        "search": (
            "🔎 SURVIVOR DATABASE // SEARCH",
            "Use `/search <query>` across items, recipes, construction, crops, fishing, documents and maps.",
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
