from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
)

from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.project import ProjectError
from local_novel_tool.version import APP_NAME, APP_VERSION, AUTHOR_NAME
from .editor_tab import TextEditorTab
from .plot_tab import PlotTab
from .preview_tab import PreviewTab
from .project_tree import ProjectTree
from .reference_tab import ReferenceTab
from .sample_project import (
    SAMPLE_INITIALIZED_KEY,
    SAMPLE_PROJECT_TITLE,
    archive_tutorial_project,
    initialize_sample_project,
    recreate_tutorial_project,
    tutorial_matches_bundled,
)
from .search_tab import SearchTab
from .timeline_tab import TimelineTab


PROJECTS_ROOT_KEY = "projects_root"


class NewProjectDialog(QDialog):
    """Collect a project title while showing its fixed destination."""

    def __init__(self, projects_parent: Path, parent=None) -> None:
        super().__init__(parent)
        self.projects_parent = projects_parent
        self.setWindowTitle("新規作品")
        self.title_edit = QLineEdit(self)
        self.destination_label = QLabel(self)
        self.destination_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.destination_label.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QFormLayout(self)
        layout.addRow("作品名:", self.title_edit)
        layout.addRow("保存先:", self.destination_label)
        layout.addRow(buttons)
        self.title_edit.textChanged.connect(self._update_destination)
        self._update_destination("")

    def _update_destination(self, title: str) -> None:
        self.destination_label.setText(str(self.projects_parent / title.strip()))

    def project_title(self) -> str:
        return self.title_edit.text().strip()


