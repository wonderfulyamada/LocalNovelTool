from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from local_novel_tool.core.api import CoreAPI
from local_novel_tool.gui.sample_project import (
    SAMPLE_INITIALIZED_KEY,
    SAMPLE_PROJECT_TITLE,
    SAMPLE_REFERENCES,
    TABS_BODY,
    WELCOME_BODY,
    WELCOME_NOTE,
    initialize_sample_project,
)


def make_settings(path: Path) -> QSettings:
    return QSettings(str(path / "settings.ini"), QSettings.Format.IniFormat)


def test_first_launch_creates_complete_sample_project(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    api = CoreAPI()

    project = initialize_sample_project(api, settings, tmp_path / "作品 保存先")

    assert project is not None
    assert project.title == SAMPLE_PROJECT_TITLE
    assert project.root == (tmp_path / "作品 保存先" / SAMPLE_PROJECT_TITLE).resolve()
    assert settings.value(SAMPLE_INITIALIZED_KEY, False, bool)
    assert len(project.chapters) == 1
    chapter = project.chapters[0]
    assert chapter.title == "はじめに"
    assert [episode.title for episode in chapter.episodes] == [
        "ようこそ",
        "各タブを試してみる",
    ]
    assert api.load_episode_body(chapter.episodes[0].id) == WELCOME_BODY
    assert api.load_episode_body(chapter.episodes[1].id) == TABS_BODY
    assert api.load_episode_note(chapter.episodes[0].id) == WELCOME_NOTE
    assert [
        (reference.category, reference.title, api.load_reference(reference.id))
        for reference in project.references
    ] == list(SAMPLE_REFERENCES)


def test_initialized_sample_is_not_created_again(tmp_path: Path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    settings.setValue(SAMPLE_INITIALIZED_KEY, True)
    api = CoreAPI()

    def unexpected_create(_parent: Path, _title: str):
        raise AssertionError("sample was recreated")

    monkeypatch.setattr(api, "create_project", unexpected_create)
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
    class FailingAPI(CoreAPI):
        def save_episode_body(self, episode_id: str, text: str) -> None:
            raise RuntimeError("sample creation failed")

    settings = make_settings(tmp_path)
    parent = tmp_path / "保存先"
    api = FailingAPI()

    with pytest.raises(RuntimeError, match="sample creation failed"):
        initialize_sample_project(api, settings, parent)

    assert not settings.value(SAMPLE_INITIALIZED_KEY, False, bool)
    assert not (parent / SAMPLE_PROJECT_TITLE).exists()
    assert api.project is None
