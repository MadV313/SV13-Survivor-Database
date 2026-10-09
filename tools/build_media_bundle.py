from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
from typing import Any, Dict, Iterable, List, Set


SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MEDIA_PREFIX = "sv13_media_"
INDEX_NAME = "media_index.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(asset_path: str) -> str:
    source = Path(asset_path)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem).strip("._") or "sprite"
    short = hashlib.sha1(asset_path.encode("utf-8")).hexdigest()[:12]
    return f"{MEDIA_PREFIX}{short}_{stem}{source.suffix.lower()}"


def gather_asset_paths(knowledge: Path) -> Set[str]:
    paths: Set[str] = set()

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if text:
            paths.add(text)

    for name in ("items.json", "item_categories.json", "build_materials.json", "buildables.json"):
        file_path = knowledge / name
        if not file_path.is_file():
            continue
        data = load_json(file_path)
        if not isinstance(data, list):
            continue
        for record in data:
            if isinstance(record, dict):
                add(record.get("iconAssetPath"))

    levels_path = knowledge / "levels.json"
    if levels_path.is_file():
        data = load_json(levels_path)
        if isinstance(data, list):
            for record in data:
                if isinstance(record, dict):
                    add(record.get("thumbnailAssetPath"))
                    add(record.get("loadingImageAssetPath"))

    return paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy only sprite/image assets referenced by the SV13 knowledge export "
            "into the flat knowledge package so Discord/Railway can display them."
        )
    )
    parser.add_argument(
        "--unity-project",
        required=True,
        help="Unity project root containing the Assets folder.",
    )
    parser.add_argument(
        "--knowledge",
        help="Knowledge folder. Defaults to <unity-project>/SV13_Knowledge/Latest.",
    )
    args = parser.parse_args()

    unity_project = Path(args.unity_project).expanduser().resolve()
    knowledge = (
        Path(args.knowledge).expanduser().resolve()
        if args.knowledge
        else (unity_project / "SV13_Knowledge" / "Latest").resolve()
    )

    if not (unity_project / "Assets").is_dir():
        raise SystemExit(f"Unity Assets folder not found: {unity_project / 'Assets'}")
    if not (knowledge / "manifest.json").is_file():
        raise SystemExit(f"Knowledge manifest not found: {knowledge / 'manifest.json'}")

    # Remove only media files created by this tool.
    for existing in knowledge.glob(f"{MEDIA_PREFIX}*"):
        if existing.is_file():
            existing.unlink()
    index_path = knowledge / INDEX_NAME
    if index_path.exists():
        index_path.unlink()

    requested = sorted(gather_asset_paths(knowledge), key=str.lower)
    entries: List[Dict[str, Any]] = []
    missing: List[str] = []
    unsupported: List[str] = []

    for asset_path in requested:
        source = unity_project / Path(asset_path)
        suffix = source.suffix.lower()
        if suffix not in SUPPORTED:
            unsupported.append(asset_path)
            continue
        if not source.is_file():
            missing.append(asset_path)
            continue

        file_name = safe_name(asset_path)
        target = knowledge / file_name
        shutil.copy2(source, target)

        entries.append(
            {
                "assetPath": asset_path,
                "fileName": file_name,
                "sha256": sha256(target),
                "bytes": target.stat().st_size,
            }
        )

    media_index = {
        "schemaVersion": "1",
        "generatedUtc": datetime.now(timezone.utc).isoformat(),
        "assets": entries,
    }
    index_path.write_text(
        json.dumps(media_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest_path = knowledge / "manifest.json"
    manifest = load_json(manifest_path)
    files = manifest.get("files") or []
    if not isinstance(files, list):
        raise SystemExit("manifest.json files must be an array.")

    retained = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("fileName", ""))
        if name == INDEX_NAME or name.startswith(MEDIA_PREFIX):
            continue
        retained.append(entry)

    for entry in entries:
        retained.append(
            {
                "fileName": entry["fileName"],
                "sha256": entry["sha256"],
                "bytes": entry["bytes"],
                "recordCount": 0,
            }
        )

    retained.append(
        {
            "fileName": INDEX_NAME,
            "sha256": sha256(index_path),
            "bytes": index_path.stat().st_size,
            "recordCount": len(entries),
        }
    )
    manifest["files"] = retained

    notes = manifest.get("notes")
    if not isinstance(notes, list):
        notes = []
        manifest["notes"] = notes
    note = (
        "Player-facing media bundle attached by tools/build_media_bundle.py; "
        "raw Unity asset paths remain unchanged for auditing."
    )
    if note not in notes:
        notes.append(note)

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("SV13 media bundle complete")
    print(f"Knowledge: {knowledge}")
    print(f"Referenced images: {len(requested)}")
    print(f"Copied: {len(entries)}")
    print(f"Missing: {len(missing)}")
    print(f"Unsupported format: {len(unsupported)}")
    if missing:
        print("\nMissing examples:")
        for value in missing[:15]:
            print(" -", value)
    if unsupported:
        print("\nUnsupported examples:")
        for value in unsupported[:15]:
            print(" -", value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
