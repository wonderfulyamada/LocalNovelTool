from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from local_novel_tool.core.recovery import RecoveryStore
from local_novel_tool.gui.main_window import MainWindow


def make_window(tmp_path: Path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(MainWindow, "_try_open_initial_project", lambda self: None)
    window = MainWindow()
    window.recovery_store = RecoveryStore(tmp_path / "AppData" / "Recovery")
    projects = tmp_path / "projects"
    projects.mkdir()
    project = window.api.create_project(projects, "作品")
    chapter = window.api.create_chapter("章")
    episode = window.api.create_episode(chapter.id, "話")
    window._after_project_loaded()
    return app, window, project, episode


def test_unsaved_edit_creates_recovery_and_successful_save_removes_it(tmp_path, monkeypatch):
    _app, window, project, episode = make_window(tmp_path, monkeypatch)
    window.editor_tab.editor.setPlainText("未保存本文")
    window._write_pending_recovery()
    entries = window.recovery_store.load(project.root)
    assert [(item.source, item.item_id, item.content) for item in entries] == [("body", episode.id, "未保存本文")]

    window.save_current_body("未保存本文")
    assert window.recovery_store.load(project.root) == []
    assert window.api.load_episode_body(episode.id) == "未保存本文"
    window.close()


def test_failed_save_keeps_recovery_and_canonical_file(tmp_path, monkeypatch):
    _app, window, project, episode = make_window(tmp_path, monkeypatch)
    window.editor_tab.editor.setPlainText("復旧対象")
    window._write_pending_recovery()
    monkeypatch.setattr(window.api, "save_episode_body", lambda *_args: (_ for _ in ()).throw(OSError("失敗")))

    with pytest.raises(OSError):
        window.save_current_body("復旧対象")

    assert window.recovery_store.load(project.root)[0].content == "復旧対象"
    assert project.load_episode_body(episode.id) == ""
    window._dirty_sources.clear()
    window.close()


def test_recovery_is_detected_and_restored_without_changing_canonical(tmp_path, monkeypatch):
    _app, window, project, episode = make_window(tmp_path, monkeypatch)
    project.save_episode_body(episode.id, "正本")
    window.recovery_store.save(project.root, "body", episode.id, "復旧本文")
    monkeypatch.setattr(window, "_confirm_recovery", lambda _entry: True)

    window._offer_recovery()

    assert window.editor_tab.editor.toPlainText() == "復旧本文"
    assert window._has_unsaved_changes()
    assert project.load_episode_body(episode.id) == "正本"
    window._dirty_sources.clear()
    window.close()


def test_ignored_and_identical_recovery_do_not_change_project(tmp_path, monkeypatch):
    _app, window, project, episode = make_window(tmp_path, monkeypatch)
    project.save_episode_body(episode.id, "正本")
    window.recovery_store.save(project.root, "body", episode.id, "無視する本文")
    monkeypatch.setattr(window, "_confirm_recovery", lambda _entry: False)
    window._offer_recovery()
    assert project.load_episode_body(episode.id) == "正本"
    assert window.recovery_store.load(project.root) == []

    window.recovery_store.save(project.root, "body", episode.id, "正本")
    monkeypatch.setattr(window, "_confirm_recovery", lambda _entry: pytest.fail("同内容で確認された"))
    window._offer_recovery()
    assert window.recovery_store.load(project.root) == []
    window.close()


def test_recovery_separates_projects_and_episodes(tmp_path):
    store = RecoveryStore(tmp_path / "AppData" / "Recovery")
    first = tmp_path / "作品 A"
    second = tmp_path / "作品 B"
    store.save(first, "body", "ep-1", "A1")
    store.save(first, "note", "ep-2", "A2")
    store.save(second, "body", "ep-1", "B1")

    assert {(item.source, item.item_id, item.content) for item in store.load(first)} == {("body", "ep-1", "A1"), ("note", "ep-2", "A2")}
    assert [(item.source, item.item_id, item.content) for item in store.load(second)] == [("body", "ep-1", "B1")]


def test_legacy_recovery_restore_ignore_and_same_content_cleanup(tmp_path, monkeypatch):
    _app, window, project, episode = make_window(tmp_path, monkeypatch)
    legacy = RecoveryStore(tmp_path / "legacy-appdata" / "Recovery")
    window.legacy_recovery_store = legacy
    project.save_episode_body(episode.id, "正本")
    legacy.save(project.root, "body", episode.id, "正本")
    monkeypatch.setattr(window, "_confirm_recovery", lambda _entry: pytest.fail("same content prompt"))
    window._offer_recovery()
    assert legacy.load(project.root) == []

    legacy.save(project.root, "body", episode.id, "旧Recovery")
    legacy.save(project.root, "note", episode.id, "別のRecovery")
    monkeypatch.setattr(window, "_confirm_recovery", lambda _entry: True)
    window._offer_recovery()
    assert window.editor_tab.editor.toPlainText() == "旧Recovery"
    assert project.load_episode_body(episode.id) == "正本"
    assert len(legacy.load(project.root)) == 2
    window.save_current_body("旧Recovery")
    assert project.load_episode_body(episode.id) == "旧Recovery"
    assert [(item.source, item.content) for item in legacy.load(project.root)] == [("note", "別のRecovery")]

    monkeypatch.setattr(window, "_confirm_recovery", lambda _entry: False)
    window._offer_recovery()
    assert legacy.load(project.root) == []
    window.close()
