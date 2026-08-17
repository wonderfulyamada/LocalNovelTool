from __future__ import annotations

import json
from pathlib import Path

import pytest

import local_novel_tool.core.api as api_module
import local_novel_tool.core.migration as migration_module
from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.project import ProjectError
from local_novel_tool.tutorial.generator import generate_tutorial


def _metadata(path: Path) -> dict:
    return json.loads((path / "project.json").read_text(encoding="utf-8"))


def test_new_project_and_tutorial_have_format_version_one(tmp_path: Path) -> None:
    project = CoreAPI().create_project(tmp_path, "新規作品")
    tutorial = generate_tutorial(tmp_path / "チュートリアル")

    assert _metadata(project.root)["format_version"] == 1
    assert _metadata(tutorial)["format_version"] == 1


def test_legacy_project_without_version_opens_as_v1_without_rewrite(
    tmp_path: Path,
) -> None:
    project = CoreAPI().create_project(tmp_path, "旧作品")
    metadata_path = project.root / "project.json"
    data = _metadata(project.root)
    data.pop("format_version")
    metadata_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    before = metadata_path.read_bytes()

    reopened = CoreAPI().open_project(project.root)

    assert reopened.title == "旧作品"
    assert metadata_path.read_bytes() == before
    assert "format_version" not in _metadata(project.root)


def test_v1_project_opens_without_changing_existing_data(tmp_path: Path) -> None:
    project = CoreAPI().create_project(tmp_path, "v1作品")
    metadata_path = project.root / "project.json"
    before = metadata_path.read_bytes()

    reopened = CoreAPI().open_project(project.root)

    assert reopened.title == "v1作品"
    assert metadata_path.read_bytes() == before


def test_future_format_version_is_rejected_without_rewrite(tmp_path: Path) -> None:
    project = CoreAPI().create_project(tmp_path, "未来作品")
    metadata_path = project.root / "project.json"
    data = _metadata(project.root)
    data["format_version"] = 999
    metadata_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    before = metadata_path.read_bytes()

    with pytest.raises(ProjectError, match="未対応.*format_version=999"):
        CoreAPI().open_project(project.root)

    assert metadata_path.read_bytes() == before


def test_future_migration_uses_backup_api_before_conversion(
    tmp_path: Path, monkeypatch
) -> None:
    project = CoreAPI().create_project(tmp_path, "移行対象")
    metadata_path = project.root / "project.json"
    before = metadata_path.read_bytes()
    order: list[str] = []

    def migrate_v1_to_v2(data: dict) -> dict:
        order.append("migrate")
        converted = dict(data)
        converted["format_version"] = 2
        return converted

    monkeypatch.setattr(migration_module, "CURRENT_FORMAT_VERSION", 2)
    monkeypatch.setattr(migration_module, "MIGRATIONS", {1: migrate_v1_to_v2})
    original_backup = api_module.create_project_backup

    def record_backup(project_root: Path, backups_root: Path) -> Path:
        order.append("backup")
        return original_backup(project_root, backups_root)

    monkeypatch.setattr(api_module, "create_project_backup", record_backup)
    backups = tmp_path / "Backups"

    # CoreAPI supplies the existing complete-project backup implementation as
    # the pre-migration hook. The migration itself remains format-layer code.
    reopened = CoreAPI().open_project(
        project.root, migration_backups_root=backups
    )

    assert reopened.title == "移行対象"
    generations = list(backups.rglob("project.json"))
    assert len(generations) == 1
    assert generations[0].read_bytes() == before
    assert metadata_path.read_bytes() == before
    assert order == ["backup", "migrate"]
