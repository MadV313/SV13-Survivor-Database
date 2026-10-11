from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import BotConfig


log = logging.getLogger("sv13bot.knowledge_source")


class KnowledgeSource:
    """Resolves either a local Unity export or a remotely hosted knowledge package."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.remote = bool(config.knowledge_base_url)
        self.local_dir = Path(config.knowledge_dir)
        self.cache_dir = Path(config.knowledge_cache_dir)

    @property
    def active_dir(self) -> Path:
        return self.cache_dir if self.remote else self.local_dir

    @property
    def description(self) -> str:
        if self.remote:
            return f"remote:{self.config.knowledge_base_url}"
        return f"local:{self.local_dir}"

    def prepare_initial(self) -> Path:
        if self.remote:
            try:
                self.refresh(force=True)
            except Exception:
                if not (self.cache_dir / "manifest.json").is_file():
                    raise
                log.exception(
                    "Remote knowledge refresh failed; starting from the existing verified cache at %s",
                    self.cache_dir,
                )
        return self.active_dir

    def refresh(self, force: bool = False) -> Tuple[bool, List[str]]:
        if not self.remote:
            return False, []

        remote_manifest = self._download_json("manifest.json")
        remote_fingerprint = self._fingerprint(remote_manifest)

        cached_manifest_path = self.cache_dir / "manifest.json"
        cached_manifest: Dict[str, Any] = {}
        if cached_manifest_path.is_file():
            try:
                cached_manifest = json.loads(
                    cached_manifest_path.read_text(encoding="utf-8")
                )
            except Exception:
                cached_manifest = {}

        cached_fingerprint = self._fingerprint(cached_manifest) if cached_manifest else ""
        source_changed = remote_fingerprint != cached_fingerprint

        remote_hashes = self._hash_map(remote_manifest)
        cached_hashes = self._hash_map(cached_manifest)
        changed_files = sorted(
            name
            for name in set(remote_hashes) | set(cached_hashes)
            if remote_hashes.get(name) != cached_hashes.get(name)
        )

        if not source_changed and not force:
            return False, []

        # A forced refresh re-downloads and verifies the package, but it is not
        # reported as a content change unless the remote manifest fingerprint
        # actually differs from the cached package.
        self._download_package_atomically(remote_manifest)
        return source_changed, changed_files if source_changed else []

    def _download_package_atomically(self, manifest: Dict[str, Any]) -> None:
        parent = self.cache_dir.parent
        parent.mkdir(parents=True, exist_ok=True)

        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{self.cache_dir.name}.staging-",
                dir=str(parent),
            )
        )
        backup = parent / f".{self.cache_dir.name}.backup"

        try:
            files = manifest.get("files") or []
            if not isinstance(files, list) or not files:
                raise RuntimeError("Remote manifest has no files list.")

            for entry in files:
                if not isinstance(entry, dict):
                    raise RuntimeError("Remote manifest contains a malformed file entry.")
                name = str(entry.get("fileName", "")).strip()
                candidate = Path(name)
                if (
                    not name
                    or name in {".", ".."}
                    or candidate.is_absolute()
                    or candidate.name != name
                    or "/" in name
                    or "\\" in name
                ):
                    raise RuntimeError(
                        f"Unsafe or empty fileName in manifest: {name!r}"
                    )

                payload = self._download_bytes(name)
                expected_hash = str(entry.get("sha256", "")).strip().lower()
                if expected_hash:
                    actual_hash = hashlib.sha256(payload).hexdigest()
                    if actual_hash != expected_hash:
                        raise RuntimeError(
                            f"Remote knowledge hash mismatch for {name}: "
                            f"expected {expected_hash}, got {actual_hash}"
                        )

                expected_bytes = entry.get("bytes")
                if isinstance(expected_bytes, int) and expected_bytes >= 0:
                    if len(payload) != expected_bytes:
                        raise RuntimeError(
                            f"Remote knowledge byte-count mismatch for {name}: "
                            f"expected {expected_bytes}, got {len(payload)}"
                        )

                (staging / name).write_bytes(payload)

            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)

            if self.cache_dir.exists():
                os.replace(self.cache_dir, backup)

            os.replace(staging, self.cache_dir)

            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            if not self.cache_dir.exists() and backup.exists():
                os.replace(backup, self.cache_dir)
            raise

    def _download_json(self, name: str) -> Dict[str, Any]:
        payload = self._download_bytes(name)
        data = json.loads(payload.decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise RuntimeError(f"{name} must contain a JSON object.")
        return data

    def _download_bytes(self, name: str) -> bytes:
        url = f"{self.config.knowledge_base_url}/{name}"
        req = Request(
            url,
            headers={
                "User-Agent": "SV13-Survivor-Database/0.2.1",
                "Accept": "application/json,text/plain,*/*",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urlopen(
                req,
                timeout=self.config.knowledge_http_timeout_seconds,
            ) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"Could not download SV13 knowledge file {url}: {exc}") from exc

    @staticmethod
    def _hash_map(manifest: Dict[str, Any]) -> Dict[str, str]:
        return {
            str(entry.get("fileName", "")): str(entry.get("sha256", ""))
            for entry in (manifest.get("files") or [])
            if isinstance(entry, dict) and entry.get("fileName")
        }

    @classmethod
    def _fingerprint(cls, manifest: Dict[str, Any]) -> str:
        raw = json.dumps(
            {
                "packageVersion": str(manifest.get("packageVersion", "")),
                "files": sorted(cls._hash_map(manifest).items()),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
