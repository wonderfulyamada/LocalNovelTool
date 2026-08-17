from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QWidget

import local_novel_tool.gui.main_window as main_window_module
import local_novel_tool.gui.preview_tab as preview_module
from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.project import ProjectContentError, ProjectError


@pytest.mark.parametrize(
    "broken_json",
    (
        '{"format_version": 1, invalid}',
        '{"format_version": 1, "title": "途中",',
    ),
)
def test_broken_project_json_is_identified_and_never_rewritten(
    tmp_path: Path, broken_json: str
) -> None:
    root = tmp_path / "破損作品"
    root.mkdir()
    metadata = root / "project.json"
    metadata.write_text(broken_json, encoding="utf-8")
    before = metadata.read_bytes()

    with pytest.raises(ProjectError) as error:
        CoreAPI().open_project(root)

    assert "project.json が壊れています" in str(error.value)
    assert str(metadata.resolve()) in str(error.value)
    assert metadata.read_bytes() == before
    assert list(root.iterdir()) == [metadata]


def _content_project(parent: Path) -> tuple[CoreAPI, object, object, object]:
    parent.mkdir()
    api = CoreAPI()
    project = api.create_project(parent, "部分破損作品")
    chapter = api.create_chapter("章")
    episode = api.create_episode(chapter.id, "話")
    api.save_episode_body(episode.id, "読める本文")
    api.save_episode_note(episode.id, "読める話メモ")
    reference = api.create_reference("登場人物", "人物")
    api.save_reference(reference.id, "読める資料")
    return api, project, episode, reference


@pytest.mark.parametrize("kind", ("body", "note"))
def test_missing_episode_file_keeps_other_content_and_gui_running(
    tmp_path: Path, monkeypatch, kind: str
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    api, project, episode, _reference = _content_project(tmp_path / "projects")
    missing_relative = episode.body_file if kind == "body" else episode.note_file
    missing = project.root / missing_relative
    missing.unlink()
    metadata = project.root / "project.json"
    metadata_before = metadata.read_bytes()
    readable = (
        project.root / (episode.note_file if kind == "body" else episode.body_file)
    )
    readable_before = readable.read_bytes()
    warnings: list[str] = []
    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "warning",
        lambda _parent, _title, text: warnings.append(text),
    )
    window = main_window_module.MainWindow()
    window.api.open_project(project.root)

    window._after_project_loaded()

    assert window.current_episode_id == episode.id
    if kind == "body":
        assert window.editor_tab.editor.toPlainText() == ""
        assert window.note_tab.editor.toPlainText() == "読める話メモ"
    else:
        assert window.editor_tab.editor.toPlainText() == "読める本文"
        assert window.note_tab.editor.toPlainText() == ""
    assert warnings and str(missing.resolve()) in warnings[-1]
    assert not missing.exists()
    assert readable.read_bytes() == readable_before
    assert metadata.read_bytes() == metadata_before
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_missing_reference_is_identified_without_metadata_rewrite(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    _api, project, _episode, reference = _content_project(tmp_path / "projects")
    missing = project.root / reference.file
    missing.unlink()
    metadata = project.root / "project.json"
    before = metadata.read_bytes()
    warnings: list[str] = []
    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "warning",
        lambda _parent, _title, text: warnings.append(text),
    )
    window = main_window_module.MainWindow()
    window.api.open_project(project.root)
    window._after_project_loaded()

    window.open_reference(reference.id)

    assert window.reference_tab.editor.toPlainText() == ""
    assert warnings and str(missing.resolve()) in warnings[-1]
    assert not missing.exists()
    assert metadata.read_bytes() == before
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_missing_content_error_names_the_problem_file(tmp_path: Path) -> None:
    api, project, episode, reference = _content_project(tmp_path / "projects")
    plot = api.create_plot_item("検索可能", "検索語を含む読めるデータ")
    targets = (
        (project.root / episode.body_file, lambda: api.load_episode_body(episode.id)),
        (project.root / episode.note_file, lambda: api.load_episode_note(episode.id)),
        (project.root / reference.file, lambda: api.load_reference(reference.id)),
    )
    for path, load in targets:
        path.unlink()
        with pytest.raises(ProjectContentError) as error:
            load()
        assert str(path.resolve()) in str(error.value)
        assert not path.exists()

    results = api.search("検索語")
    assert [result.source_id for result in results] == [plot.id]
    errors = api.content_errors()
    assert len(errors) == 3
    assert all("見つかりません" in str(error) for error in errors)