class SettingsDialog(QDialog):
    def __init__(self, projects_root: Path, default_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.default_root = default_root
        self.setWindowTitle("設定")

        self.path_edit = QLineEdit(str(projects_root), self)
        self.path_edit.setReadOnly(True)
        select_button = QPushButton("選択...", self)
        reset_button = QPushButton("デフォルトに戻す", self)
        select_button.clicked.connect(self.select_projects_root)
        reset_button.clicked.connect(self.reset_projects_root)

        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(select_button)
        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        reset_row.addWidget(reset_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("作品の保存フォルダ", self))
        layout.addLayout(path_row)
        layout.addLayout(reset_row)
        layout.addWidget(buttons)

    def selected_root(self) -> Path:
        return Path(self.path_edit.text())

    def select_projects_root(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "作品の保存フォルダを選択", self.path_edit.text()
        )
        if not folder:
            return
        path = Path(folder)
        if not path.is_dir() or not os.access(path, os.W_OK):
            QMessageBox.warning(
                self, "設定できません", "書き込み可能なフォルダを選択してください。"
            )
            return
        self.path_edit.setText(str(path))

    def reset_projects_root(self) -> None:
        self.path_edit.setText(str(self.default_root))

    def accept(self) -> None:
        path = self.selected_root()
        if not path.is_absolute():
            QMessageBox.warning(self, "設定できません", "有効な保存先を選択してください。")
            return
        if path != self.default_root and (
            not path.is_dir() or not os.access(path, os.W_OK)
        ):
            QMessageBox.warning(
                self, "設定できません", "書き込み可能なフォルダを選択してください。"
            )
            return
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 760)
        self.api = CoreAPI()
        self.current_episode_id: str | None = None
        self._dirty_sources: set[str] = set()
        config_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
        config_dir.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(str(config_dir / "settings.ini"), QSettings.Format.IniFormat)

        self.tree = ProjectTree()
        self.tabs = QTabWidget()
        self.tabs.tabBar().setStyleSheet(
            "QTabBar::tab { min-height: 24px; padding: 6px 14px; font-size: 10pt; }"
            "QTabBar::tab:selected { font-weight: bold; background: palette(base); "
            "border: 1px solid palette(mid); border-bottom: 2px solid palette(highlight); }"
        )
        self.tabs.tabBar().setUsesScrollButtons(True)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.editor_tab = TextEditorTab(show_ruby_button=True)
        self.preview_tab = PreviewTab()
        self.note_tab = TextEditorTab()
        self.plot_tab = PlotTab()
        self.timeline_tab = TimelineTab()
        self.search_tab = SearchTab()
        self.reference_tab = ReferenceTab()
        self.tabs.addTab(self.editor_tab, "本文")
        self.tabs.addTab(self.preview_tab, "プレビュー")
        self.tabs.addTab(self.note_tab, "話メモ")
        self.tabs.addTab(self.plot_tab, "展開")
        self.tabs.addTab(self.timeline_tab, "時系列")
        self.tabs.addTab(self.search_tab, "文章検索")
        self.tabs.addTab(self.reference_tab, "資料")
        self._set_episode_editors_enabled(False)

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
        self._try_open_initial_project()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("メイン")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        actions = [
            ("新規作品", self.new_project),
            ("開く", self.open_project),
            ("保存", self.manual_save),
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
        file_menu = self.menuBar().addMenu("ファイル")
        save_action = QAction("保存", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.manual_save)
        file_menu.addAction(save_action)
        self.save_action = save_action
        file_menu.addSeparator()
        self.open_folder_action = QAction("作品フォルダを開く", self)
        self.open_folder_action.setEnabled(False)
        self.open_folder_action.triggered.connect(self.open_project_folder)
        file_menu.addAction(self.open_folder_action)
        file_menu.addSeparator()
        self.settings_action = QAction("設定...", self)
        self.settings_action.setEnabled(True)
        self.settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(self.settings_action)

        help_menu = self.menuBar().addMenu("ヘルプ")
        tutorial_action = QAction("チュートリアルを再作成", self)
        tutorial_action.triggered.connect(self.recreate_tutorial)
        help_menu.addAction(tutorial_action)
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
        self.plot_tab.open_requested.connect(self.open_plot_item)
        self.plot_tab.create_requested.connect(self.create_plot_item)
        self.plot_tab.rename_requested.connect(self.rename_plot_item)
        self.plot_tab.delete_requested.connect(self.delete_plot_item)
        self.plot_tab.save_requested.connect(self.save_plot_item)
        self.plot_tab.reorder_requested.connect(self.reorder_plot_items)
        self.timeline_tab.open_requested.connect(self.open_timeline_item)
        self.timeline_tab.create_requested.connect(self.create_timeline_item)
        self.timeline_tab.delete_requested.connect(self.delete_timeline_item)
        self.timeline_tab.save_requested.connect(self.save_timeline_item)
        self.timeline_tab.reorder_requested.connect(self.reorder_timeline_items)
        self.editor_tab.editor.textChanged.connect(
            lambda: self._mark_dirty(
                "body",
                self.current_episode_id is not None and not self.editor_tab._loading
            )
        )
        self.note_tab.editor.textChanged.connect(
            lambda: self._mark_dirty(
                "note",
                self.current_episode_id is not None and not self.note_tab._loading
            )
        )
        self.reference_tab.editor.textChanged.connect(
            lambda: self._mark_dirty(
                "reference",
                self.reference_tab.current_id is not None
                and not self.reference_tab._loading
            )
        )
        for signal in (
            self.plot_tab.title.textChanged,
            self.plot_tab.content.textChanged,
            self.plot_tab.chapter.currentIndexChanged,
            self.plot_tab.episode.currentIndexChanged,
        ):
            signal.connect(
                lambda *_args: self._mark_dirty(
                    "plot",
                    self.plot_tab.current_id is not None
                    and not self.plot_tab._loading
                    and not self.plot_tab._rebuilding
                )
            )
        for signal in (
            self.timeline_tab.point.textChanged,
            self.timeline_tab.title.textChanged,
            self.timeline_tab.content.textChanged,
        ):
            signal.connect(
                lambda *_args: self._mark_dirty(
                    "timeline",
                    self.timeline_tab.current_id is not None
                    and not self.timeline_tab._loading
                    and not self.timeline_tab._rebuilding
                )
            )

    def _mark_dirty(self, source: str, changed: bool = True) -> None:
        if changed and self.api.project:
            self._dirty_sources.add(source)

    def _mark_saved(self, source: str) -> None:
        self._dirty_sources.discard(source)

    def _has_unsaved_changes(self) -> bool:
        return bool(self._dirty_sources)

    def _try_open_last_project(self) -> None:
        last = self.settings.value("last_project", "", str)
        if last and (Path(last) / "project.json").exists():
            try:
                self._load_project(Path(last))
            except Exception:
                pass

    def _try_open_initial_project(self) -> None:
        try:
            sample = initialize_sample_project(
                self.api, self.settings, self._tutorial_parent()
            )
        except Exception as exc:
            QMessageBox.warning(self, "サンプル作成失敗", str(exc))
        else:
            if sample is not None:
                self._after_project_loaded()
                return
        self._try_open_last_project()

    @staticmethod
    def _tutorial_parent() -> Path:
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        if not documents:
            raise RuntimeError("ドキュメントフォルダが見つかりません。")
        return Path(documents) / "LocalNovelTool"

    @classmethod
    def _default_projects_parent(cls) -> Path:
        return cls._tutorial_parent() / "作品"

    def _projects_parent(self) -> Path:
        configured = self.settings.value(PROJECTS_ROOT_KEY, "", str).strip()
        return Path(configured) if configured else self._default_projects_parent()

    def _set_projects_parent(self, path: Path) -> None:
        self.settings.setValue(PROJECTS_ROOT_KEY, str(path))
        self.settings.sync()

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self._projects_parent(), self._default_projects_parent(), self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._set_projects_parent(dialog.selected_root())

    def recreate_tutorial(self) -> None:
        tutorial_root = self._tutorial_parent() / SAMPLE_PROJECT_TITLE
        choice = "recreate"
        if tutorial_root.exists():
            if tutorial_matches_bundled(tutorial_root):
                choice = (
                    "recreate"
                    if self._confirm_recreate_current_tutorial()
                    else "cancel"
                )
            else:
                choice = self._tutorial_recreation_choice()
        if choice == "cancel":
            return

        current = self.api.project
        tutorial_is_current = bool(
            current and current.root.resolve() == tutorial_root.resolve()
        )
        if tutorial_is_current:
            self._flush_editors()

        archived = None
        if choice == "archive":
            try:
                archived = archive_tutorial_project(
                    tutorial_root, self._projects_parent()
                )
            except Exception as exc:
                QMessageBox.critical(self, "退避失敗", str(exc))
                return

        load_recreated = current is None or tutorial_is_current
        recreate_api = self.api if load_recreated else CoreAPI()
        try:
            recreate_tutorial_project(recreate_api, self._tutorial_parent())
            self.settings.setValue(SAMPLE_INITIALIZED_KEY, True)
            self.settings.sync()
            if load_recreated:
                self._after_project_loaded()
            if archived:
                self.statusBar().showMessage(f"退避先: {archived}")
        except Exception as exc:
            QMessageBox.critical(self, "再作成失敗", str(exc))

    def _confirm_recreate_current_tutorial(self) -> bool:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Question)
        message.setWindowTitle("チュートリアルを再作成")
        message.setText("現在のチュートリアルはすでに最新の初期状態です。")
        message.setInformativeText("再作成しますか？")
        message.addButton("再作成", QMessageBox.ButtonRole.AcceptRole)
        cancel_button = message.addButton(
            "キャンセル", QMessageBox.ButtonRole.RejectRole
        )
        message.setDefaultButton(cancel_button)
        message.exec()
        clicked = message.clickedButton()
        return bool(
            clicked is not None
            and message.buttonRole(clicked) == QMessageBox.ButtonRole.AcceptRole
        )

    def _tutorial_recreation_choice(self) -> str:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("チュートリアルを再作成")
        message.setText("チュートリアルを初期状態に戻します。")
        message.setInformativeText(
            "現在のチュートリアルに書いた内容は失われます。"
        )
        archive_button = message.addButton(
            "作品として保存してから再作成",
            QMessageBox.ButtonRole.AcceptRole,
        )
        recreate_button = message.addButton(
            "そのまま再作成",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = message.addButton(
            "キャンセル", QMessageBox.ButtonRole.RejectRole
        )
        message.setDefaultButton(cancel_button)
        message.exec()
        clicked = message.clickedButton()
        role = message.buttonRole(clicked) if clicked is not None else None
        return self._tutorial_choice_for_role(role)

    @staticmethod
    def _tutorial_choice_for_role(role) -> str:
        if role == QMessageBox.ButtonRole.AcceptRole:
            return "archive"
        if role == QMessageBox.ButtonRole.DestructiveRole:
            return "recreate"
        return "cancel"

    def _flush_editors(self) -> None:
        self.editor_tab.flush()
        self.note_tab.flush()
        self.reference_tab.flush()
        self.plot_tab.flush()
        self.timeline_tab.flush()

    def manual_save(self) -> bool:
        if not self.api.project:
            return True
        try:
            if self.current_episode_id:
                self.save_current_body(self.editor_tab.editor.toPlainText())
                self.save_current_note(self.note_tab.editor.toPlainText())
            if self.reference_tab.current_id:
                self.save_reference(
                    self.reference_tab.current_id,
                    self.reference_tab.editor.toPlainText(),
                )
            if self.plot_tab.current_id:
                self.save_plot_item(
                    self.plot_tab.current_id,
                    self.plot_tab.title.text(),
                    self.plot_tab.content.toPlainText(),
                    self.plot_tab.chapter.currentData(),
                    self.plot_tab.episode.currentData(),
                )
            if self.timeline_tab.current_id:
                self.save_timeline_item(
                    self.timeline_tab.current_id,
                    self.timeline_tab.point.text(),
                    self.timeline_tab.title.text(),
                    self.timeline_tab.content.toPlainText(),
                )
        except Exception as exc:
            QMessageBox.critical(self, "保存失敗", str(exc))
            return False
        self.editor_tab.mark_saved()
        self.note_tab.mark_saved()
        self.reference_tab.timer.stop()
        self.plot_tab.timer.stop()
        self.timeline_tab.timer.stop()
        self._dirty_sources.clear()
        self.statusBar().showMessage("保存しました")
        return True

    def new_project(self) -> None:
        self._flush_editors()
        projects_parent = self._projects_parent()
        dialog = NewProjectDialog(projects_parent, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        title = dialog.project_title()
        if not title:
            return
        try:
            if not projects_parent.is_absolute():
                raise ProjectError("作品の保存フォルダが無効です。設定を確認してください。")
            projects_parent.mkdir(parents=True, exist_ok=True)
            if not projects_parent.is_dir() or not os.access(projects_parent, os.W_OK):
                raise ProjectError(
                    "作品の保存フォルダへ書き込めません。設定を確認してください。"
                )
            self.api.create_project(projects_parent, title)
            self._after_project_loaded()
        except ProjectError as exc:
            QMessageBox.warning(self, "作成できません", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "作成失敗", str(exc))

    def open_project(self) -> None:
        self._flush_editors()
        folder = QFileDialog.getExistingDirectory(
            self, "作品フォルダを開く", str(self._projects_parent())
        )
        if folder:
            self._load_project(Path(folder))

    def open_project_folder(self) -> None:
        if self.api.project:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.api.project.root)))

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
        self._dirty_sources.clear()
        self.editor_tab.set_text("")
        self.note_tab.set_text("")
        self.preview_tab.set_source_text("")
        self._set_episode_editors_enabled(False)
        self.tree.rebuild(project.chapters)
        self.refresh_references()
        self.refresh_planning()
        self.setWindowTitle(f"{project.title} - {APP_NAME}")
        self.open_folder_action.setEnabled(True)
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

    def refresh_planning(self) -> None:
        if self.api.project:
            self.plot_tab.set_items(self.api.plot_items(), self.api.chapters())
            self.timeline_tab.set_items(self.api.timeline_items())

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
            QMessageBox.information(
                self, "話追加", "先に章を追加してください。"
            )
            return
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
        clear_episode = bool(
            self.current_episode_id
            and (
                (kind == "episode" and self.current_episode_id == selected_id)
                or (
                    kind == "chapter"
                    and any(
                        episode.id == self.current_episode_id
                        for episode in self.api.project.get_chapter(selected_id).episodes
                    )
                )
            )
        )
        if kind == "chapter":
            self.api.delete_chapter(selected_id)
        else:
            self.api.delete_episode(selected_id)
        if clear_episode:
            self.current_episode_id = None
            self.editor_tab.set_text("")
            self.note_tab.set_text("")
            self.preview_tab.set_source_text("")
            self._set_episode_editors_enabled(False)
        self.refresh_tree()

    def open_episode(self, episode_id: str) -> None:
        if not self.api.project or episode_id == self.current_episode_id:
            return
        self._flush_editors()
        self.current_episode_id = episode_id
        self._set_episode_editors_enabled(True)
        self.editor_tab.set_text(self.api.load_episode_body(episode_id))
        self.note_tab.set_text(self.api.load_episode_note(episode_id))
        episode = self.api.project.get_episode(episode_id)
        self.statusBar().showMessage(episode.title)
        if self.tabs.currentWidget() == self.preview_tab:
            self.preview_tab.set_source_text(self.editor_tab.editor.toPlainText())

    def _set_episode_editors_enabled(self, enabled: bool) -> None:
        self.editor_tab.editor.setReadOnly(not enabled)
        self.note_tab.editor.setReadOnly(not enabled)
        message = "" if enabled else "話を追加すると本文を編集できます"
        self.editor_tab.editor.setPlaceholderText(message)
        self.note_tab.editor.setPlaceholderText(message)

    def save_current_body(self, text: str) -> None:
        if self.current_episode_id and self.api.project:
            self.api.save_episode_body(self.current_episode_id, text)
            self._mark_saved("body")
            if self.tabs.currentWidget() == self.preview_tab:
                self.preview_tab.set_source_text(text)

    def save_current_note(self, text: str) -> None:
        if self.current_episode_id and self.api.project:
            self.api.save_episode_note(self.current_episode_id, text)
            self._mark_saved("note")

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
        elif result.kind == "plot":
            self.tabs.setCurrentWidget(self.plot_tab)
            self.open_plot_item(result.source_id)
            self.plot_tab.content.setFocus()
        elif result.kind == "timeline":
            self.tabs.setCurrentWidget(self.timeline_tab)
            self.open_timeline_item(result.source_id)
            self.timeline_tab.content.setFocus()

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
        self._mark_saved("reference")

    def open_plot_item(self, plot_id: str) -> None:
        if self.api.project:
            self.plot_tab.flush()
            self.plot_tab.show_item(self.api.project.get_plot_item(plot_id))

    def create_plot_item(self, title: str) -> None:
        if self.api.project:
            item = self.api.create_plot_item(title)
            self.refresh_planning()
            self.plot_tab.select_item(item.id)

    def rename_plot_item(self, plot_id: str, title: str) -> None:
        if not self.api.project:
            return
        item = self.api.project.get_plot_item(plot_id)
        self.api.update_plot_item(
            plot_id, title, item.content, item.chapter_id, item.episode_id
        )
        self.refresh_planning()
        self.plot_tab.select_item(plot_id)

    def delete_plot_item(self, plot_id: str) -> None:
        if self.api.project:
            self.api.delete_plot_item(plot_id)
            self.refresh_planning()

    def save_plot_item(
        self,
        plot_id: str,
        title: str,
        content: str,
        chapter_id,
        episode_id,
    ) -> None:
        if self.api.project:
            self.api.update_plot_item(
                plot_id, title, content, chapter_id, episode_id
            )
            saved = self.api.project.get_plot_item(plot_id)
            self.plot_tab.update_item_label(plot_id, saved.title)
            self._mark_saved("plot")

    def reorder_plot_items(self, ordered_ids: list[str]) -> None:
        if self.api.project:
            self.api.reorder_plot_items(ordered_ids)

    def open_timeline_item(self, timeline_id: str) -> None:
        if self.api.project:
            self.timeline_tab.flush()
            self.timeline_tab.show_item(
                self.api.project.get_timeline_item(timeline_id)
            )

    def create_timeline_item(self, point: str, title: str) -> None:
        if self.api.project:
            item = self.api.create_timeline_item(point, title)
            self.refresh_planning()
            self.timeline_tab.select_item(item.id)

    def delete_timeline_item(self, timeline_id: str) -> None:
        if self.api.project:
            self.api.delete_timeline_item(timeline_id)
            self.refresh_planning()

    def save_timeline_item(
        self, timeline_id: str, point: str, title: str, content: str
    ) -> None:
        if self.api.project:
            self.api.update_timeline_item(timeline_id, point, title, content)
            saved = self.api.project.get_timeline_item(timeline_id)
            self.timeline_tab.update_item_label(
                timeline_id, saved.point, saved.title
            )
            self._mark_saved("timeline")

    def reorder_timeline_items(self, ordered_ids: list[str]) -> None:
        if self.api.project:
            self.api.reorder_timeline_items(ordered_ids)

    def _confirm_save_on_close(self) -> bool:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Question)
        message.setWindowTitle("終了確認")
        message.setText("未保存の変更があります。")
        message.setInformativeText("保存して終了しますか？")
        message.addButton("保存して終了", QMessageBox.ButtonRole.AcceptRole)
        cancel_button = message.addButton(
            "キャンセル", QMessageBox.ButtonRole.RejectRole
        )
        message.setDefaultButton(cancel_button)
        message.exec()
        clicked = message.clickedButton()
        return bool(
            clicked is not None
            and message.buttonRole(clicked) == QMessageBox.ButtonRole.AcceptRole
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._has_unsaved_changes():
            if not self._confirm_save_on_close():
                event.ignore()
                return
            if not self.manual_save():
                event.ignore()
                return
        self.settings.sync()
        event.accept()
