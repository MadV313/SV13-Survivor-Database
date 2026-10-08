from __future__ import annotations

import ast
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "bot.py",
    "requirements.txt",
    "runtime.txt",
    ".env.example",
    ".gitignore",
    "sv13bot/__init__.py",
    "sv13bot/config.py",
    "sv13bot/bot_app.py",
    "sv13bot/knowledge.py",
    "sv13bot/knowledge_source.py",
    "sv13bot/state.py",
    "sv13bot/discord_setup.py",
    "sv13bot/publisher.py",
    "sv13bot/embeds.py",
    "sv13bot/cogs/public.py",
    "sv13bot/cogs/admin.py",
]


SECRET_PATTERNS = [
    re.compile(
        r"(?i)(?:discord[_-]?token|bot[_-]?token)\s*[=:]\s*[\"']?"
        r"([A-Za-z0-9._-]{30,})"
    ),
    re.compile(
        r"(?i)(?:api[_-]?key|password|private[_-]?key)\s*[=:]\s*[\"']?"
        r"([^\s\"']{20,})"
    ),
]


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            errors.append(f"Missing required file: {rel}")

    pyc = list(ROOT.rglob("*.pyc"))
    malformed_cache_dirs = [
        p for p in ROOT.rglob("*")
        if p.is_dir() and p.name == "__pycache_"
    ]
    normal_cache_dirs = [
        p for p in ROOT.rglob("*")
        if p.is_dir() and p.name == "__pycache__"
    ]
    if malformed_cache_dirs:
        errors.append(
            "Malformed/committed __pycache_ directories present: "
            f"{len(malformed_cache_dirs)}"
        )
    if pyc or normal_cache_dirs:
        warnings.append(
            "Normal Python bytecode/cache files exist locally. They are ignored by "
            ".gitignore; remove them before creating a source ZIP if needed."
        )

    for py in ROOT.rglob("*.py"):
        try:
            ast.parse(py.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Python parse failed: {py.relative_to(ROOT)}: {exc}")

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".pyc", ".zip", ".png", ".jpg"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(1)
                lower = value.lower()
                if (
                    "your_" in lower
                    or value.endswith("=")
                    or "example" in lower
                ):
                    continue
                errors.append(
                    f"Possible committed secret in {path.relative_to(ROOT)}"
                )

    env = ROOT / ".env"
    if env.exists():
        warnings.append(
            ".env exists locally. Confirm it remains ignored and is not committed."
        )

    print("SV13 repository preflight")
    print(f"Python files checked: {len(list(ROOT.rglob('*.py')))}")

    for warning in warnings:
        print("WARN:", warning)
    for error in errors:
        print("ERROR:", error)

    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        return 1

    print("PASS: repository structure, syntax, cache hygiene, and basic secret scan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
