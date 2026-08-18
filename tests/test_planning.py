from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QModelIndex, QSettings, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget

import local_novel_tool.gui.main_window as main_window_module
import local_novel_tool.gui.backup_worker as backup_worker_module
import local_novel_tool.gui.preview_tab as preview_module
from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.models import SearchResult
from local_novel_tool.core.project import REFERENCE_CATEGORIES
from local_novel_tool.gui.plot_tab import PlotTab
from local_novel_tool.gui.sample_project import (
    SAMPLE_PROJECT_TITLE,
    initialize_sample_project,
)
from local_novel_tool.gui.timeline_tab import TimelineTab
from local_novel_tool.tutorial.generator import tutorial_matches_template
from local_novel_tool.tutorial.template import TUTORIAL_TEXT_FILES


def test_plot_crud_and_reorder(tmp_path: Path) -> None:
    api = CoreAPI()
    api.create_project(tmp_path, "展開テスト")
    chapter = api.create_chapter("第一章")
    episode = api.create_episode(chapter.id, "第一話")
    first = api.create_plot_item("冒険開始", "旅立つ", chapter.id, episode.id)
    second = api.create_plot_item("対決", "敵と戦う")

    api.update_plot_item(first.id, "旅の始まり", "港から出る", chapter.id, episode.id)
    updated = api.project.get_plot_item(first.id)
    assert (updated.title, updated.content) == ("旅の始まり", "港から出る")
    assert (updated.chapter_id, updated.episode_id) == (chapter.id, episode.id)

    api.reorder_plot_items([second.id, first.id])
    assert [item.id for item in api.plot_items()] == [second.id, first.id]
    api.delete_plot_item(second.id)
    assert [item.id for item in api.plot_items()] == [first.id]

    reopened = CoreAPI()
    reopened.open_project(tmp_path / "展開テスト")
    persisted = reopened.plot_items()[0]
    assert (persisted.title, persisted.content) == ("旅の始まり", "港から出る")


def test_timeline_crud_and_reorder(tmp_path: Path) -> None:
    api = CoreAPI()
    api.create_project(tmp_path, "時系列テスト")
    first = api.create_timeline_item("2年前", "出会い", "森で出会う")
    second = api.create_timeline_item("現在", "旅立ち", "港へ向かう")

    api.update_timeline_item(first.id, "3年前", "最初の出会い", "雨の森")
    updated = api.project.get_timeline_item(first.id)
    assert (updated.point, updated.title, updated.content) == (
        "3年前",
        "最初の出会い",
        "雨の森",
    )

    api.reorder_timeline_items([second.id, first.id])
    assert [item.id for item in api.timeline_items()] == [second.id, first.id]
    api.delete_timeline_item(second.id)
    assert [item.id for item in api.timeline_items()] == [first.id]

    reopened = CoreAPI()
    reopened.open_project(tmp_path / "時系列テスト")
    persisted = reopened.timeline_items()[0]
    assert (persisted.point, persisted.title, persisted.content) == (
        "3年前",
        "最初の出会い",
        "雨の森",
    )


def test_reference_categories_and_cross_search(tmp_path: Path) -> None:
    assert REFERENCE_CATEGORIES == ("登場人物", "アイテム", "世界観", "その他")
    api = CoreAPI()
    api.create_project(tmp_path, "横断検索")
    chapter = api.create_chapter("第一章")
    episode = api.create_episode(chapter.id, "第三話")
    api.save_episode_body(episode.id, "本文の合言葉")
    api.save_episode_note(episode.id, "話メモの合言葉")
    reference = api.create_reference("登場人物", "サンプル主人公")
    api.save_reference(reference.id, "資料の合言葉")
    plot = api.create_plot_item("冒険開始", "展開の合言葉", chapter.id, episode.id)
    timeline = api.create_timeline_item("2年前", "出会い", "時系列の合言葉")

    expected = {
        "本文": ("episode", episode.id),
        "話メモ": ("episode_note", episode.id),
        "資料": ("reference", reference.id),
        "展開": ("plot", plot.id),
        "時系列": ("timeline", timeline.id),
    }
    for query, identity in expected.items():
        hits = api.search(f"{query}の合言葉")
        assert [(hit.kind, hit.source_id) for hit in hits] == [identity]

    assert api.search("サンプル主人公")[0].category == "登場人物"
    assert api.search("冒険開始")[0].kind == "plot"
    timeline_hit = api.search("出会い")[0]
    assert (timeline_hit.kind, timeline_hit.category) == ("timeline", "2年前")


