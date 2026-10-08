from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sv13bot.knowledge import KnowledgeStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an SV13 knowledge package against the bot loader.")
    parser.add_argument("--knowledge", required=True, help="Path to SV13_Knowledge/Latest or a timestamp export folder.")
    args = parser.parse_args()

    store = KnowledgeStore(
        Path(args.knowledge),
        {"SV13AuthoredCandidate", "ProjectIntegratedCandidate"},
    )
    store.load()

    print("SV13 Survivor Database smoke test")
    print("Package:", store.package_version)
    print("Manifest/file integrity: PASS")
    print("Counts:", store.counts())

    checks = [
        ("item search", store.best("Cabbage", "item", include_review=True)),
        ("recipe search", store.best(".45 ACP", "recipe", include_review=True)),
        ("building search", store.best("GreenHouse", "building", include_review=True)),
        ("crop search", store.best("Cabbage", "crop", include_review=True)),
        ("document search", store.best("Didn't Mean to Stay", "document", include_review=True)),
    ]

    failed = False
    for label, hit in checks:
        print(f"{label}: {'PASS' if hit else 'FAIL'}", f"-> {hit.name if hit else ''}")
        failed = failed or hit is None

    public_hits = store.search("green", "all", limit=5)
    print("Public search sample:", [(h.kind, h.name) for h in public_hits])

    if failed:
        print("One or more expected lookups failed.")
        return 1

    print("Knowledge loader/search smoke test PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
