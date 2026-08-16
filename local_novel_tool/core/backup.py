from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path


class BackupError(RuntimeError):
    pass


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot(root: Path) -> tuple[tuple[str, ...], dict[str, str]]:
    directories: list[str] = []
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            directories.append(relative)
        elif path.is_file():
            files[relative] = _digest(path)
    return tuple(directories), files


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def create_project_backup(
    project_root: Path,
    backups_root: Path,
    *,
    created_at: datetime | None = None,
) -> Path:
    """Copy a complete project into a verified, non-overwriting generation."""
    project_root = project_root.resolve()
    backups_root = backups_root.resolve()
    if not (project_root / "project.json").is_file():
        raise BackupError("作品データが見つかりません。")
    if backups_root == project_root or _is_within(backups_root, project_root):
        raise BackupError("バックアップ先は作品フォルダの外にしてください。")

    path_key = hashlib.sha256(str(project_root).casefold().encode("utf-8")).hexdigest()[:10]
    series = backups_root / f"{project_root.name} - {path_key}"
    timestamp = (created_at or datetime.now()).strftime("%Y%m%d-%H%M%S")
    generation = series / timestamp
    number = 2
    while generation.exists():
        generation = series / f"{timestamp}-{number}"
        number += 1

    staged = series / f".{generation.name}.tmp-{uuid.uuid4().hex}"
    try:
        series.mkdir(parents=True, exist_ok=True)
        source_snapshot = _snapshot(project_root)
        shutil.copytree(project_root, staged)
        if _snapshot(staged) != source_snapshot:
            raise BackupError("バックアップ内容の検証に失敗しました。")
        staged.rename(generation)
        return generation
    except BackupError:
        shutil.rmtree(staged, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(staged, ignore_errors=True)
        raise BackupError(f"バックアップを作成できませんでした: {exc}") from exc