def test_opening_old_project_adds_empty_planning_and_maps_categories(
    tmp_path: Path,
) -> None:
    root = tmp_path / "旧作品"
    root.mkdir()
    for folder in ("manuscript", "episode_notes", "references", "backups"):
        (root / folder).mkdir()
    (root / "references" / "old.txt").write_text("旧資料", encoding="utf-8")
    (root / "project.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "title": "旧作品",
                "chapters": [],
                "references": [
                    {
                        "id": "ref_old",
                        "category": "キャラ",
                        "title": "旧人物",
                        "file": "references/old.txt",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    api = CoreAPI()
    project = api.open_project(root)
    assert project.references[0].category == "登場人物"
    assert api.plot_items() == []
    assert api.timeline_items() == []


def test_search_result_opens_plot_and_timeline_tabs(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_try_open_initial_project",
        lambda self: None,
    )
    window = main_window_module.MainWindow()
    window.settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    window.api.create_project(tmp_path, "検索遷移")
    plot = window.api.create_plot_item("冒険開始", "内容")
    timeline = window.api.create_timeline_item("現在", "出会い", "内容")
    window._after_project_loaded()

    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "本文",
        "プレビュー",
        "話メモ",
        "展開",
        "時系列",
        "文章検索",
        "資料",
    ]
    tab_style = window.tabs.tabBar().styleSheet()
    assert "min-height: 24px" in tab_style
    assert "padding: 6px 14px" in tab_style
    assert "QTabBar::tab:selected" in tab_style
    assert "font-weight: bold" in tab_style
    assert "border-bottom: 2px solid palette(highlight)" in tab_style
    assert window.tabs.tabBar().usesScrollButtons()
    assert "チュートリアルを再作成" in [
        action.text() for action in window.findChildren(main_window_module.QAction)
    ]

    window.open_search_result(
        SearchResult("plot", plot.id, plot.title, "", 1, "冒険開始")
    )
    assert window.tabs.currentWidget() is window.plot_tab
    assert window.plot_tab.current_id == plot.id

    window.open_search_result(
        SearchResult(
            "timeline", timeline.id, timeline.title, timeline.point, 1, "出会い"
        )
    )
    assert window.tabs.currentWidget() is window.timeline_tab
    assert window.timeline_tab.current_id == timeline.id

    tutorial_parent = tmp_path / "ドキュメント"
    (tutorial_parent / main_window_module.SAMPLE_PROJECT_TITLE).mkdir(parents=True)
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tutorial_parent),
    )
    monkeypatch.setattr(
        window, "_tutorial_recreation_choice", lambda: "cancel"
    )
    monkeypatch.setattr(
        main_window_module,
        "recreate_tutorial_project",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cancelled recreation ran")
        ),
    )
    window.recreate_tutorial()

    recreated: list[Path] = []
    monkeypatch.setattr(
        window, "_tutorial_recreation_choice", lambda: "recreate"
    )
    monkeypatch.setattr(
        main_window_module,
        "recreate_tutorial_project",
        lambda _api, parent: recreated.append(parent),
    )
    window.recreate_tutorial()
    assert recreated == [tutorial_parent]
    assert window.settings.value(
        main_window_module.SAMPLE_INITIALIZED_KEY, False, bool
    )
    window.close()
    app.processEvents()


def test_new_project_uses_dedicated_projects_folder(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tmp_path / "Documents" / "LocalNovelTool"),
    )
    class FakeNewProjectDialog:
        def __init__(self, projects_parent, _parent) -> None:
            assert projects_parent == tmp_path / "Documents" / "LocalNovelTool" / "作品"

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def project_title(self) -> str:
            return "新しい作品"

    monkeypatch.setattr(main_window_module, "NewProjectDialog", FakeNewProjectDialog)
    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("保存先選択ダイアログが表示されました")
        ),
    )

    window = main_window_module.MainWindow()
    window.settings = QSettings(
        str(tmp_path / "settings-new.ini"), QSettings.Format.IniFormat
    )
    window.new_project()

    root = tmp_path / "Documents" / "LocalNovelTool" / "作品" / "新しい作品"
    assert window.api.project is not None
    assert window.api.project.root == root.resolve()
    assert (root / "project.json").is_file()
    for folder in ("manuscript", "episode_notes", "references", "backups"):
        assert (root / folder).is_dir()

    window.close()
    app.processEvents()


def test_failed_tutorial_archive_prevents_recreation_and_preserves_normal_project(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    tutorial_parent = tmp_path / "Documents" / "LocalNovelTool"
    tutorial_root = tutorial_parent / main_window_module.SAMPLE_PROJECT_TITLE
    tutorial_root.mkdir(parents=True)
    (tutorial_root / "project.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tutorial_parent),
    )

    window = main_window_module.MainWindow()
    window.settings = QSettings(
        str(tmp_path / "settings-archive.ini"), QSettings.Format.IniFormat
    )
    normal_parent = tmp_path / "normal"
    normal_parent.mkdir()
    normal = window.api.create_project(normal_parent, "通常作品")
    marker = normal.root / "変更しない.txt"
    marker.write_text("保護対象", encoding="utf-8")
    window._after_project_loaded()

    monkeypatch.setattr(window, "_tutorial_recreation_choice", lambda: "archive")
    monkeypatch.setattr(
        main_window_module,
        "archive_tutorial_project",
        lambda *_args: (_ for _ in ()).throw(OSError("コピー失敗")),
    )
    recreated = []
    monkeypatch.setattr(
        main_window_module,
        "recreate_tutorial_project",
        lambda *_args: recreated.append(True),
    )
    errors = []
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "critical",
        lambda *_args: errors.append(_args[2]),
    )

    window.recreate_tutorial()

    assert recreated == []
    assert errors == ["コピー失敗"]
    assert marker.read_text(encoding="utf-8") == "保護対象"
    assert window.api.project is normal
    assert (tutorial_root / "project.json").is_file()
    window.close()
    app.processEvents()


