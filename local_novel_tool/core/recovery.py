from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class RecoveryEntry:
    project_root: str
    source: str
    item_id: str
    content: object
    updated_at: str


class RecoveryStore:
    """Atomic, per-project storage for unsaved editor contents."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _project_key(project_root: Path) -> str:
        value = str(project_root.resolve()).casefold().encode("utf-8")
        return hashlib.sha256(value).hexdigest()

    def _path(self, project_root: Path) -> Path:
        return self.root / f"{self._project_key(project_root)}.json"

    def load(self, project_root: Path) -> list[RecoveryEntry]:
        path = self._path(project_root)
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("project_root") != str(project_root.resolve()):
                return []
            return [RecoveryEntry(**item) for item in data.get("entries", [])]
        except (OSError, ValueError, TypeError):
            return []

    def save(self, project_root: Path, source: str, item_id: str, content: object) -> None:
        entries = {(item.source, item.item_id): item for item in self.load(project_root)}
        entries[(source, item_id)] = RecoveryEntry(
            str(project_root.resolve()), source, item_id, content,
            datetime.now(timezone.utc).isoformat(),
        )
        self._write(project_root, list(entries.values()))

    def remove(self, project_root: Path, source: str, item_id: str) -> None:
        entries = [item for item in self.load(project_root) if (item.source, item.item_id) != (source, item_id)]
        self._write(project_root, entries)

    def _write(self, project_root: Path, entries: list[RecoveryEntry]) -> None:
        path = self._path(project_root)
        if not entries:
            path.unlink(missing_ok=True)
            return
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"project_root": str(project_root.resolve()), "entries": [asdict(item) for item in entries]}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
