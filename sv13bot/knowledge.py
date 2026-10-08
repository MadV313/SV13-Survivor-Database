from __future__ import annotations

import difflib
import hashlib
import json
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

        self.manifest = self._read_json("manifest.json")
        self.items = self._read_json(DATA_FILES["items"])
        self.recipes = self._read_json(DATA_FILES["recipes"])
        self.categories = self._read_json(DATA_FILES["categories"])
        self.buildables = self._read_json(DATA_FILES["buildables"])
        self.build_materials = self._read_json(DATA_FILES["build_materials"])
        self.crops = self._read_json(DATA_FILES["crops"])
        self.fishing = self._read_json(DATA_FILES["fishing"])
        self.documents = self._read_json(DATA_FILES["documents"])
        self.levels = self._read_json(DATA_FILES["levels"])
        self.loot_tables = self._read_json(DATA_FILES["loot_tables"])
        self.validation = self._read_json(DATA_FILES["validation"])

        self._file_hashes = {
            str(entry.get("fileName", "")): str(entry.get("sha256", ""))
            for entry in self.manifest.get("files", [])
            if entry.get("fileName")
        }

        raw = json.dumps(
            {
                "package": self.package_version,
                "files": sorted(self._file_hashes.items()),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self._manifest_fingerprint = hashlib.sha256(raw).hexdigest()
        self._rebuild_indexes()

    def reload_if_changed(self, force: bool = False) -> tuple[bool, List[str]]:
        self.validate_path()
        manifest = self._read_json("manifest.json")
        next_hashes = {
            str(entry.get("fileName", "")): str(entry.get("sha256", ""))
            for entry in manifest.get("files", [])
            if entry.get("fileName")
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
        hits = self.search(query or " ", kind=kind, limit=limit, include_review=False)
        if hits:
            return [h.name[:100] for h in hits[:limit]]

        # Empty autocomplete query: show a small alphabetical sample.
        records = [
            r for r in self._indexes.get(self._normalize_kind(kind), [])
            if self.is_public(self._normalize_kind(kind), r)
        ]
        names = sorted(
            {self.display_name(self._normalize_kind(kind), r) for r in records},
            key=str.lower,
        )
        return [n[:100] for n in names[:limit] if n]

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
            return str(record.get("resultItemName", "") or record.get("recipeKey", ""))
        if kind == "building":
            return str(record.get("name", ""))
        if kind == "crop":
            return str(record.get("cropName", "") or record.get("name", ""))
        if kind == "bait":
            return str(record.get("baitName", "") or record.get("assetName", ""))
        if kind == "fishing":
            return str(record.get("lootName", "") or record.get("assetName", ""))
        if kind == "document":
            return str(record.get("title", "") or record.get("id", ""))
        if kind == "level":
            return str(record.get("name", "") or record.get("assetName", ""))
        return str(record.get("name", ""))

    def aliases(self, kind: str, record: Dict[str, Any]) -> List[str]:
        aliases: List[str] = []
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
