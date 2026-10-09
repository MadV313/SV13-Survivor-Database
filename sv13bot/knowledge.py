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
            "validationWarnings": int(counts.get("validationWarnings", 0)),
            "validationErrors": int(counts.get("validationErrors", 0)),
        }

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
        if kind in {"map", "maps", "level", "levels"}:
            return self.levels
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
                score = max(self._score(query, value) for value in [name, *aliases] if value)

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
        if kind == "level":
            return str(
                record.get("thumbnailAssetPath")
                or record.get("loadingImageAssetPath")
                or ""
            )
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
        return [a for a in aliases if a]

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
        self._indexes = {
            "item": list(self.items),
            "recipe": list(self.recipes),
            "building": list(self.buildables),
            "crop": list(self.crops),
            "bait": list(self.fishing.get("baits", [])),
            "fishing": list(self.fishing.get("loot", [])),
            "document": list(self.documents),
            "level": list(self.levels),
        }

    def _candidate_kinds(self, kind: str) -> Sequence[str]:
        normalized = self._normalize_kind(kind)
        if normalized == "all":
            return ("item", "recipe", "building", "crop", "bait", "fishing", "document", "level")
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
            "maps": "level",
            "map": "level",
            "levels": "level",
        }
        return mapping.get(kind, kind if kind in {
            "all", "item", "recipe", "building", "crop", "bait", "fishing", "document", "level"
        } else "all")

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
