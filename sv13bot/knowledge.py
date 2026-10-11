from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


DATA_FILES = {
    "items": "items.json",
    "recipes": "recipes.json",
    "categories": "item_categories.json",
    "buildables": "buildables.json",
    "build_materials": "build_materials.json",
    "crops": "crops.json",
    "fishing": "fishing.json",
    "documents": "documents.json",
    "levels": "levels.json",
    "loot_tables": "loot_tables.json",
    "validation": "validation.json",
}

# Scene/world intelligence was added after the original bot shipped. Keep these
# optional so a rolling Railway deploy can still boot against the previous
# package while the new Unity export is being published to the website.
OPTIONAL_DATA_FILES = {
    "areas": "areas.json",
    "weather": "weather.json",
    "ui": "ui.json",
}


@dataclass
class SearchHit:
    kind: str
    key: str
    name: str
    score: float
    record: Dict[str, Any]
    public: bool


class KnowledgeStore:
    def __init__(self, knowledge_dir: Path, public_statuses: Iterable[str]):
        self.knowledge_dir = Path(knowledge_dir)
        self.public_statuses = frozenset(public_statuses)

        self.manifest: Dict[str, Any] = {}
        self.items: List[Dict[str, Any]] = []
        self.recipes: List[Dict[str, Any]] = []
        self.categories: List[Dict[str, Any]] = []
        self.buildables: List[Dict[str, Any]] = []
        self.build_materials: List[Dict[str, Any]] = []
        self.crops: List[Dict[str, Any]] = []
        self.fishing: Dict[str, List[Dict[str, Any]]] = {"baits": [], "loot": []}
        self.documents: List[Dict[str, Any]] = []
        self.levels: List[Dict[str, Any]] = []
        self.loot_tables: List[Dict[str, Any]] = []
        self.areas: List[Dict[str, Any]] = []
        self.weather: List[Dict[str, Any]] = []
        self.ui: List[Dict[str, Any]] = []
        self.validation: List[Dict[str, Any]] = []
        self.media_index: Dict[str, str] = {}

        self._manifest_fingerprint = ""
        self._file_hashes: Dict[str, str] = {}
        self._indexes: Dict[str, List[Dict[str, Any]]] = {}

    @property
    def package_version(self) -> str:
        return str(self.manifest.get("packageVersion", ""))

    @property
    def generated_utc(self) -> str:
        return str(self.manifest.get("generatedUtc", ""))

    @property
    def manifest_fingerprint(self) -> str:
        return self._manifest_fingerprint

    @property
    def file_hashes(self) -> Dict[str, str]:
        return dict(self._file_hashes)

    def validate_path(self) -> None:
        manifest = self.knowledge_dir / "manifest.json"
        if not manifest.is_file():
            raise FileNotFoundError(
                f"manifest.json was not found in SV13_KNOWLEDGE_DIR: {self.knowledge_dir}"
            )

    def load(self) -> None:
        self.validate_path()

        manifest = self._read_json("manifest.json")
        if not isinstance(manifest, dict):
            raise RuntimeError("manifest.json must contain a JSON object.")

        self._verify_manifest_files(manifest)

        items = self._read_json(DATA_FILES["items"])
        recipes = self._read_json(DATA_FILES["recipes"])
        categories = self._read_json(DATA_FILES["categories"])
        buildables = self._read_json(DATA_FILES["buildables"])
        build_materials = self._read_json(DATA_FILES["build_materials"])
        crops = self._read_json(DATA_FILES["crops"])
        fishing = self._read_json(DATA_FILES["fishing"])
        documents = self._read_json(DATA_FILES["documents"])
        levels = self._read_json(DATA_FILES["levels"])
        loot_tables = self._read_json(DATA_FILES["loot_tables"])
        validation = self._read_json(DATA_FILES["validation"])

        areas = self._read_optional_array(OPTIONAL_DATA_FILES["areas"])
        weather = self._read_optional_array(OPTIONAL_DATA_FILES["weather"])
        ui = self._read_optional_array(OPTIONAL_DATA_FILES["ui"])

        media_index: Dict[str, str] = {}
        media_index_path = self.knowledge_dir / "media_index.json"
        if media_index_path.is_file():
            raw_media = self._read_json("media_index.json")
            if isinstance(raw_media, dict):
                assets = raw_media.get("assets", [])
                if isinstance(assets, list):
                    for entry in assets:
                        if not isinstance(entry, dict):
                            continue
                        asset_path = str(entry.get("assetPath", "")).strip()
                        file_name = str(entry.get("fileName", "")).strip()
                        if asset_path and file_name:
                            media_index[asset_path] = file_name

        for label, value in (
            ("items", items),
            ("recipes", recipes),
            ("categories", categories),
            ("buildables", buildables),
            ("build_materials", build_materials),
            ("crops", crops),
            ("documents", documents),
            ("levels", levels),
            ("loot_tables", loot_tables),
            ("validation", validation),
        ):
            if not isinstance(value, list):
                raise RuntimeError(f"{DATA_FILES[label]} must contain a JSON array.")

        if not isinstance(fishing, dict):
            raise RuntimeError("fishing.json must contain a JSON object.")
        if not isinstance(fishing.get("baits", []), list) or not isinstance(
            fishing.get("loot", []), list
        ):
            raise RuntimeError("fishing.json must contain baits[] and loot[] arrays.")

        file_hashes = {
            str(entry.get("fileName", "")): str(entry.get("sha256", ""))
            for entry in manifest.get("files", [])
            if isinstance(entry, dict) and entry.get("fileName")
        }

        raw = json.dumps(
            {
                "package": str(manifest.get("packageVersion", "")),
                "files": sorted(file_hashes.items()),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        manifest_fingerprint = hashlib.sha256(raw).hexdigest()

        # Assign only after the entire package has parsed and validated.
        self.manifest = manifest
        self.items = items
        self.recipes = recipes
        self.categories = categories
        self.buildables = buildables
        self.build_materials = build_materials
        self.crops = crops
        self.fishing = fishing
        self.documents = documents
        self.levels = levels
        self.loot_tables = loot_tables
        self.areas = areas
        self.weather = weather
        self.ui = ui
        self.validation = validation
        self.media_index = media_index
        self._file_hashes = file_hashes
        self._manifest_fingerprint = manifest_fingerprint
        self._rebuild_indexes()

    def _verify_manifest_files(self, manifest: Dict[str, Any]) -> None:
        entries = manifest.get("files") or []
        if not isinstance(entries, list):
            raise RuntimeError("manifest.json files must be an array.")

        entry_map = {
            str(entry.get("fileName", "")): entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("fileName")
        }

        required = set(DATA_FILES.values())
        missing_manifest_entries = sorted(required - set(entry_map))
        if missing_manifest_entries:
            raise RuntimeError(
                "manifest.json is missing required data entries: "
                + ", ".join(missing_manifest_entries)
            )

        for name, entry in entry_map.items():
            path = self.knowledge_dir / name
            if not path.is_file():
                raise FileNotFoundError(
                    f"Knowledge package file listed by manifest is missing: {path}"
                )

            expected_bytes = entry.get("bytes")
            if isinstance(expected_bytes, int) and expected_bytes >= 0:
                actual_bytes = path.stat().st_size
                if actual_bytes != expected_bytes:
                    raise RuntimeError(
                        f"Knowledge byte-count mismatch for {name}: "
                        f"expected {expected_bytes}, got {actual_bytes}"
                    )

            expected_hash = str(entry.get("sha256", "")).strip().lower()
            if expected_hash:
                actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual_hash != expected_hash:
                    raise RuntimeError(
                        f"Knowledge hash mismatch for {name}: "
                        f"expected {expected_hash}, got {actual_hash}"
                    )

    def reload_if_changed(self, force: bool = False) -> tuple[bool, List[str]]:
        self.validate_path()
        manifest = self._read_json("manifest.json")
        entries = manifest.get("files") or []
        if not isinstance(entries, list):
            raise RuntimeError("manifest.json files must be an array.")

        next_hashes = {
            str(entry.get("fileName", "")): str(entry.get("sha256", ""))
            for entry in entries
            if isinstance(entry, dict) and entry.get("fileName")
        }
        raw = json.dumps(
            {
                "package": str(manifest.get("packageVersion", "")),
                "files": sorted(next_hashes.items()),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        next_fingerprint = hashlib.sha256(raw).hexdigest()

        if not force and next_fingerprint == self._manifest_fingerprint:
            return False, []

        before = self._file_hashes
        changed = sorted(
            {
                name
                for name in set(before) | set(next_hashes)
                if before.get(name) != next_hashes.get(name)
            }
        )
        self.load()
        return True, changed

    def counts(self) -> Dict[str, int]:
        counts = self.manifest.get("counts", {})
        return {
            "items": int(counts.get("items", len(self.items))),
            "recipes": int(counts.get("recipes", len(self.recipes))),
            "buildables": int(counts.get("buildables", len(self.buildables))),
            "crops": int(counts.get("crops", len(self.crops))),
            "documents": int(counts.get("documents", len(self.documents))),
            "levels": int(counts.get("levels", len(self.levels))),
            "areas": int(counts.get("areas", len(self.areas))),
            "weatherProfiles": int(counts.get("weatherProfiles", len(self.weather))),
            "uiEntries": int(counts.get("uiEntries", len(self.ui))),
            "validationWarnings": int(counts.get("validationWarnings", 0)),
            "validationErrors": int(counts.get("validationErrors", 0)),
        }

    def public_counts(self) -> Dict[str, int]:
        return {
            "items": sum(1 for r in self.items if self.is_public("item", r)),
            "recipes": sum(1 for r in self.recipes if self.is_public("recipe", r)),
            "buildables": sum(
                1 for r in self.buildables if self.is_public("building", r)
            ),
            "crops": sum(1 for r in self.crops if self.is_public("crop", r)),
            "documents": sum(
                1 for r in self.documents if self.is_public("document", r)
            ),
            "levels": sum(1 for r in self.levels if self.is_public("level", r)),
            "areas": sum(1 for r in self.areas if self.is_public("area", r)),
            "capturedAreas": sum(
                1
                for r in self.areas
                if self.is_public("area", r) and bool(r.get("hasSceneCapture"))
            ),
            "weatherProfiles": sum(
                1 for r in self.weather if self.is_public("weather", r)
            ),
            "uiEntries": sum(1 for r in self.ui if self.is_public("ui", r)),
            "fishingBaits": sum(
                1 for r in self.fishing.get("baits", []) if self.is_public("bait", r)
            ),
            "fishingLoot": sum(
                1
                for r in self.fishing.get("loot", [])
                if self.is_public("fishing", r)
            ),
        }

    def media_file_name_for(self, kind: str, record: Dict[str, Any]) -> str:
        asset_path = self.media_asset_path_for(kind, record)
        return self.media_index.get(asset_path, "")

    def media_hash_for(self, kind: str, record: Dict[str, Any]) -> str:
        file_name = self.media_file_name_for(kind, record)
        return self._file_hashes.get(file_name, "") if file_name else ""

    def forum_tag_names(self, kind: str, record: Dict[str, Any]) -> List[str]:
        if kind == "item":
            category = self.friendly_label(record.get("categoryName")).casefold()
            if "firearm" in category or "attachment" in category:
                return ["Firearms"]
            if "magazine" in category:
                return ["Magazines"]
            if "ammo" in category or "spent shell" in category:
                return ["Ammo"]
            if "melee" in category:
                return ["Melee"]
            if "tool" in category:
                return ["Tools"]
            if "clothing" in category:
                return ["Clothing"]
            if any(token in category for token in ("helmet", "armor")):
                return ["Armor"]
            if "backpack" in category:
                return ["Backpacks"]
            if "food" in category:
                return ["Food"]
            if "heal" in category or "medical" in category:
                return ["Medical"]
            if "seed" in category:
                return ["Seeds"]
            if "bait" in category:
                return ["Fishing"]
            if "animal" in category:
                return ["Animals"]
            if "key" in category:
                return ["Keys"]
            if "quest" in category:
                return ["Quest"]
            if "currency" in category:
                return ["Currency"]
            if "explosive" in category or "throwable" in category:
                return ["Throwables"]
            return ["Resources"]

        if kind == "recipe":
            station = self.friendly_label(record.get("requiredStation")).casefold()
            result_name = self.display_name("recipe", record).casefold()
            if "ammo" in station or "reload" in station:
                return ["Ammo Reloading"]
            if "medical" in station or "med" in station:
                return ["Medical"]
            if "builder" in station or "construction" in station:
                return ["Builder"]
            if "workbench" in station or "work bench" in station:
                return ["Workbench"]
            if any(token in result_name for token in ("shirt", "jacket", "pants", "hat", "glove", "boot")):
                return ["Clothing"]
            if any(token in result_name for token in ("food", "meal", "stew", "cook")):
                return ["Food"]
            if any(token in result_name for token in ("rifle", "pistol", "shotgun", "smg", "carbine")):
                return ["Weapons"]
            if any(token in result_name for token in ("hammer", "shovel", "axe", "saw", "tool")):
                return ["Tools"]
            return ["General"]

        if kind == "building":
            context = self.building_context(record).casefold()
            category = self.friendly_label(record.get("categoryName")).casefold()
            name = self.display_name("building", record).casefold()

            if "boren player cabin upgrade" in context:
                return ["Cabin Upgrade"]
            if "wall" in category:
                return ["Walls"]
            if "roof" in category:
                return ["Roofs"]
            if "platform" in category:
                return ["Platforms"]
            if "door" in category:
                return ["Doors"]
            if "stair" in category:
                return ["Stairs"]
            if "workstation" in category:
                return ["Workstations"]
            if "storage" in category:
                return ["Storage"]
            if "shelter" in category:
                return ["Shelter"]
            if "fire" in category or "campfire" in name:
                return ["Fire"]
            if "landmine" in name or "defen" in category:
                return ["Defense"]
            return ["Construction"]

        if kind == "crop":
            return ["Crops"]
        if kind == "bait":
            return ["Bait", "Fishing"]
        if kind == "fishing":
            return ["Fishing"]
        if kind == "document":
            return ["Codex"]
        if kind == "level":
            return ["Maps"]
        return []

    def dataset(self, kind: str) -> List[Dict[str, Any]]:
        kind = kind.lower().strip()
        if kind in {"item", "items"}:
            return self.items
        if kind in {"recipe", "recipes", "craft", "crafting"}:
            return self.recipes
        if kind in {"building", "buildable", "buildables", "construction"}:
            return self.buildables
        if kind in {"crop", "crops", "farming"}:
            return self.crops
        if kind in {"document", "documents", "codex"}:
            return self.documents
        if kind in {"map", "maps", "area", "areas"}:
            return self.areas if self.areas else self.levels
        if kind in {"level", "levels"}:
            return self.levels
        if kind in {"weather", "storm", "storms", "environment"}:
            return self.weather
        if kind in {"ui", "hud", "interface", "icon", "icons"}:
            return self.ui
        if kind in {"bait", "baits"}:
            return list(self.fishing.get("baits", []))
        if kind in {"fish", "fishing", "loot", "fishingloot"}:
            return list(self.fishing.get("loot", [])) + list(
                self.fishing.get("baits", [])
            )
        if kind in {"all", "*", ""}:
            combined: List[Dict[str, Any]] = []
            for records in self._indexes.values():
                combined.extend(records)
            return combined
        return []

    def search(
        self,
        query: str,
        kind: str = "all",
        limit: int = 10,
        include_review: bool = False,
    ) -> List[SearchHit]:
        query = (query or "").strip()
        if not query:
            return []

        candidate_kinds = self._candidate_kinds(kind)
        hits: List[SearchHit] = []

        for candidate_kind in candidate_kinds:
            for record in self._indexes.get(candidate_kind, []):
                public = self.is_public(candidate_kind, record)
                if not include_review and not public:
                    continue

                name = self.display_name(candidate_kind, record)
                aliases = self.aliases(candidate_kind, record)
                name_score = self._score(query, name) if name else 0.0
                alias_score = max(
                    (self._score(query, value) for value in aliases if value),
                    default=0.0,
                )

                if candidate_kind == "ui":
                    # Category/meaning aliases make UI discoverable, but the
                    # actual icon/control name should win over generic bars and
                    # backgrounds that merely live in the same HUD category.
                    score = max(name_score, alias_score * 0.84)
                    if record.get("iconAuthoritative"):
                        score += 0.08
                    if record.get("playerHud"):
                        score += 0.02
                    low_name = name.lower()
                    if any(token in low_name for token in ("background", "fill bar", "frame", "mask")) or low_name.endswith(" bg"):
                        score -= 0.15
                    if low_name.endswith(" text") or low_name == "text":
                        score -= 0.04
                    score = min(1.0, max(0.0, score))
                else:
                    score = max(name_score, alias_score)

                if score < 0.32:
                    continue

                hits.append(
                    SearchHit(
                        kind=candidate_kind,
                        key=self.entity_key(candidate_kind, record),
                        name=name,
                        score=score,
                        record=record,
                        public=public,
                    )
                )

        hits.sort(key=lambda h: (-h.score, h.name.lower(), h.kind))
        return hits[: max(1, limit)]

    def best(
        self,
        query: str,
        kind: str,
        include_review: bool = False,
    ) -> Optional[SearchHit]:
        hits = self.search(query, kind=kind, limit=1, include_review=include_review)
        return hits[0] if hits else None

    def autocomplete(
        self, query: str, kind: str, limit: int = 25
    ) -> List[str]:
        query = (query or "").strip()
        if query:
            hits = self.search(query, kind=kind, limit=limit, include_review=False)
            return [h.name[:100] for h in hits[:limit]]

        # Discord allows at most 25 autocomplete choices. With no typed text,
        # show an alphabetical slice across the currently selected dataset.
        names = set()
        for candidate_kind in self._candidate_kinds(kind):
            for record in self._indexes.get(candidate_kind, []):
                if self.is_public(candidate_kind, record):
                    name = self.display_name(candidate_kind, record)
                    if name:
                        names.add(name)
        return [n[:100] for n in sorted(names, key=str.lower)[:limit]]

    def is_public(self, kind: str, record: Dict[str, Any]) -> bool:
        # Scene intelligence records do not carry their own Unity contentStatus;
        # inherit publication eligibility from the corresponding LevelDefinition.
        if kind == "area":
            level = self.level_for_area(record)
            return level is not None and self.is_public("level", level)

        if kind == "weather":
            area = self.area_for_weather(record)
            return (
                area is not None
                and self.is_public("area", area)
                and bool(record.get("hasWeatherSystem", True))
            )

        if kind == "ui":
            name = self.display_name("ui", record).strip()
            if not name:
                return False
            scenes = [str(x).strip() for x in (record.get("sourceScenes") or []) if str(x).strip()]
            if scenes and not any(self._is_public_scene_name(scene) for scene in scenes):
                return False
            # ui.json is already the curated public layer. Require either a real
            # icon, visible text, or a meaningful explanation before surfacing it.
            return bool(
                record.get("iconAuthoritative")
                or record.get("visibleLabels")
                or str(record.get("importance", "")).strip()
                or str(record.get("meaning", "")).strip()
            )

        source = record.get("source") or {}
        status = str(source.get("contentStatus", "")).strip()
        if status not in self.public_statuses:
            return False

        name = self.display_name(kind, record).strip()
        low = name.lower()

        # The Unity export intentionally keeps review candidates. The public bot
        # uses a conservative publication overlay until reachability data is added.
        if not name:
            return False
        if any(token in low for token in ("example ", " demo", "prototype", "showcase")):
            return False

        if kind == "recipe" and not bool(record.get("hasIngredients", False)):
            return False

        if kind == "level":
            if not str(record.get("sceneName", "")).strip():
                return False

        return True

    def entity_key(self, kind: str, record: Dict[str, Any]) -> str:
        source = record.get("source") or {}
        path = str(source.get("assetPath", ""))
        if kind == "item":
            return f"item:{record.get('id', 0)}:{path}"
        if kind == "recipe":
            return f"recipe:{record.get('recipeKey', '')}"
        if kind == "building":
            return f"building:{record.get('id', 0)}:{path}"
        if kind == "crop":
            return f"crop:{path}"
        if kind == "bait":
            return f"bait:{path}"
        if kind == "fishing":
            return f"fishing:{path}"
        if kind == "document":
            return f"document:{record.get('id', '')}:{path}"
        if kind == "level":
            return f"level:{path}"
        if kind == "area":
            return f"area:{record.get('areaKey', '')}:{record.get('sceneAssetPath', '')}"
        if kind == "weather":
            return f"weather:{record.get('areaKey', '')}:{record.get('sceneAssetPath', '')}"
        if kind == "ui":
            return f"ui:{record.get('uiKey', '')}"
        return f"{kind}:{path}:{self.display_name(kind, record)}"

    def display_name(self, kind: str, record: Dict[str, Any]) -> str:
        if kind == "recipe":
            raw = str(record.get("resultItemName", "") or record.get("recipeKey", ""))
        elif kind == "building":
            raw = str(record.get("name", ""))
            if raw.startswith("BuildingPiece_") and record.get("description"):
                raw = str(record.get("description"))
        elif kind == "crop":
            raw = str(record.get("cropName", "") or record.get("name", ""))
        elif kind == "bait":
            raw = str(record.get("baitName", "") or record.get("assetName", ""))
        elif kind == "fishing":
            raw = str(record.get("lootName", "") or record.get("assetName", ""))
        elif kind == "document":
            raw = str(record.get("title", "") or record.get("id", ""))
        elif kind == "level":
            raw = str(record.get("name", "") or record.get("assetName", ""))
        elif kind == "area":
            raw = str(record.get("name", "") or record.get("areaKey", "") or record.get("sceneName", ""))
        elif kind == "weather":
            raw = str(record.get("areaName", "") or record.get("areaKey", "") or record.get("sceneName", ""))
        elif kind == "ui":
            raw = self._ui_public_name(record)
        else:
            raw = str(record.get("name", ""))
        return self.friendly_label(raw)

    @staticmethod
    def friendly_label(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        # Remove implementation/vendor prefixes from player-facing copy while
        # retaining the untouched raw values in the knowledge records for audit.
        for _ in range(4):
            updated = re.sub(
                r"^(?:SV13|HQFPS|STP|FPSCore|FPS)[_\- ]+",
                "",
                text,
                flags=re.IGNORECASE,
            )
            if updated == text:
                break
            text = updated.strip()

        text = re.sub(r"^RarityLevel[_\- ]+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^ItemCategory[_\- ]+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^Category[_\- ]+", "", text, flags=re.IGNORECASE)
        text = text.replace("_", " ")
        text = re.sub(r"\s+", " ", text).strip()

        # SV13 uses .45 ACP in player-facing copy while several source assets
        # are named "45 ACP".
        text = re.sub(r"(?<!\d)45 ACP\b", ".45 ACP", text, flags=re.IGNORECASE)
        return text

    def rarity_label(self, value: Any) -> str:
        label = self.friendly_label(value)
        label = re.sub(r"^RarityLevel\s*", "", label, flags=re.IGNORECASE).strip()
        return label or "Unknown"

    def building_context(self, record: Dict[str, Any]) -> str:
        components = {str(x) for x in (record.get("sv13ComponentTypes") or [])}
        if "SV13PermanentUpgradeController" in components:
            return "Boren Player Cabin Upgrade"
        if "SV13PermanentConstructable" in components:
            return "Player Cabin Construction"
        return self.friendly_label(record.get("categoryName")) or "Construction"

    def media_asset_path_for(self, kind: str, record: Dict[str, Any]) -> str:
        if kind == "item":
            return str(record.get("iconAssetPath", ""))
        if kind == "recipe":
            item = self._item_by_id.get(int(record.get("resultItemId", 0)))
            return str(item.get("iconAssetPath", "")) if item else ""
        if kind == "building":
            return str(record.get("iconAssetPath", ""))
        if kind == "crop":
            item = self._item_by_id.get(int(record.get("produceItemId", 0)))
            return str(item.get("iconAssetPath", "")) if item else ""
        if kind == "bait":
            for linked in record.get("linkedItems") or []:
                item = self._item_by_id.get(int(linked.get("id", 0)))
                if item and item.get("iconAssetPath"):
                    return str(item["iconAssetPath"])
            return ""
        if kind == "fishing":
            item = self._item_by_clean_name.get(
                self.friendly_label(
                    record.get("lootName") or record.get("assetName")
                ).lower()
            )
            return str(item.get("iconAssetPath", "")) if item else ""
        if kind in {"level", "area"}:
            return str(
                record.get("thumbnailAssetPath")
                or record.get("loadingImageAssetPath")
                or ""
            )
        if kind == "weather":
            area = self.area_for_weather(record)
            return self.media_asset_path_for("area", area) if area else ""
        if kind == "ui":
            return str(record.get("iconAssetPath", ""))
        return ""

    def media_path_for(self, kind: str, record: Dict[str, Any]) -> Optional[Path]:
        asset_path = self.media_asset_path_for(kind, record)
        file_name = self.media_index.get(asset_path, "")
        if not file_name:
            return None
        candidate = self.knowledge_dir / Path(file_name).name
        return candidate if candidate.is_file() else None

    def aliases(self, kind: str, record: Dict[str, Any]) -> List[str]:
        aliases: List[str] = []
        # Always keep the raw exported name searchable even though the public
        # display name is scrubbed of implementation prefixes.
        if kind == "recipe":
            aliases.append(str(record.get("resultItemName", "")))
        elif kind == "building":
            aliases.append(str(record.get("name", "")))
        elif kind == "crop":
            aliases.append(str(record.get("cropName", "") or record.get("name", "")))
        elif kind == "bait":
            aliases.append(str(record.get("baitName", "") or record.get("assetName", "")))
        elif kind == "fishing":
            aliases.append(str(record.get("lootName", "") or record.get("assetName", "")))
        elif kind == "document":
            aliases.append(str(record.get("title", "") or record.get("id", "")))
        elif kind == "level":
            aliases.append(str(record.get("name", "") or record.get("assetName", "")))
        elif kind == "area":
            aliases.append(str(record.get("name", "") or record.get("areaKey", "")))
        elif kind == "weather":
            aliases.append(str(record.get("areaName", "") or record.get("areaKey", "")))
        elif kind == "ui":
            aliases.append(str(record.get("name", "")))
        else:
            aliases.append(str(record.get("name", "")))

        if kind == "item":
            aliases.extend(
                [
                    str(record.get("description", "")),
                    str(record.get("longDescription", "")),
                    str(record.get("categoryName", "")),
                ]
            )
        elif kind == "recipe":
            aliases.extend(
                [
                    str(record.get("requiredStation", "")),
                    " ".join(
                        str(r.get("itemName", ""))
                        for r in record.get("requirements", [])
                    ),
                ]
            )
        elif kind == "building":
            aliases.extend(
                [
                    str(record.get("description", "")),
                    str(record.get("categoryName", "")),
                    " ".join(
                        str(r.get("buildMaterialName", ""))
                        for r in record.get("requirements", [])
                    ),
                ]
            )
        elif kind == "crop":
            aliases.extend(
                [
                    str(record.get("seedItemName", "")),
                    str(record.get("produceItemName", "")),
                ]
            )
        elif kind in {"bait", "fishing"}:
            aliases.extend(
                [
                    str(record.get("description", "")),
                    str(record.get("baitTier", "")),
                    str(record.get("lootTier", "")),
                    str(record.get("lootType", "")),
                ]
            )
        elif kind == "document":
            aliases.extend(
                [
                    str(record.get("id", "")),
                    str(record.get("codexEntryId", "")),
                    str(record.get("documentType", "")),
                ]
            )
        elif kind == "level":
            aliases.extend(
                [
                    str(record.get("sceneName", "")),
                    str(record.get("description", "")),
                    str(record.get("assetName", "")),
                ]
            )
        elif kind == "area":
            aliases.extend(
                [
                    str(record.get("areaKey", "")),
                    str(record.get("sceneName", "")),
                    str(record.get("description", "")),
                    " ".join(str(x) for x in (record.get("activities") or [])),
                    " ".join(str(x) for x in (record.get("borenUpgrades") or [])),
                    " ".join(
                        str(x.get("name", "")) + " " + str(x.get("summary", "")) + " " +
                        " ".join(str(v) for v in (x.get("capabilities") or []))
                        for x in (record.get("upgrades") or []) if isinstance(x, dict)
                    ),
                    " ".join(
                        str(x.get("name", "")) + " " + str(x.get("summary", ""))
                        for x in (record.get("specialFeatures") or []) if isinstance(x, dict)
                    ),
                ]
            )
        elif kind == "weather":
            aliases.extend(
                [
                    str(record.get("areaKey", "")),
                    str(record.get("sceneName", "")),
                    " ".join(str(x) for x in (record.get("scheduledWeatherTypes") or [])),
                    " ".join(str(x) for x in (record.get("supportedHazardTypes") or [])),
                    " ".join(
                        str(x.get("label", "")) for x in (record.get("facts") or [])
                        if isinstance(x, dict)
                    ),
                ]
            )
        elif kind == "ui":
            aliases.extend(
                [
                    str(record.get("category", "")),
                    str(record.get("meaning", "")),
                    str(record.get("importance", "")),
                    str(record.get("iconName", "")),
                    " ".join(str(x) for x in (record.get("visibleLabels") or [])),
                    " ".join(str(x) for x in (record.get("sourceScenes") or [])),
                    " ".join(str(x) for x in (record.get("hierarchyPaths") or [])),
                ]
            )
        return [a for a in aliases if a]

    def level_for_area(self, area: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(area, dict):
            return None
        scene_path = str(area.get("sceneAssetPath", "")).strip().lower()
        if scene_path and scene_path in self._level_by_scene_path:
            return self._level_by_scene_path[scene_path]
        scene_name = str(area.get("sceneName", "") or area.get("areaKey", "")).strip().lower()
        if scene_name and scene_name in self._level_by_scene_name:
            return self._level_by_scene_name[scene_name]
        return None

    def area_for_level(self, level: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(level, dict):
            return None
        scene_path = str(level.get("sceneAssetPath", "")).strip().lower()
        if scene_path and scene_path in self._area_by_scene_path:
            return self._area_by_scene_path[scene_path]
        scene_name = str(level.get("sceneName", "")).strip().lower()
        if scene_name and scene_name in self._area_by_scene_name:
            return self._area_by_scene_name[scene_name]
        return None

    def area_for_weather(self, weather: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(weather, dict):
            return None
        key = str(weather.get("areaKey", "")).strip().lower()
        if key and key in self._area_by_key:
            return self._area_by_key[key]
        scene_path = str(weather.get("sceneAssetPath", "")).strip().lower()
        if scene_path and scene_path in self._area_by_scene_path:
            return self._area_by_scene_path[scene_path]
        scene_name = str(weather.get("sceneName", "")).strip().lower()
        if scene_name and scene_name in self._area_by_scene_name:
            return self._area_by_scene_name[scene_name]
        return None

    def weather_for_area(self, area: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(area, dict):
            return None
        key = str(area.get("areaKey", "")).strip().lower()
        if key and key in self._weather_by_area_key:
            return self._weather_by_area_key[key]
        scene_name = str(area.get("sceneName", "")).strip().lower()
        if scene_name and scene_name in self._weather_by_scene_name:
            return self._weather_by_scene_name[scene_name]
        return None

    def ui_by_key(self, ui_key: str) -> Optional[Dict[str, Any]]:
        return self._ui_by_key.get(str(ui_key or "").strip().lower())

    def publication_context(self, kind: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """Return related data that materially changes a published embed."""
        if kind == "level":
            area = self.area_for_level(record)
            weather = self.weather_for_area(area) if area else None
            return {"area": area, "weather": weather}
        return {}

    def _is_public_scene_name(self, scene_name: str) -> bool:
        level = self._level_by_scene_name.get(str(scene_name or "").strip().lower())
        return level is not None and self.is_public("level", level)

    def _ui_public_name(self, record: Dict[str, Any]) -> str:
        raw = str(record.get("name", "") or "").strip()
        compact = re.sub(r"[^A-Fa-f0-9]", "", raw)
        looks_generated = len(compact) >= 20 and len(compact) >= int(len(raw.replace(" ", "")) * 0.65)
        generic = self.friendly_label(raw).lower() in {"", "icon", "image", "sprite", "background", "bg"}
        if not looks_generated and not generic:
            return raw

        for path in record.get("hierarchyPaths") or []:
            parts = [p.strip() for p in str(path).split("/") if p.strip()]
            if not parts:
                continue
            candidate = parts[-1]
            if self.friendly_label(candidate).lower() in {"icon", "image", "sprite", "background", "bg"} and len(parts) > 1:
                candidate = parts[-2]
            if candidate:
                return candidate

        category = str(record.get("category", "")).strip()
        return category or raw

    def public_entities(self, scope: str = "all") -> List[tuple[str, Dict[str, Any]]]:
        scope = (scope or "all").lower()
        kinds: Sequence[str]
        if scope == "items":
            kinds = ("item",)
        elif scope in {"recipes", "crafting"}:
            kinds = ("recipe",)
        elif scope in {"buildings", "construction"}:
            kinds = ("building",)
        elif scope == "field":
            kinds = ("crop", "bait", "fishing", "document", "level")
        else:
            kinds = ("item", "recipe", "building", "crop", "bait", "fishing", "document", "level")

        results: List[tuple[str, Dict[str, Any]]] = []
        for kind in kinds:
            for record in self._indexes.get(kind, []):
                if self.is_public(kind, record):
                    results.append((kind, record))
        return results

    def recipe_for_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        for recipe in self.recipes:
            if int(recipe.get("resultItemId", 0)) == int(item_id):
                return recipe
        return None

    def _read_optional_array(self, file_name: str) -> List[Dict[str, Any]]:
        path = self.knowledge_dir / file_name
        if not path.is_file():
            return []
        value = self._read_json(file_name)
        if not isinstance(value, list):
            raise RuntimeError(f"{file_name} must contain a JSON array.")
        return value

    def _read_json(self, file_name: str) -> Any:
        path = self.knowledge_dir / file_name
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _rebuild_indexes(self) -> None:
        self._item_by_id = {
            int(item.get("id", 0)): item
            for item in self.items
            if int(item.get("id", 0)) != 0
        }
        self._item_by_asset_path = {
            str((item.get("source") or {}).get("assetPath", "")): item
            for item in self.items
            if str((item.get("source") or {}).get("assetPath", ""))
        }
        self._item_by_clean_name = {
            self.friendly_label(item.get("name")).lower(): item
            for item in self.items
            if self.friendly_label(item.get("name"))
        }

        self._level_by_scene_name = {
            str(level.get("sceneName", "")).strip().lower(): level
            for level in self.levels
            if str(level.get("sceneName", "")).strip()
        }
        self._level_by_scene_path = {
            str(level.get("sceneAssetPath", "")).strip().lower(): level
            for level in self.levels
            if str(level.get("sceneAssetPath", "")).strip()
        }
        self._area_by_key = {
            str(area.get("areaKey", "")).strip().lower(): area
            for area in self.areas
            if str(area.get("areaKey", "")).strip()
        }
        self._area_by_scene_name = {
            str(area.get("sceneName", "")).strip().lower(): area
            for area in self.areas
            if str(area.get("sceneName", "")).strip()
        }
        self._area_by_scene_path = {
            str(area.get("sceneAssetPath", "")).strip().lower(): area
            for area in self.areas
            if str(area.get("sceneAssetPath", "")).strip()
        }
        self._weather_by_area_key = {
            str(profile.get("areaKey", "")).strip().lower(): profile
            for profile in self.weather
            if str(profile.get("areaKey", "")).strip()
        }
        self._weather_by_scene_name = {
            str(profile.get("sceneName", "")).strip().lower(): profile
            for profile in self.weather
            if str(profile.get("sceneName", "")).strip()
        }
        self._ui_by_key = {
            str(record.get("uiKey", "")).strip().lower(): record
            for record in self.ui
            if str(record.get("uiKey", "")).strip()
        }

        self._indexes = {
            "item": list(self.items),
            "recipe": list(self.recipes),
            "building": list(self.buildables),
            "crop": list(self.crops),
            "bait": list(self.fishing.get("baits", [])),
            "fishing": list(self.fishing.get("loot", [])),
            "document": list(self.documents),
            "level": list(self.levels),
            "area": list(self.areas),
            "weather": list(self.weather),
            "ui": list(self.ui),
        }

    def _candidate_kinds(self, kind: str) -> Sequence[str]:
        normalized = self._normalize_kind(kind)
        if normalized == "all":
            # Area replaces the duplicate LevelDefinition entry in global search;
            # level remains available internally for publication/back-compat.
            base = ("item", "recipe", "building", "crop", "bait", "fishing", "document")
            world = ("area", "weather", "ui") if self.areas or self.weather or self.ui else ("level",)
            return base + world
        if normalized == "area" and not self.areas:
            return ("level",)
        return (normalized,)

    @staticmethod
    def _normalize_kind(kind: str) -> str:
        kind = (kind or "all").lower().strip()
        mapping = {
            "items": "item",
            "recipes": "recipe",
            "craft": "recipe",
            "crafting": "recipe",
            "build": "building",
            "buildable": "building",
            "buildables": "building",
            "construction": "building",
            "crops": "crop",
            "farm": "crop",
            "farming": "crop",
            "baits": "bait",
            "fish": "fishing",
            "documents": "document",
            "codex": "document",
            "maps": "area",
            "map": "area",
            "areas": "area",
            "levels": "level",
            "storms": "weather",
            "storm": "weather",
            "environment": "weather",
            "hud": "ui",
            "interface": "ui",
            "icons": "ui",
            "icon": "ui",
        }
        allowed = {
            "all", "item", "recipe", "building", "crop", "bait", "fishing",
            "document", "level", "area", "weather", "ui"
        }
        return mapping.get(kind, kind if kind in allowed else "all")

    @staticmethod
    def _score(query: str, candidate: str) -> float:
        q = query.strip().lower()
        c = candidate.strip().lower()
        if not q or not c:
            return 0.0
        if q == c:
            return 1.0
        if c.startswith(q):
            return 0.95
        if q in c:
            return 0.88
        if all(token in c for token in q.split()):
            return 0.82
        return difflib.SequenceMatcher(None, q, c).ratio()
