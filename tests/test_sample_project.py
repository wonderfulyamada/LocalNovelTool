from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from local_novel_tool.core.api import CoreAPI
from local_novel_tool.gui.sample_project import (
    SAMPLE_INITIALIZED_KEY,
    SAMPLE_PROJECT_TITLE,
    archive_tutorial_project,
    initialize_sample_project,
    recreate_tutorial_project,
    tutorial_resource_path,
)


def make_settings(path: Path) -> QSettings:
    return QSettings(str(path / "settings.ini"), QSettings.Format.IniFormat)


def assert_tutorial_contents(api: CoreAPI) -> None:
    project = api.project
    assert project is not None
    assert project.title == SAMPLE_PROJECT_TITLE
    assert [chapter.title for chapter in project.chapters] == [
        "まず触ってみよう",
        "設定を整理しよう",
        "練習用の章",
    ]
    assert [len(chapter.episodes) for chapter in project.chapters] == [4, 4, 1]
    assert [reference.title for reference in project.references] == [
        "サンプル主人公",
        "白雨",
        "サンプルの町",
        "自由メモの例",
    ]
    assert len(project.plot_items) == 3
    assert len(project.timeline_items) == 3
    hit_kinds = {result.kind for result in api.search("白雨")}
    assert {"episode", "reference"} <= hit_kinds


def test_bundled_tutorial_is_a_readable_project(tmp_path: Path) -> None:
    resource = tutorial_resource_path()
    assert resource.name == "tutorial"
    copied_resource = tmp_path / "tutorial"
    shutil.copytree(resource, copied_resource)
    api = CoreAPI()
    api.open_project(copied_resource)
    assert_tutorial_contents(api)


def test_first_launch_copies_complete_tutorial_project(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    api = CoreAPI()
    source = tutorial_resource_path()
    source_metadata = (source / "project.json").read_bytes()

    project = initialize_sample_project(api, settings, tmp_path / "作品 保存先")

    assert project is not None
    assert project.root == (tmp_path / "作品 保存先" / SAMPLE_PROJECT_TITLE).resolve()
    assert settings.value(SAMPLE_INITIALIZED_KEY, False, bool)
    assert_tutorial_contents(api)
    assert (source / "project.json").read_bytes() == source_metadata


def test_initialized_sample_is_not_created_again(tmp_path: Path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    settings.setValue(SAMPLE_INITIALIZED_KEY, True)
    api = CoreAPI()

    def unexpected_copy(*_args, **_kwargs):
        raise AssertionError("sample was recreated")

    monkeypatch.setattr(shutil, "copytree", unexpected_copy)
    assert initialize_sample_project(api, settings, tmp_path / "保存先") is None


def test_deleted_sample_is_not_recreated(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    parent = tmp_path / "保存先"
    first_api = CoreAPI()
    project = initialize_sample_project(first_api, settings, parent)
    assert project is not None
    shutil.rmtree(project.root)

    second_api = CoreAPI()
    assert initialize_sample_project(second_api, settings, parent) is None
    assert not (parent / SAMPLE_PROJECT_TITLE).exists()


def test_failed_sample_creation_leaves_no_project_or_flag(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    parent = tmp_path / "保存先"
    broken_source = tmp_path / "壊れた原本"
    broken_source.mkdir()
    (broken_source / "project.json").write_text("{broken", encoding="utf-8")
    api = CoreAPI()

    with pytest.raises(Exception):
        initialize_sample_project(api, settings, parent, broken_source)

    assert not settings.value(SAMPLE_INITIALIZED_KEY, False, bool)
    assert not (parent / SAMPLE_PROJECT_TITLE).exists()
    assert api.project is None


def test_recreate_tutorial_replaces_only_tutorial(tmp_path: Path) -> None:
    parent = tmp_path / "作品"
    settings = make_settings(tmp_path)
    api = CoreAPI()
    tutorial = initialize_sample_project(api, settings, parent)
    assert tutorial is not None
    edited_file = tutorial.root / tutorial.chapters[0].episodes[0].body_file
    edited_file.write_text("ユーザー編集", encoding="utf-8")

    normal_api = CoreAPI()
    normal = normal_api.create_project(parent, "通常作品")
    marker = normal.root / "残す.txt"
    marker.write_text("保護対象", encoding="utf-8")

    recreated = recreate_tutorial_project(api, parent)
    assert recreated.root == tutorial.root
    assert edited_file.read_text(encoding="utf-8") != "ユーザー編集"
    assert marker.read_text(encoding="utf-8") == "保護対象"
    assert_tutorial_contents(api)


def test_failed_recreate_preserves_existing_tutorial(tmp_path: Path) -> None:
    parent = tmp_path / "作品"
    settings = make_settings(tmp_path)
    api = CoreAPI()
    tutorial = initialize_sample_project(api, settings, parent)
    assert tutorial is not None
    marker = tutorial.root / "編集済み.txt"
    marker.write_text("維持", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        recreate_tutorial_project(api, parent, tmp_path / "存在しない原本")

    assert marker.read_text(encoding="utf-8") == "維持"


def test_archive_succeeds_before_tutorial_is_recreated(tmp_path: Path) -> None:
    tutorial_parent = tmp_path / "LocalNovelTool"
    projects_root = tmp_path / "作品"
    settings = make_settings(tmp_path)
    api = CoreAPI()
    tutorial = initialize_sample_project(api, settings, tutorial_parent)
    assert tutorial is not None
    edited = tutorial.root / "ユーザー編集.txt"
    edited.write_text("残す内容", encoding="utf-8")

    archived = archive_tutorial_project(
        tutorial.root, projects_root, datetime(2026, 8, 16, 13, 36)
    )
    recreate_tutorial_project(api, tutorial_parent)

    assert (archived / "ユーザー編集.txt").read_text(encoding="utf-8") == "残す内容"
    assert not edited.exists()
    assert_tutorial_contents(api)


def test_archive_never_overwrites_same_named_destination(tmp_path: Path) -> None:
    tutorial_parent = tmp_path / "LocalNovelTool"
    projects_root = tmp_path / "作品"
    settings = make_settings(tmp_path)
    api = CoreAPI()
    tutorial = initialize_sample_project(api, settings, tutorial_parent)
    assert tutorial is not None
    projects_root.mkdir()
    existing = projects_root / "LocalNovelTool チュートリアル - 保存 2026-08-16 1336"
    existing.mkdir()
    marker = existing / "既存.txt"
    marker.write_text("上書き禁止", encoding="utf-8")

    archived = archive_tutorial_project(
        tutorial.root, projects_root, datetime(2026, 8, 16, 13, 36)
    )

    assert archived.name.endswith("(2)")
    assert marker.read_text(encoding="utf-8") == "上書き禁止"
    assert (archived / "project.json").is_file()