def test_tutorial_menu_archives_and_reloads_bundled_original(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    tutorial_parent = tmp_path / "Documents" / "LocalNovelTool"
    projects_root = tmp_path / "configured-projects"
    projects_root.mkdir()
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tutorial_parent),
    )
    window = main_window_module.MainWindow()
    window.settings = QSettings(
        str(tmp_path / "settings-regression.ini"), QSettings.Format.IniFormat
    )
    window._set_projects_parent(projects_root)
    tutorial = initialize_sample_project(window.api, window.settings, tutorial_parent)
    assert tutorial is not None
    window._after_project_loaded()
    edited_relative = tutorial.chapters[0].episodes[0].body_file
    edited = tutorial.root / edited_relative
    edited.write_text("退避する内容", encoding="utf-8")

    monkeypatch.setattr(window, "_tutorial_recreation_choice", lambda: "archive")
    action = next(
        item
        for item in window.findChildren(main_window_module.QAction)
        if item.text() == "チュートリアルを再作成"
    )
    action.trigger()

    archives = list(projects_root.iterdir())
    assert len(archives) == 1
    assert (archives[0] / edited_relative).read_text(encoding="utf-8") == "退避する内容"
    assert window.api.project is not None
    assert window.api.project.root == (tutorial_parent / SAMPLE_PROJECT_TITLE).resolve()
    assert tutorial_matches_template(window.api.project.root)

    direct_relative = window.api.project.chapters[0].episodes[0].body_file
    direct_body = window.api.project.root / direct_relative
    direct_body.write_text("削除対象", encoding="utf-8")
    monkeypatch.setattr(window, "_tutorial_recreation_choice", lambda: "recreate")
    action.trigger()
    assert direct_body.read_bytes() == TUTORIAL_TEXT_FILES[direct_relative].encode(
        "utf-8"
    )
    assert list(projects_root.iterdir()) == archives
    window.close()
    app.processEvents()


