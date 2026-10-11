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


def _humanize(value: Any, store: KnowledgeStore) -> str:
    text = store.friendly_label(value)
    if not text:
        return ""
    # Keep established item/building naming untouched elsewhere; this helper is
    # only for scene hierarchy labels such as BuilderWorkshop / PowerSupply.
    out = []
    for i, char in enumerate(text):
        if i > 0 and char.isupper() and text[i - 1].islower():
            out.append(" ")
        out.append(char)
    return "".join(out).strip()


def _weather_fact(record: Dict[str, Any], key_suffix: str) -> Optional[str]:
    suffix = "." + key_suffix.lower()
    matches = [
        fact
        for fact in (record.get("facts") or [])
        if isinstance(fact, dict)
        and str(fact.get("key", "")).lower().endswith(suffix)
    ]
    if not matches:
        return None
    matches.sort(
        key=lambda f: (
            0 if str(f.get("sourceKind", "")) == "Scene" else 1,
            0 if str(f.get("sourceType", "")) == "SV13PlayerTemperature" else 1,
        )
    )
    return str(matches[0].get("value", "")).strip() or None


def _number(value: Optional[str], default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _percent(value: Optional[str]) -> str:
    return f"{_number(value) * 100:g}%"


def area_embed(
    record: Dict[str, Any],
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    name = store.display_name("area", record) or "Unknown Area"
    embed = base_embed(
        f"🗺️ AREA INTEL // {name}",
        record.get("description") or "",
        color=STEEL,
    )

    if not record.get("hasSceneCapture"):
        embed.add_field(
            name="Scene Intelligence",
            value="Detailed scene capture has not been completed for this area yet.",
            inline=False,
        )
    else:
        activities = [str(x) for x in (record.get("activities") or []) if str(x).strip()]
        if activities:
            embed.add_field(
                name="What You Can Do Here",
                value=_clip(" • ".join(activities)),
                inline=False,
            )

        upgrades = [x for x in (record.get("upgrades") or []) if isinstance(x, dict)]
        if upgrades:
            lines = []
            for upgrade in upgrades:
                upgrade_name = _humanize(upgrade.get("name"), store) or "Upgrade"
                caps = [str(x) for x in (upgrade.get("capabilities") or []) if str(x).strip()]
                detail = ", ".join(caps) if caps else "purpose still being resolved"
                lines.append(f"• **{upgrade_name}** — {detail}")
            embed.add_field(
                name=f"Player Cabin Upgrades ({len(upgrades)})",
                value=_clip("\n".join(lines)),
                inline=False,
            )

        docs = [x for x in (record.get("documents") or []) if isinstance(x, dict)]
        if docs:
            embed.add_field(
                name="Found Intel",
                value=_clip("\n".join(
                    f"• {store.friendly_label(d.get('name')) or d.get('id') or 'Document'}"
                    for d in docs
                )),
                inline=False,
            )

        features = [x for x in (record.get("specialFeatures") or []) if isinstance(x, dict)]
        if features:
            feature_lines = []
            for feature in features:
                fname = store.friendly_label(feature.get("name")) or "Special Feature"
                summary = str(feature.get("summary", "")).strip()
                feature_lines.append(f"• **{fname}**" + (f" — {summary}" if summary else ""))
            embed.add_field(
                name="Special Systems",
                value=_clip("\n".join(feature_lines)),
                inline=False,
            )

        weather = store.weather_for_area(record)
        if weather and store.is_public("weather", weather):
            scheduled = weather.get("scheduledWeatherTypes") or weather.get("stormTypes") or []
            value = ", ".join(str(x) for x in scheduled) or "Weather system detected"
            value += f"\nUse `/weather {name}` for survival effects and storm details."
            embed.add_field(name="Weather", value=_clip(value), inline=False)

        buildables = record.get("buildables") or []
        embed.add_field(
            name="Scene Knowledge",
            value=(
                f"{len(buildables)} linked buildables • "
                f"{len(record.get('uiKeys') or [])} linked UI records"
            ),
            inline=False,
        )

    if _website(config):
        embed.url = _website(config).rstrip("/") + "/maps/"
    return embed


def level_embed(
    record: Dict[str, Any],
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    area = store.area_for_level(record)
    if area is not None:
        return area_embed(area, store, config)

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


def weather_embed(
    record: Dict[str, Any],
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    area_name = store.display_name("weather", record) or "Unknown Area"
    embed = base_embed(
        f"🌨️ SURVIVAL INTEL // {area_name} WEATHER",
        "Authoritative environment and player-exposure settings captured from Unity.",
        color=STEEL,
    )

    scheduled = record.get("scheduledWeatherTypes") or record.get("stormTypes") or []
    supported = record.get("supportedHazardTypes") or []
    if scheduled:
        embed.add_field(
            name="Weather That Can Occur Here",
            value=_clip(" • ".join(str(x) for x in scheduled)),
            inline=False,
        )
    extra_supported = [x for x in supported if x not in scheduled]
    if extra_supported:
        embed.add_field(
            name="Other Supported Hazards",
            value=_clip(" • ".join(str(x) for x in extra_supported) +
                        "\nSupported by the game's warning/UI systems; not scheduled for this area."),
            inline=False,
        )

    cold = _weather_fact(record, "maxColdAmbientTempC")
    neutral = _weather_fact(record, "neutralAmbientTempC")
    heat = _weather_fact(record, "maxHeatAmbientTempC")
    if any(v is not None for v in (cold, neutral, heat)):
        embed.add_field(
            name="Temperature Model",
            value=(
                f"Maximum-cold point: **{_number(cold):g}°C**\n"
                f"Neutral point: **{_number(neutral):g}°C**\n"
                f"Maximum-heat point: **{_number(heat):g}°C**"
            ),
            inline=True,
        )

    stamina_start = _weather_fact(record, "staminaDrainStartsAtColdSeverity")
    max_stamina = _weather_fact(record, "maxStaminaDrainPerSecond")
    min_regen = _weather_fact(record, "minStaminaRegenMultiplierAtMaxCold")
    if any(v is not None for v in (stamina_start, max_stamina, min_regen)):
        embed.add_field(
            name="Cold → Stamina",
            value=(
                f"Drain begins: **{_percent(stamina_start)} cold severity**\n"
                f"Maximum drain: **{_number(max_stamina):g}/sec**\n"
                f"Regen at max cold: **{_percent(min_regen)}**"
            ),
            inline=True,
        )

    health_start = _weather_fact(record, "healthDrainStartsAtColdSeverity")
    grace = _weather_fact(record, "freezingGraceSeconds")
    max_health = _weather_fact(record, "maxHealthDrainPerSecond")
    ramp = _weather_fact(record, "freezingRampSeconds")
    if any(v is not None for v in (health_start, grace, max_health, ramp)):
        embed.add_field(
            name="Cold → Health",
            value=(
                f"Damage begins: **{_percent(health_start)} cold severity**\n"
                f"Grace period: **{_number(grace):g}s** • ramp: **{_number(ramp):g}s**\n"
                f"Maximum drain: **{_number(max_health):g}/sec**"
            ),
            inline=True,
        )

    cold_cap = _weather_fact(record, "_maxEffectiveColdProtection")
    heat_cap = _weather_fact(record, "_maxEffectiveHeatProtection")
    if cold_cap is not None or heat_cap is not None:
        embed.add_field(
            name="Wearable Protection Cap",
            value=f"Cold: **{_percent(cold_cap)}** • Heat: **{_percent(heat_cap)}**",
            inline=False,
        )

    chances = []
    for label, suffix in (
        ("Rain", "rainChance"),
        ("Thunderstorm", "thunderChance"),
        ("Light Snow", "lightSnowChance"),
        ("Heavy Snow", "heavySnowChance"),
        ("Blizzard", "blizzardChance"),
    ):
        value = _weather_fact(record, suffix)
        if value is not None:
            chances.append(f"{label} {_percent(value)}")
    if chances:
        duration_min = _weather_fact(record, "minDurationHours")
        duration_max = _weather_fact(record, "maxDurationHours")
        warning = _weather_fact(record, "warningLeadHours")
        extra = ""
        if duration_min is not None or duration_max is not None:
            extra += f"\nStorm duration: **{_number(duration_min):g}–{_number(duration_max):g} in-game hours**"
        if warning is not None:
            extra += f"\nWarning lead: **{_number(warning):g} in-game hour(s)**"
        embed.add_field(
            name="Cabin Weather Cycle",
            value=_clip(" • ".join(chances) + extra),
            inline=False,
        )

    shelter_temp = [
        _number(str(f.get("value", "0")))
        for f in (record.get("facts") or [])
        if isinstance(f, dict)
        and str(f.get("sourceType", "")) == "SV13ShelterVolume"
        and str(f.get("key", "")).lower().endswith(".temperaturebonusc")
    ]
    shelter_wind = [
        _number(str(f.get("value", "0")))
        for f in (record.get("facts") or [])
        if isinstance(f, dict)
        and str(f.get("sourceType", "")) == "SV13ShelterVolume"
        and str(f.get("key", "")).lower().endswith(".windprotection01")
    ]
    if shelter_temp or shelter_wind:
        temp_text = f"{min(shelter_temp):g}–{max(shelter_temp):g}°C bonus" if shelter_temp else "temperature protection varies"
        wind_text = f"{min(shelter_wind)*100:g}–{max(shelter_wind)*100:g}% wind protection" if shelter_wind else "wind protection varies"
        embed.add_field(
            name="Shelter",
            value=f"Detected shelter volumes provide **{temp_text}** and **{wind_text}**, depending on the structure.",
            inline=False,
        )

    if _website(config):
        embed.url = _website(config).rstrip("/") + "/maps/"
    return embed


def ui_embed(
    record: Dict[str, Any],
    store: KnowledgeStore,
    config: Any,
) -> discord.Embed:
    name = store.display_name("ui", record) or "Interface Element"
    category = store.friendly_label(record.get("category")) or "Interface"
    meaning = str(record.get("meaning", "")).strip() or f"UI element for {category}."
    embed = base_embed(
        f"◈ HUD / UI GUIDE // {name}",
        meaning,
        color=STEEL,
    )
    embed.add_field(name="Category", value=category, inline=True)
    embed.add_field(
        name="Context",
        value="Player HUD" if record.get("playerHud") else "Menu / interface",
        inline=True,
    )

    importance = str(record.get("importance", "")).strip()
    if importance:
        embed.add_field(name="Why It Matters", value=_clip(importance), inline=False)

    labels = [str(x).strip() for x in (record.get("visibleLabels") or []) if str(x).strip()]
    if labels:
        embed.add_field(
            name="Visible Text",
            value=_clip("\n".join(f"• {x}" for x in labels[:12])),
            inline=False,
        )

    scenes = [store.friendly_label(x) for x in (record.get("sourceScenes") or []) if str(x).strip()]
    if scenes:
        embed.add_field(name="Seen In", value=_clip(" • ".join(scenes)), inline=False)

    evidence = str(record.get("iconEvidenceKind", "")).strip()
    if evidence:
        readable = {
            "RenderedImage": "Rendered UI image",
            "RenderedRawImage": "Rendered UI texture",
            "ScriptIconReference": "Trusted runtime icon reference",
        }.get(evidence, store.friendly_label(evidence))
        embed.add_field(name="Icon Evidence", value=readable, inline=True)

    if _website(config):
        embed.url = _website(config)
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
    if hit.kind == "area":
        return area_embed(hit.record, store, config)
    if hit.kind == "weather":
        return weather_embed(hit.record, store, config)
    if hit.kind == "ui":
        return ui_embed(hit.record, store, config)
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
        "area": "🗺️",
        "weather": "🌨️",
        "ui": "◈",
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
        "area": "map",
        "weather": "weather",
        "ui": "ui",
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
            f"{raw['crops']} crops • {raw['documents']} documents • {raw['levels']} levels\n"
            f"{raw['areas']} area records • {raw['weatherProfiles']} weather profiles • "
            f"{raw['uiEntries']} UI guide entries"
        ),
        inline=False,
    )
    embed.add_field(
        name="Public Database",
        value=(
            f"{public['items']} items • {public['recipes']} recipes • "
            f"{public['buildables']} buildables\n"
            f"{public['crops']} crops • {public['documents']} documents • "
            f"{public['areas']} areas ({public['capturedAreas']} fully captured)\n"
            f"{public['weatherProfiles']} weather profiles • {public['uiEntries']} UI entries"
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
            f"{public['buildables']} buildables • {public['crops']} crops\n"
            f"{public['areas']} areas • {public['weatherProfiles']} weather profiles • "
            f"{public['uiEntries']} UI entries"
        ),
        inline=False,
    )
    embed.add_field(
        name="Raw Unity Package",
        value=(
            f"{raw['items']} items • {raw['recipes']} recipes • "
            f"{raw['buildables']} buildables • {raw['crops']} crops\n"
            f"{raw['areas']} areas • {raw['weatherProfiles']} weather profiles • "
            f"{raw['uiEntries']} UI entries"
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
            "Use `/map` for what each captured area contains: activities, upgrades, found intel, special systems and weather.",
        ),
        "weather": (
            "🌨️ FIELD MANUAL // WEATHER & SURVIVAL",
            "Use `/weather` to see scheduled storms plus the captured temperature, stamina, health, clothing-protection and shelter effects.",
        ),
        "interface": (
            "◈ FIELD MANUAL // HUD & UI",
            "Use `/ui` to identify HUD icons, status indicators, skill/perk controls and other player-facing interface elements.",
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
            f"{counts['buildables']} buildables • {counts['documents']} recovered documents\n"
            f"{counts['areas']} area records • {counts['weatherProfiles']} weather profiles • {counts['uiEntries']} UI entries"
        ),
        inline=False,
    )
    return embed
