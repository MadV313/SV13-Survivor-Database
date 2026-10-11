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


def requirement_media(store: KnowledgeStore, kind: str, record: Dict[str, Any]):
    """Return (embeds, files, fingerprint) for available crafting material sprites.

    Missing sprites are deliberately omitted; the authoritative text requirements
    remain in the main embed. Keep within Discord's ten-embed/file limits.
    """
    if kind not in {"recipe", "building"}:
        return [], [], []
    requirements = record.get("requirements") or []
    material_by_id = {int(m.get("id", 0)): m for m in store.build_materials}
    item_by_id = {int(i.get("id", 0)): i for i in store.items}
    embeds, files, fingerprint = [], [], []
    seen = set()
    for req in requirements:
        if not isinstance(req, dict):
            continue
        if kind == "recipe":
            source = item_by_id.get(int(req.get("itemId") or 0))
            amount = req.get("amount", 0)
            name = req.get("itemName", "Material")
        else:
            source = material_by_id.get(int(req.get("buildMaterialId") or 0))
            amount = req.get("requiredAmount", 0)
            name = req.get("buildMaterialName", "Material")
        if not source:
            continue
        path = store.media_path_for("item" if kind == "recipe" else "building", source)
        if path is None:
            continue
        # Multiple repeated requirements use one image, never duplicate filename.
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        sprite_name = path.name
        graphic = discord.Embed(
            title=f"{store.friendly_label(name)} × {amount}"[:256],
            color=discord.Color.from_rgb(176, 132, 69),
        )
        graphic.set_thumbnail(url=f"attachment://{sprite_name}")
        embeds.append(graphic)
        files.append(discord.File(str(path), filename=sprite_name))
        fingerprint.append((sprite_name, store._file_hashes.get(sprite_name, "")))
        if len(embeds) >= 9:
            break
    return embeds, files, fingerprint