def test_content_font_toolbar_persists_clamps_and_updates_editors(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(main_window_module.MainWindow, "_try_open_initial_project", lambda self: None)
    window = main_window_module.MainWindow()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue(main_window_module.CONTENT_FONT_SIZE_KEY, 20)
    window.settings = settings
    window._set_content_font_size(window._content_font_size())
    assert window.content_font_size_spin.value() == 20
    assert window.editor_tab.editor.font().pointSize() == 20
    assert window.note_tab.editor.font().pointSize() == 20
    assert window.reference_tab.editor.font().pointSize() == 20
    tree_size = window.tree.font().pointSize()
    window.content_font_size_spin.setValue(32)
    assert window.plot_tab.content.font().pointSize() == 32
    assert window.timeline_tab.content.font().pointSize() == 32
    assert window.tree.font().pointSize() == tree_size
    window._set_content_font_size(100)
    assert window.content_font_size_spin.value() == 32
    window._set_content_font_size(1)
    assert window.content_font_size_spin.value() == 10
    assert settings.value(main_window_module.CONTENT_FONT_SIZE_KEY, 0, int) == 10
    window.close()
    app.processEvents()


def test_content_font_shortcuts_step_and_clamp(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window_module.MainWindow, "_try_open_initial_project", lambda self: None)
    window = main_window_module.MainWindow()
    window.settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window._set_content_font_size(20)
    window.increase_font_action.trigger()
    assert window.content_font_size_spin.value() == 21
    window.decrease_font_action.trigger()
    assert window.content_font_size_spin.value() == 20
    window._set_content_font_size(32)
    window.increase_font_action.trigger()
    assert window.content_font_size_spin.value() == 32
    window._set_content_font_size(10)
    window.decrease_font_action.trigger()
    assert window.content_font_size_spin.value() == 10
    window.close()
    app.processEvents()


def test_tutorial_choice_maps_qt_button_roles() -> None:
    assert main_window_module.MainWindow._tutorial_choice_for_role(
        QMessageBox.ButtonRole.AcceptRole
    ) == "archive"
    assert main_window_module.MainWindow._tutorial_choice_for_role(
        QMessageBox.ButtonRole.DestructiveRole
    ) == "recreate"
    assert main_window_module.MainWindow._tutorial_choice_for_role(
        QMessageBox.ButtonRole.RejectRole
    ) == "cancel"


def test_missing_and_initial_tutorial_do_not_create_unnecessary_archive(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    tutorial_parent = tmp_path / "Documents" / "LocalNovelTool"
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tutorial_parent),
    )
    window = main_window_module.MainWindow()
    window.settings = QSettings(
        str(tmp_path / "settings-initial-tutorial.ini"), QSettings.Format.IniFormat
    )
    window._set_projects_parent(projects_root)
    monkeypatch.setattr(
        window,
        "_tutorial_recreation_choice",
        lambda: (_ for _ in ()).throw(AssertionError("編集済み三択が表示されました")),
    )

    window.recreate_tutorial()
    tutorial_root = tutorial_parent / SAMPLE_PROJECT_TITLE
    assert (tutorial_root / "project.json").is_file()
    assert list(projects_root.iterdir()) == []

    before = {
        path.relative_to(tutorial_root): path.read_bytes()
        for path in tutorial_root.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(window, "_confirm_recreate_current_tutorial", lambda: False)
    window.recreate_tutorial()
    after_cancel = {
        path.relative_to(tutorial_root): path.read_bytes()
        for path in tutorial_root.rglob("*")
        if path.is_file()
    }
    assert after_cancel == before
    assert list(projects_root.iterdir()) == []

    monkeypatch.setattr(window, "_confirm_recreate_current_tutorial", lambda: True)
    monkeypatch.setattr(
        main_window_module,
        "archive_tutorial_project",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("初期状態が退避されました")
        ),
    )
    window.recreate_tutorial()
    assert list(projects_root.iterdir()) == []
    assert main_window_module.tutorial_matches_bundled(tutorial_root)

    relative = window.api.project.chapters[0].episodes[0].body_file
    body = tutorial_root / relative
    body.write_text(body.read_text(encoding="utf-8") + "一", encoding="utf-8")
    choices = []
    monkeypatch.setattr(
        window, "_confirm_recreate_current_tutorial", lambda: (_ for _ in ()).throw(
            AssertionError("編集済みが初期状態扱いされました")
        )
    )
    monkeypatch.setattr(
        window, "_tutorial_recreation_choice", lambda: choices.append(True) or "cancel"
    )
    window.recreate_tutorial()
    assert choices == [True]
    assert body.read_text(encoding="utf-8").endswith("一")

    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_new_project_dialog_destination_tracks_trimmed_title(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    parent = tmp_path / "Documents" / "LocalNovelTool" / "作品"
    dialog = main_window_module.NewProjectDialog(parent)

    dialog.title_edit.setText("  私の小説  ")

    assert dialog.project_title() == "私の小説"
    assert dialog.destination_label.text() == str(parent / "私の小説")
    dialog.close()
    app.processEvents()


def test_open_project_starts_in_projects_folder(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    projects_parent = tmp_path / "Documents" / "LocalNovelTool" / "作品"
    calls = []
    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getExistingDirectory",
        lambda *args: calls.append(args) or "",
    )

    window = main_window_module.MainWindow()
    window.settings = QSettings(
        str(tmp_path / "settings-open.ini"), QSettings.Format.IniFormat
    )
    window._set_projects_parent(projects_parent)
    window.open_project()

    assert calls[0][2] == str(projects_parent)
    window.close()
    app.processEvents()


def test_projects_root_defaults_persists_and_resets(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    tutorial_parent = tmp_path / "Documents" / "LocalNovelTool"
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tutorial_parent),
    )
    settings_path = tmp_path / "settings-projects-root.ini"
    window = main_window_module.MainWindow()
    window.settings = QSettings(str(settings_path), QSettings.Format.IniFormat)

    default_root = tutorial_parent / "作品"
    assert window._projects_parent() == default_root

    custom_root = tmp_path / "NovelProjects"
    custom_root.mkdir()
    window._set_projects_parent(custom_root)
    reloaded = QSettings(str(settings_path), QSettings.Format.IniFormat)
    assert reloaded.value(main_window_module.PROJECTS_ROOT_KEY, "", str) == str(
        custom_root
    )
    window.settings = reloaded
    assert window._projects_parent() == custom_root

    dialog = main_window_module.SettingsDialog(custom_root, default_root)
    dialog.reset_projects_root()
    assert dialog.selected_root() == default_root
    dialog.close()
    window.close()
    app.processEvents()


def test_project_storage_settings_are_available_without_any_project(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    tutorial_parent = tmp_path / "missing" / "Documents" / "LocalNovelTool"
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tutorial_parent),
    )
    custom_root = tmp_path / "NovelProjects"
    custom_root.mkdir()

    class FakeSettingsDialog:
        def __init__(self, _current, _default, _parent, **_kwargs) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def selected_root(self) -> Path:
            return custom_root

        def content_font_size(self) -> int:
            return 18

    monkeypatch.setattr(main_window_module, "SettingsDialog", FakeSettingsDialog)
    window = main_window_module.MainWindow()
    window.settings = QSettings(
        str(tmp_path / "settings-no-project.ini"), QSettings.Format.IniFormat
    )

    assert window.api.project is None
    assert not tutorial_parent.exists()
    assert window.settings_action.isEnabled()
    window.settings_action.trigger()
    assert window._projects_parent() == custom_root
    assert window.content_font_size_spin.value() == 18
    assert window.api.project is None
    assert not tutorial_parent.exists()
    window.close()
    app.processEvents()


