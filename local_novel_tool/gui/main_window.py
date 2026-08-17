from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QToolBar,
)

from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.project import ProjectError
from local_novel_tool.version import APP_NAME, APP_VERSION, AUTHOR_NAME
from .editor_tab import TextEditorTab
from .preview_tab import PreviewTab
from .project_tree import ProjectTree
from .reference_tab import ReferenceTab
from .search_tab import SearchTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 760)
        self.api = CoreAPI()
        self.current_episode_id: str | None = None
        config_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
        config_dir.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(str(config_dir / "settings.ini"), QSettings.Format.IniFormat)

        self.tree = ProjectTree()
        self.tabs = QTabWidget()
        self.editor_tab = TextEditorTab(show_ruby_button=True)
        self.preview_tab = PreviewTab()
        self.note_tab = TextEditorTab()
        self.search_tab = SearchTab()
        self.reference_tab = ReferenceTab()
        self.tabs.addTab(self.editor_tab, "本文")
        self.tabs.addTab(self.preview_tab, "プレビュー")
        self.tabs.addTab(self.note_tab, "話メモ")
        self.tabs.addTab(self.search_tab, "文章検索")
        self.tabs.addTab(self.reference_tab, "資料")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 940])
        self.setCentralWidget(splitter)

        self._build_toolbar()
        self._build_menu()
        self._connect()
        self.statusBar().showMessage("作品を新規作成するか開いてください。")
        self._try_open_last_project()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("メイン")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        actions = [
            ("新規作品", self.new_project),
            ("開く", self.open_project),
            ("章追加", self.add_chapter),
            ("話追加", self.add_episode),
            ("名前変更", self.rename_selected),
            ("削除", self.delete_selected),
        ]
        for label, handler in actions:
            action = QAction(label, self)
            action.triggered.connect(handler)
            toolbar.addAction(action)

    def _build_menu(self) -> None:
        help_menu = self.menuBar().addMenu("ヘルプ")
        about_action = QAction("このソフトについて", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            f"{APP_NAME} について",
            f"{APP_NAME} {APP_VERSION}\n\n"
            f"Copyright (c) 2026 {AUTHOR_NAME}\n\n"
            "Built with Python / Qt for Python (PySide6)\n"
            "完全ローカルで動作します。",
        )

    def _connect(self) -> None:
        self.tree.episode_selected.connect(self.open_episode)
        self.tree.structure_changed.connect(self.apply_tree_order)
        self.editor_tab.save_requested.connect(self.save_current_body)
        self.note_tab.save_requested.connect(self.save_current_note)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.search_tab.search_requested.connect(self.perform_search)
        self.search_tab.result_activated.connect(self.open_search_result)
        self.reference_tab.open_requested.connect(self.open_reference)
        self.reference_tab.create_requested.connect(self.create_reference)
        self.reference_tab.rename_requested.connect(self.rename_reference)
        self.reference_tab.delete_requested.connect(self.delete_reference)
        self.reference_tab.save_requested.connect(self.save_reference)

    def _try_open_last_project(self) -> None:
        last = self.settings.value("last_project", "", str)
        if last and (Path(last) / "project.json").exists():
            try:
                self._load_project(Path(last))
            except Exception:
                pass

    def _flush_editors(self) -> None:
        self.editor_tab.flush()
        self.note_tab.flush()
        self.reference_tab.flush()

    def new_project(self) -> None:
        self._flush_editors()
        title, ok = QInputDialog.getText(self, "新規作品", "作品名")
        if not ok or not title.strip():
            return
        folder = QFileDialog.getExistingDirectory(self, "保存先の親フォルダを選択")
        if not folder:
            return
        try:
            self.api.create_project(Path(folder), title.strip())
            self._after_project_loaded()
        except ProjectError as exc:
            QMessageBox.warning(self, "作成できません", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "作成失敗", str(exc))

    def open_project(self) -> None:
        self._flush_editors()
        folder = QFileDialog.getExistingDirectory(self, "作品フォルダを開く")
        if folder:
            self._load_project(Path(folder))

    def _load_project(self, root: Path) -> None:
        try:
            self.api.open_project(root)
            self._after_project_loaded()
        except Exception as exc:
            QMessageBox.critical(self, "読込失敗", str(exc))

    def _after_project_loaded(self) -> None:
        project = self.api.project
        if not project:
            return
        self.current_episode_id = None
        self.tree.rebuild(project.chapters)
        self.refresh_references()
        self.setWindowTitle(f"{project.title} - {APP_NAME}")
        self.settings.setValue("last_project", str(project.root))
        self.statusBar().showMessage(str(project.root))
        if project.chapters and project.chapters[0].episodes:
            self.tree.select_episode(project.chapters[0].episodes[0].id)

    def refresh_tree(self) -> None:
        if self.api.project:
            selected = self.current_episode_id
            self.tree.rebuild(self.api.chapters())
            if selected:
                self.tree.select_episode(selected)

    def refresh_references(self) -> None:
        if self.api.project:
            self.reference_tab.set_references(self.api.references(), self.api.recent_references())

    def add_chapter(self) -> None:
        if not self.api.project:
            return
        title, ok = QInputDialog.getText(self, "章追加", "章名")
        if ok:
            self.api.create_chapter(title)
            self.refresh_tree()

    def add_episode(self) -> None:
        if not self.api.project:
            return
        kind, selected_id = self.tree.selected_identity()
        chapter_id = None
        if kind == "chapter":
            chapter_id = selected_id
        elif kind == "episode" and selected_id:
            chapter_id = self.api.project.find_episode_parent(selected_id).id
        elif self.api.chapters():
            chapter_id = self.api.chapters()[0].id
        if chapter_id is None:
            chapter = self.api.create_chapter("第一章")
            chapter_id = chapter.id
        title, ok = QInputDialog.getText(self, "話追加", "話タイトル")
        if ok:
            episode = self.api.create_episode(chapter_id, title)
            self.refresh_tree()
            self.tree.select_episode(episode.id)

    def rename_selected(self) -> None:
        if not self.api.project:
            return
        kind, selected_id = self.tree.selected_identity()
        if not kind or not selected_id:
            return
        title, ok = QInputDialog.getText(self, "名前変更", "新しい名前")
        if not ok or not title.strip():
            return
        if kind == "chapter":
            self.api.rename_chapter(selected_id, title)
        else:
            self.api.rename_episode(selected_id, title)
        self.refresh_tree()

    def delete_selected(self) -> None:
        if not self.api.project:
            return
        kind, selected_id = self.tree.selected_identity()
        if not kind or not selected_id:
            return
        message = "章と中の話をすべて削除しますか？" if kind == "chapter" else "この話を削除しますか？"
        if QMessageBox.question(self, "削除", message) != QMessageBox.StandardButton.Yes:
            return
        if kind == "chapter":
            self.api.delete_chapter(selected_id)
        else:
            self.api.delete_episode(selected_id)
            if self.current_episode_id == selected_id:
                self.current_episode_id = None
                self.editor_tab.set_text("")
                self.note_tab.set_text("")
        self.refresh_tree()

    def open_episode(self, episode_id: str) -> None:
        if not self.api.project or episode_id == self.current_episode_id:
            return
        self._flush_editors()
        self.current_episode_id = episode_id
        self.editor_tab.set_text(self.api.load_episode_body(episode_id))
        self.note_tab.set_text(self.api.load_episode_note(episode_id))
        episode = self.api.project.get_episode(episode_id)
        self.statusBar().showMessage(episode.title)
        if self.tabs.currentWidget() == self.preview_tab:
            self.preview_tab.set_source_text(self.editor_tab.editor.toPlainText())

    def save_current_body(self, text: str) -> None:
        if self.current_episode_id and self.api.project:
            self.api.save_episode_body(self.current_episode_id, text)
            if self.tabs.currentWidget() == self.preview_tab:
                self.preview_tab.set_source_text(text)

    def save_current_note(self, text: str) -> None:
        if self.current_episode_id and self.api.project:
            self.api.save_episode_note(self.current_episode_id, text)

    def _tab_changed(self, _index: int) -> None:
        if self.tabs.currentWidget() == self.preview_tab:
            self.preview_tab.set_source_text(self.editor_tab.editor.toPlainText())
        elif self.tabs.currentWidget() == self.reference_tab:
            self.refresh_references()

    def apply_tree_order(self) -> None:
        if not self.api.project:
            return
        order = self.tree.structure_order()
        if order is None:
            self.refresh_tree()
            return
        try:
            self.api.reorder_structure(order)
            self.refresh_tree()
        except ProjectError as exc:
            QMessageBox.warning(self, "移動できません", str(exc))
            self.refresh_tree()

    def perform_search(self, query: str) -> None:
        if self.api.project:
            self.search_tab.set_results(self.api.search(query))

    def open_search_result(self, result) -> None:
        if result.kind in ("episode", "episode_note"):
            self.tree.select_episode(result.source_id)
            tab = self.editor_tab if result.kind == "episode" else self.note_tab
            self.tabs.setCurrentWidget(tab)
            tab.go_to_line(result.line)
        elif result.kind == "reference":
            self.tabs.setCurrentWidget(self.reference_tab)
            self.open_reference(result.source_id)
            self.reference_tab.editor.setFocus()

    def open_reference(self, reference_id: str) -> None:
        if not self.api.project:
            return
        self.reference_tab.flush()
        ref = self.api.project.get_reference(reference_id)
        text = self.api.load_reference(reference_id)
        self.reference_tab.show_reference(ref, text)
        self.refresh_references()

    def create_reference(self, category: str, title: str) -> None:
        if not self.api.project:
            return
        ref = self.api.create_reference(category, title)
        self.refresh_references()
        self.open_reference(ref.id)

    def rename_reference(self, reference_id: str, title: str) -> None:
        self.api.rename_reference(reference_id, title)
        self.refresh_references()
        self.open_reference(reference_id)

    def delete_reference(self, reference_id: str) -> None:
        self.api.delete_reference(reference_id)
        self.refresh_references()

    def save_reference(self, reference_id: str, text: str) -> None:
        self.api.save_reference(reference_id, text)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._flush_editors()
        self.settings.sync()
        event.accept()
