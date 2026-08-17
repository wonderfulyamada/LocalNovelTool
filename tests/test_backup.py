from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

import local_novel_tool.core.backup as backup_module
from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.backup import BackupError, create_project_backup


FIXED_TIME = datetime(2026, 8, 16, 13, 36, 0)


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _project(parent: Path, title: str = "作品") -> tuple[CoreAPI, Path]:
    parent.mkdir(parents=True, exist_ok=True)
    api = CoreAPI()
    project = api.create_project(parent, title)
    chapter = api.create_chapter("章")
    episode = api.create_episode(chapter.id, "話")
    api.save_episode_body(episode.id, "本文")
    api.save_episode_note(episode.id, "話メモ")
    return api, project.root


def test_complete_project_backup_matches_source_and_is_separate(tmp_path: Path) -> None:
    api, source = _project(tmp_path / "正本", "日本語 作品")
    backups = tmp_path / "別領域" / "Backups"
    before = _files(source)

    destination = create_project_backup(source, backups, created_at=FIXED_TIME)

    assert destination.parent.parent == backups.resolve()
    assert destination.name == "20260816-133600"
    assert _files(destination) == before
    assert _files(source) == before
    reopened = CoreAPI().open_project(destination)
    assert reopened.title == api.project.title
    assert reopened.load_episode_body(reopened.chapters[0].episodes[0].id) == "本文"


def test_backup_generations_never_overwrite(tmp_path: Path) -> None:
    _api, source = _project(tmp_path / "projects")
    backups = tmp_path / "Backups"

    first = create_project_backup(source, backups, created_at=FIXED_TIME)
    second = create_project_backup(source, backups, created_at=FIXED_TIME)

    assert first != second
    assert first.name == "20260816-133600"
    assert second.name == "20260816-133600-2"
    assert (first / "project.json").is_file()
    assert (second / "project.json").is_file()


def test_backup_failure_preserves_official_project(
    tmp_path: Path, monkeypatch
) -> None:
    _api, source = _project(tmp_path / "projects")
    before = _files(source)

    def fail_copy(_source: Path, staged: Path) -> None:
        staged.mkdir()
        (staged / "partial.txt").write_text("partial", encoding="utf-8")
        raise OSError("copy failed")

    monkeypatch.setattr(backup_module.shutil, "copytree", fail_copy)
    with pytest.raises(BackupError, match="copy failed"):
        create_project_backup(source, tmp_path / "Backups", created_at=FIXED_TIME)

    assert _files(source) == before
    assert not list((tmp_path / "Backups").rglob("project.json"))
    assert not list((tmp_path / "Backups").rglob("*.tmp-*"))


def test_empty_project_can_be_backed_up(tmp_path: Path) -> None:
    parent = tmp_path / "空作品 親"
    parent.mkdir()
    project = CoreAPI().create_project(parent, "空の作品")

    destination = create_project_backup(
        project.root, tmp_path / "バックアップ 保存先", created_at=FIXED_TIME
    )

    restored = CoreAPI().open_project(destination)
    assert restored.chapters == []
    assert (destination / "project.json").is_file()


def test_core_api_creates_backup_without_changing_existing_project(tmp_path: Path) -> None:
    api, source = _project(tmp_path / "projects", "既存 作品")
    before = _files(source)

    destination = api.create_backup(tmp_path / "Backups 日本語")

    assert destination.is_dir()
    assert api.project is not None
    assert api.project.root == source
    assert _files(source) == before