def test_new_project_uses_configured_root_without_moving_existing(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    old_root = tmp_path / "old" / "既存作品"
    old_root.parent.mkdir()
    CoreAPI().create_project(old_root.parent, old_root.name)
    custom_root = tmp_path / "new-root"
    custom_root.mkdir()

    captured = []

    class FakeNewProjectDialog:
        def __init__(self, projects_parent, _parent) -> None:
            captured.append(projects_parent)

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def project_title(self) -> str:
            return "新規作品"

    monkeypatch.setattr(main_window_module, "NewProjectDialog", FakeNewProjectDialog)
    window = main_window_module.MainWindow()
    window.settings = QSettings(
        str(tmp_path / "settings-custom.ini"), QSettings.Format.IniFormat
    )
    window._set_projects_parent(custom_root)

    window.new_project()

    assert captured == [custom_root]
    assert window.api.project is not None
    assert window.api.project.root == (custom_root / "新規作品").resolve()
    assert (old_root / "project.json").is_file()
    assert not (custom_root / "既存作品").exists()
    window.close()
    app.processEvents()


def test_configured_root_new_project_saves_and_reopens_body(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    class FakeNewProjectDialog:
        def __init__(self, projects_parent, _parent) -> None:
            assert projects_parent == configured_root

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def project_title(self) -> str:
            return "保存テスト"

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    monkeypatch.setattr(main_window_module, "NewProjectDialog", FakeNewProjectDialog)
    old_root = tmp_path / "old-root"
    old_root.mkdir()
    old_api = CoreAPI()
    old_project = old_api.create_project(old_root, "既存作品")
    old_chapter = old_api.create_chapter("既存章")
    old_api.create_episode(old_chapter.id, "既存話")
    old_episode = old_project.chapters[0].episodes[0]
    old_project.save_episode_body(old_episode.id, "既存本文")
    old_body = old_project.root / old_episode.body_file
    configured_root = tmp_path / "configured-root"
    configured_root.mkdir()

    window = main_window_module.MainWindow()
    window.settings = QSettings(
        str(tmp_path / "settings-save-regression.ini"), QSettings.Format.IniFormat
    )
    window.api.open_project(old_project.root)
    window._after_project_loaded()
    window._set_projects_parent(configured_root)
    window.new_project()

    project = window.api.project
    assert project is not None
    assert project.root == (configured_root / "保存テスト").resolve()
    assert window._projects_parent() == configured_root
    assert window.settings.value("last_project", "", str) == str(project.root)
    assert (project.root / "project.json").is_file()
    assert (project.root / "manuscript").is_dir()
    assert project.chapters == []
    assert window.current_episode_id is None
    assert window.editor_tab.editor.toPlainText() == ""
    assert window.editor_tab.editor.isReadOnly()
    assert window.note_tab.editor.toPlainText() == ""
    assert window.note_tab.editor.isReadOnly()
    window.editor_tab.editor.setFocus()
    QTest.keyClicks(window.editor_tab.editor, "must not be entered")
    assert window.editor_tab.editor.toPlainText() == ""

    reopened_empty = CoreAPI().open_project(project.root)
    assert reopened_empty.chapters == []

    responses = iter((("自由な章名", True), ("自由な話名", True)))
    monkeypatch.setattr(
        main_window_module.QInputDialog,
        "getText",
        lambda *_args, **_kwargs: next(responses),
    )
    window.add_chapter()
    assert [chapter.title for chapter in project.chapters] == ["自由な章名"]
    chapter = project.chapters[0]
    window.tree.setCurrentItem(window.tree.topLevelItem(0))
    window.add_episode()
    assert [item.title for item in chapter.episodes] == ["自由な話名"]
    episode = chapter.episodes[0]
    body_path = project.root / episode.body_file
    assert body_path.is_file()
    assert window.current_episode_id == episode.id
    assert not window.editor_tab.editor.isReadOnly()

    window.editor_tab.editor.setPlainText("SAVE_REGRESSION_TEST_20260816")
    assert window.manual_save()
    assert body_path.read_text(encoding="utf-8") == "SAVE_REGRESSION_TEST_20260816"

    window.editor_tab.editor.setPlainText("SAVE_REGRESSION_AUTOSAVE_20260816")
    window.editor_tab.timer.timeout.emit()
    assert body_path.read_text(encoding="utf-8") == "SAVE_REGRESSION_AUTOSAVE_20260816"

    reopened = CoreAPI().open_project(project.root)
    reopened_episode = reopened.chapters[0].episodes[0]
    assert reopened.load_episode_body(reopened_episode.id) == (
        "SAVE_REGRESSION_AUTOSAVE_20260816"
    )
    assert old_body.read_text(encoding="utf-8") == "既存本文"
    assert not (old_project.root / "manuscript" / body_path.name).exists()
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_default_root_new_project_is_empty_and_reopens(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    tutorial_parent = tmp_path / "Documents" / "LocalNovelTool"
    default_root = tutorial_parent / "作品"

    class FakeNewProjectDialog:
        def __init__(self, projects_parent, _parent) -> None:
            assert projects_parent == default_root

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def project_title(self) -> str:
            return "デフォルト保存テスト"

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tutorial_parent),
    )
    monkeypatch.setattr(main_window_module, "NewProjectDialog", FakeNewProjectDialog)
    window = main_window_module.MainWindow()
    window.settings = QSettings(
        str(tmp_path / "settings-default-save.ini"), QSettings.Format.IniFormat
    )
    window.new_project()
    project = window.api.project
    assert project is not None
    assert project.root == (default_root / "デフォルト保存テスト").resolve()
    assert project.chapters == []
    assert window.current_episode_id is None
    assert window.editor_tab.editor.toPlainText() == ""
    assert window.editor_tab.editor.isReadOnly()
    reopened = CoreAPI().open_project(project.root)
    assert reopened.chapters == []
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_planning_lists_emit_dragged_order() -> None:
    app = QApplication.instance() or QApplication([])
    first = SimpleNamespace(id="first", title="最初", point="2年前")
    second = SimpleNamespace(id="second", title="次", point="現在")

    plot_tab = PlotTab()
    plot_orders: list[list[str]] = []
    plot_tab.reorder_requested.connect(plot_orders.append)
    plot_tab.set_items([first, second], [])
    assert plot_tab.list.model().moveRow(QModelIndex(), 0, QModelIndex(), 2)
    assert plot_orders[-1] == ["second", "first"]

    timeline_tab = TimelineTab()
    timeline_orders: list[list[str]] = []
    timeline_tab.reorder_requested.connect(timeline_orders.append)
    timeline_tab.set_items([first, second])
    assert timeline_tab.list.model().moveRow(QModelIndex(), 0, QModelIndex(), 2)
    assert timeline_orders[-1] == ["second", "first"]
    app.processEvents()


def test_project_actions_follow_project_and_tree_selection(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    window = main_window_module.MainWindow()

    assert window.new_project_action.isEnabled()
    assert window.open_project_action.isEnabled()
    assert window.settings_action.isEnabled()
    for action in (
        window.toolbar_save_action,
        window.save_action,
        window.backup_action,
        window.open_folder_action,
        window.add_chapter_action,
        window.add_episode_action,
        window.rename_action,
        window.delete_action,
    ):
        assert not action.isEnabled()
    assert all(not window.tabs.isTabEnabled(index) for index in range(7))

    project = window.api.create_project(tmp_path, "空作品")
    window._after_project_loaded()
    assert window.add_chapter_action.isEnabled()
    assert window.toolbar_save_action.isEnabled()
    assert window.save_action.isEnabled()
    assert window.backup_action.isEnabled()
    assert window.open_folder_action.isEnabled()
    assert not window.add_episode_action.isEnabled()
    assert not window.rename_action.isEnabled()
    assert not window.delete_action.isEnabled()
    assert window.editor_tab.editor.isReadOnly()
    assert window.note_tab.editor.isReadOnly()
    assert all(window.tabs.isTabEnabled(index) for index in range(7))

    chapter = window.api.create_chapter("自由な章")
    window.refresh_tree()
    window.tree.setCurrentItem(window.tree.topLevelItem(0))
    app.processEvents()
    assert window.add_episode_action.isEnabled()
    assert window.rename_action.isEnabled()
    assert window.delete_action.isEnabled()
    assert window.editor_tab.editor.isReadOnly()
    assert all(window.tabs.isTabEnabled(index) for index in range(7))

    episode = window.api.create_episode(chapter.id, "自由な話")
    window.refresh_tree()
    window.tree.select_episode(episode.id)
    app.processEvents()
    assert not window.add_episode_action.isEnabled()
    assert window.rename_action.isEnabled()
    assert window.delete_action.isEnabled()
    assert not window.editor_tab.editor.isReadOnly()
    assert not window.note_tab.editor.isReadOnly()
    assert all(window.tabs.isTabEnabled(index) for index in range(7))

    chapter_item = window.tree.topLevelItem(0)
    for tab in (
        window.editor_tab,
        window.preview_tab,
        window.reference_tab,
        window.plot_tab,
        window.timeline_tab,
    ):
        window.tree.select_episode(episode.id)
        app.processEvents()
        window.tabs.setCurrentWidget(tab)
        window.tree.setCurrentItem(chapter_item)
        app.processEvents()
        assert window.tabs.currentWidget() is tab

    window.tabs.setCurrentWidget(window.preview_tab)
    window.tree.select_episode(episode.id)
    app.processEvents()
    assert window.current_episode_id == episode.id
    assert window.tabs.currentWidget() is window.preview_tab

    window.api.delete_episode(episode.id)
    window.current_episode_id = None
    window.editor_tab.set_text("")
    window.note_tab.set_text("")
    window.refresh_tree()
    assert window.editor_tab.editor.isReadOnly()
    assert window.note_tab.editor.isReadOnly()
    assert not window.add_episode_action.isEnabled()
    assert not window.rename_action.isEnabled()
    assert not window.delete_action.isEnabled()
    assert project.chapters[0].episodes == []
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_manual_backup_uses_default_external_root_and_reports_result(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    tutorial_parent = tmp_path / "Documents" / "LocalNovelTool"
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tutorial_parent),
    )
    project_parent = tmp_path / "projects"
    project_parent.mkdir()
    window = main_window_module.MainWindow()
    window.api.create_project(project_parent, "バックアップ対象")
    window._after_project_loaded()
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((title, text)),
    )
    window.create_backup()
    assert window.statusBar().currentMessage() == "バックアップ中..."
    assert not window.backup_action.isEnabled()
    first_thread = window._backup_thread
    window.create_backup()
    assert window._backup_thread is first_thread
    for _ in range(300):
        app.processEvents()
        if not window._backup_is_running():
            break
        QTest.qWait(10)
    assert not window._backup_is_running()

    backups = tutorial_parent / "Backups"
    generations = list(backups.rglob("project.json"))
    assert len(generations) == 1
    assert messages[0][0] == "バックアップ完了"
    assert str(generations[0].parent) in messages[0][1]

    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        backup_worker_module,
        "create_project_backup",
        lambda *_args: (_ for _ in ()).throw(OSError("書き込み不能")),
    )
    monkeypatch.setattr(
        main_window_module,
        "show_error",
        lambda _parent, title, text: errors.append((title, text)),
    )
    window.create_backup()
    for _ in range(300):
        app.processEvents()
        if not window._backup_is_running():
            break
        QTest.qWait(10)
    assert not window._backup_is_running()
    assert errors == [("バックアップ失敗", "書き込み不能")]
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_close_is_ignored_safely_while_backup_is_running(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    class CloseEvent:
        def __init__(self) -> None:
            self.ignored = False

        def ignore(self) -> None:
            self.ignored = True

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    tutorial_parent = tmp_path / "Documents" / "LocalNovelTool"
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tutorial_parent),
    )
    project_parent = tmp_path / "projects"
    project_parent.mkdir()
    window = main_window_module.MainWindow()
    window.api.create_project(project_parent, "実行中終了")
    window._after_project_loaded()
    started = threading.Event()
    release = threading.Event()
    original_backup = backup_worker_module.create_project_backup

    def slow_backup(project_root: Path, backups_root: Path) -> Path:
        started.set()
        assert release.wait(3)
        return original_backup(project_root, backups_root)

    monkeypatch.setattr(
        backup_worker_module, "create_project_backup", slow_backup
    )
    monkeypatch.setattr(
        main_window_module.QMessageBox, "information", lambda *_args: None
    )
    window.create_backup()
    for _ in range(100):
        app.processEvents()
        if started.is_set():
            break
        QTest.qWait(10)
    assert started.is_set()
    responsive: list[bool] = []
    QTimer.singleShot(0, lambda: responsive.append(True))
    app.processEvents()
    assert responsive == [True]

    event = CloseEvent()
    window.closeEvent(event)

    assert event.ignored
    assert window._backup_is_running()
    assert "バックアップ中です" in window.statusBar().currentMessage()
    release.set()
    for _ in range(300):
        app.processEvents()
        if not window._backup_is_running():
            break
        QTest.qWait(10)
    assert not window._backup_is_running()
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_manual_save_writes_body_and_keeps_autosave_active(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    window = main_window_module.MainWindow()
    project = window.api.create_project(tmp_path, "保存テスト")
    chapter = window.api.create_chapter("第一章")
    episode = window.api.create_episode(chapter.id, "第一話")
    window._after_project_loaded()
    window.open_episode(episode.id)

    window.editor_tab.editor.setPlainText("手動保存本文")
    assert window.editor_tab.timer.isActive()
    window.manual_save()

    assert project.read_text(episode.body_file) == "手動保存本文"
    assert window.statusBar().currentMessage() == "保存しました"
    assert window.save_action.shortcut().matches(
        QKeySequence("Ctrl+S")
    ) == QKeySequence.SequenceMatch.ExactMatch
    assert not window.editor_tab.timer.isActive()

    window.editor_tab.editor.setPlainText("手動保存本文・自動保存も有効")
    assert window.editor_tab.timer.isActive()
    window.editor_tab.timer.timeout.emit()
    assert project.read_text(episode.body_file) == "手動保存本文・自動保存も有効"
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_failed_manual_save_preserves_existing_body(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    window = main_window_module.MainWindow()
    project = window.api.create_project(tmp_path, "保存失敗テスト")
    chapter = window.api.create_chapter("第一章")
    episode = window.api.create_episode(chapter.id, "第一話")
    project.write_text(episode.body_file, "保存済み本文")
    window._after_project_loaded()
    window.open_episode(episode.id)
    window.editor_tab.editor.setPlainText("失敗する本文")
    monkeypatch.setattr(
        window.api,
        "save_episode_body",
        lambda *_args: (_ for _ in ()).throw(OSError("書き込み失敗")),
    )
    errors = []
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "critical",
        lambda *_args: errors.append(_args[2]),
    )

    window.manual_save()

    assert project.read_text(episode.body_file) == "保存済み本文"
    assert errors == ["書き込み失敗"]
    assert window._has_unsaved_changes()
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


class FakeCloseEvent:
    def __init__(self) -> None:
        self.accepted = False
        self.ignored = False

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


def test_dirty_clears_after_successful_auto_and_manual_save_and_resets_on_open(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    window = main_window_module.MainWindow()
    project = window.api.create_project(tmp_path, "終了確認作品")
    chapter = window.api.create_chapter("第一章")
    episode = window.api.create_episode(chapter.id, "第一話")
    window._after_project_loaded()
    window.open_episode(episode.id)

    assert not window._has_unsaved_changes()
    unopened_event = FakeCloseEvent()
    monkeypatch.setattr(
        window,
        "_confirm_save_on_close",
        lambda: (_ for _ in ()).throw(AssertionError("確認が表示されました")),
    )
    window.closeEvent(unopened_event)
    assert unopened_event.accepted

    window.editor_tab.editor.setPlainText("本文変更")
    assert window._has_unsaved_changes()
    assert window.editor_tab.timer.isActive()
    window.editor_tab.timer.timeout.emit()
    assert project.read_text(episode.body_file) == "本文変更"
    assert not window._has_unsaved_changes()

    window.editor_tab.editor.setPlainText("手動保存する本文")
    assert window._has_unsaved_changes()
    assert window.manual_save()
    assert not window._has_unsaved_changes()
    saved_event = FakeCloseEvent()
    window.closeEvent(saved_event)
    assert saved_event.accepted and not saved_event.ignored

    window.note_tab.editor.setPlainText("話メモ変更")
    assert window._has_unsaved_changes()
    window.note_tab.timer.timeout.emit()
    assert not window._has_unsaved_changes()

    monkeypatch.setattr(
        main_window_module.QInputDialog,
        "getText",
        lambda *_args, **_kwargs: ("追加章", True),
    )
    window.add_chapter()
    assert not window._has_unsaved_changes()

    other_parent = tmp_path / "other"
    other_parent.mkdir()
    other = CoreAPI().create_project(other_parent, "別作品")
    window._load_project(other.root)
    assert not window._has_unsaved_changes()
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_close_save_writes_official_project_and_accepts(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    window = main_window_module.MainWindow()
    project = window.api.create_project(tmp_path, "終了保存作品")
    chapter = window.api.create_chapter("第一章")
    episode = window.api.create_episode(chapter.id, "第一話")
    window._after_project_loaded()
    window.open_episode(episode.id)
    window.editor_tab.editor.setPlainText("終了時に保存")
    monkeypatch.setattr(window, "_confirm_save_on_close", lambda: True)
    event = FakeCloseEvent()

    window.closeEvent(event)

    assert event.accepted and not event.ignored
    assert project.read_text(episode.body_file) == "終了時に保存"
    window._dirty_sources.clear()
    window.close()
    app.processEvents()


def test_close_cancel_and_save_failure_keep_window_open(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def setHtml(self, _rendered: str) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    monkeypatch.setattr(
        main_window_module.MainWindow, "_try_open_initial_project", lambda self: None
    )
    window = main_window_module.MainWindow()
    window.api.create_project(tmp_path, "終了中止作品")
    window._after_project_loaded()
    window._dirty_sources.add("body")

    save_calls = []
    monkeypatch.setattr(window, "manual_save", lambda: save_calls.append(True) or True)
    monkeypatch.setattr(window, "_confirm_save_on_close", lambda: False)
    cancelled = FakeCloseEvent()
    window.closeEvent(cancelled)
    assert cancelled.ignored and not cancelled.accepted
    assert save_calls == []

    monkeypatch.setattr(window, "_confirm_save_on_close", lambda: True)
    monkeypatch.setattr(window, "manual_save", lambda: False)
    failed = FakeCloseEvent()
    window.closeEvent(failed)
    assert failed.ignored and not failed.accepted

    window._dirty_sources.clear()
    window.close()
    app.processEvents()
