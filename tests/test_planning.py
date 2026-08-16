from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QModelIndex, QSettings
from PySide6.QtWidgets import QApplication, QDialog, QWidget

import local_novel_tool.gui.main_window as main_window_module
import local_novel_tool.gui.preview_tab as preview_module
from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.models import SearchResult
from local_novel_tool.core.project import REFERENCE_CATEGORIES
from local_novel_tool.gui.plot_tab import PlotTab
from local_novel_tool.gui.timeline_tab import TimelineTab


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

    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "question",
        lambda *_args, **_kwargs: main_window_module.QMessageBox.StandardButton.No,
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
        main_window_module.QMessageBox,
        "question",
        lambda *_args, **_kwargs: main_window_module.QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        main_window_module.MainWindow,
        "_tutorial_parent",
        staticmethod(lambda: tmp_path / "ドキュメント"),
    )
    monkeypatch.setattr(
        main_window_module,
        "recreate_tutorial_project",
        lambda _api, parent: recreated.append(parent),
    )
    window.recreate_tutorial()
    assert recreated == [tmp_path / "ドキュメント"]
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
