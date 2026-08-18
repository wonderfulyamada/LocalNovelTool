from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, QThread, Qt, QUrl
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
    QSpinBox,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
)

from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.project import ProjectContentError, ProjectError
from local_novel_tool.core.recovery import RecoveryEntry, RecoveryStore
from local_novel_tool.version import APP_NAME, APP_VERSION, AUTHOR_NAME
from .backup_worker import BackupWorker
from .editor_tab import TextEditorTab
from .error_dialog import show_error
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
CONTENT_FONT_SIZE_KEY = "content_font_size"
DEFAULT_CONTENT_FONT_SIZE = 14
SETTINGS_VERSION_KEY = "Meta/settings_version"
SETTINGS_VERSION = 1
INITIAL_SETUP_COMPLETED_KEY = "initial_setup_completed"


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
    def __init__(self, projects_root: Path, default_root: Path, parent=None, content_font_size: int = DEFAULT_CONTENT_FONT_SIZE) -> None:
        super().__init__(parent)
        self.default_root = default_root
        self.setWindowTitle("設定")

        self.path_edit = QLineEdit(str(projects_root), self)
        self.path_edit.setReadOnly(True)
        select_button = QPushButton("選択...", self)
        reset_button = QPushButton("デフォルトに戻す", self)
        select_button.clicked.connect(self.select_projects_root)
        reset_button.clicked.connect(self.reset_projects_root)
        self.font_size_spin = QSpinBox(self)
        self.font_size_spin.setRange(10, 32)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setValue(max(10, min(32, content_font_size)))

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
        layout.addWidget(QLabel("文章の文字サイズ", self))
        layout.addWidget(self.font_size_spin)
        layout.addWidget(buttons)

    def selected_root(self) -> Path:
        return Path(self.path_edit.text())

    def content_font_size(self) -> int:
        return self.font_size_spin.value()

    def select_projects_root(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "作品の保存フォルダを選択", self.path_edit.text()
        )
        if not folder:
            return
        path = Path(folder)
        if not path.is_dir() or not os.access(path, os.W_OK):
            show_error(self, "設定できません", "書き込み可能なフォルダを選択してください。")
            return
        self.path_edit.setText(str(path))

    def reset_projects_root(self) -> None:
        self.path_edit.setText(str(self.default_root))

    def accept(self) -> None:
        path = self.selected_root()
        if not path.is_absolute():
            show_error(self, "設定できません", "有効な保存先を選択してください。")
            return
        if path != self.default_root and (
            not path.is_dir() or not os.access(path, os.W_OK)
        ):
            show_error(self, "設定できません", "書き込み可能なフォルダを選択してください。")
            return
        super().accept()


class FirstLaunchDialog(SettingsDialog):
    """One-page setup using the same project-root control as settings."""

    def __init__(self, projects_root: Path, default_root: Path, parent=None) -> None:
        super().__init__(projects_root, default_root, parent)
        self.setWindowTitle("LocalNovelToolへようこそ")
        self.layout().insertWidget(0, QLabel("作品を保存するフォルダを選択してください。", self))
        buttons = self.findChild(QDialogButtonBox)
        if buttons is not None:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText("開始")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 760)
        self.api = CoreAPI()
        self.current_episode_id: str | None = None
        self._dirty_sources: set[str] = set()
        self._backup_thread: QThread | None = None
        self._backup_worker: BackupWorker | None = None
        self.application_root = self._application_root()
        self.settings = self._load_portable_settings()
        self.recovery_store = RecoveryStore(self.application_root / "recovery")
        legacy_root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "Recovery"
        self.legacy_recovery_store = RecoveryStore(legacy_root)
        self._restored_recovery_stores: dict[tuple[str, str], RecoveryStore] = {}

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
        self._apply_content_font_size(self._content_font_size())

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
        self._update_action_states()

    def _ensure_projects_root_available(self) -> bool:
        configured = self.settings.value(PROJECTS_ROOT_KEY, "", str).strip()
        if not configured or Path(configured).is_dir():
            return True
        show_error(self, "作品フォルダが見つかりません", "設定されている作品フォルダが見つかりません。\n新しい保存場所を選択してください。")
        folder = QFileDialog.getExistingDirectory(self, "作品の保存フォルダを選択", configured)
        if not folder:
            return False
        replacement = Path(folder)
        if not replacement.is_dir() or not os.access(replacement, os.W_OK):
            show_error(self, "設定できません", "書き込み可能なフォルダを選択してください。")
            return False
        self._set_projects_parent(replacement)
        return True

    @staticmethod
    def _application_root() -> Path:
        executable = Path(sys.executable).resolve()
        if executable.name.lower() == "localnoveltool.exe":
            return executable.parent
        return Path(__file__).resolve().parents[2]

    def _load_portable_settings(self) -> QSettings:
        path = self.application_root / "settings.ini"
        if path.exists():
            settings = QSettings(str(path), QSettings.Format.IniFormat)
        else:
            legacy_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
            legacy = QSettings(str(legacy_dir / "settings.ini"), QSettings.Format.IniFormat)
            settings = QSettings(str(path), QSettings.Format.IniFormat)
            for key in (SAMPLE_INITIALIZED_KEY, PROJECTS_ROOT_KEY, "last_project", CONTENT_FONT_SIZE_KEY):
                if legacy.contains(key):
                    settings.setValue(key, legacy.value(key))
        if (
            not settings.contains(INITIAL_SETUP_COMPLETED_KEY)
            and settings.value(SAMPLE_INITIALIZED_KEY, False, bool)
        ):
            settings.setValue(INITIAL_SETUP_COMPLETED_KEY, True)
        settings.setValue(SETTINGS_VERSION_KEY, SETTINGS_VERSION)
        settings.sync()
        if settings.status() != QSettings.Status.NoError:
            raise RuntimeError("LocalNovelToolのフォルダに設定を書き込めません。書き込み可能な場所へLocalNovelToolフォルダを移動してください。")
        return settings

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("メイン")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        actions = [
            ("new_project_action", "新規作品", self.new_project),
            ("open_project_action", "開く", self.open_project),
            ("toolbar_save_action", "保存", self.manual_save),
            ("add_chapter_action", "章追加", self.add_chapter),
            ("add_episode_action", "話追加", self.add_episode),
            ("rename_action", "名前変更", self.rename_selected),
            ("delete_action", "削除", self.delete_selected),
        ]
        for attribute, label, handler in actions:
            action = QAction(label, self)
            action.triggered.connect(handler)
            toolbar.addAction(action)
            setattr(self, attribute, action)
        toolbar.addWidget(QLabel("文章サイズ:", self))
        self.content_font_size_spin = QSpinBox(self)
        self.content_font_size_spin.setRange(10, 32)
        self.content_font_size_spin.setSuffix(" pt")
        self.content_font_size_spin.setValue(self._content_font_size())
        self.content_font_size_spin.valueChanged.connect(self._set_content_font_size)
        toolbar.addWidget(self.content_font_size_spin)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("ファイル")
        save_action = QAction("保存", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.manual_save)
        file_menu.addAction(save_action)
        self.save_action = save_action
        self.backup_action = QAction("バックアップを作成", self)
        self.backup_action.triggered.connect(self.create_backup)
        file_menu.addAction(self.backup_action)
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
        self.increase_font_action = QAction(self)
        self.increase_font_action.setShortcut(QKeySequence("Ctrl++"))
        self.increase_font_action.triggered.connect(lambda: self._set_content_font_size(self._content_font_size() + 1))
        self.addAction(self.increase_font_action)
        self.decrease_font_action = QAction(self)
        self.decrease_font_action.setShortcut(QKeySequence("Ctrl+-"))
        self.decrease_font_action.triggered.connect(lambda: self._set_content_font_size(self._content_font_size() - 1))
        self.addAction(self.decrease_font_action)

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
        self.tree.itemSelectionChanged.connect(self._update_action_states)
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
            self._write_pending_recovery()

    def _update_action_states(self) -> None:
        """Apply project/tree dependent action states from the current context."""
        has_project = self.api.project is not None
        kind, selected_id = self.tree.selected_identity()
        chapter_selected = has_project and kind == "chapter" and bool(selected_id)
        episode_selected = has_project and kind == "episode" and bool(selected_id)
        item_selected = chapter_selected or episode_selected

        self.toolbar_save_action.setEnabled(has_project)
        self.save_action.setEnabled(has_project)
        self.backup_action.setEnabled(has_project and not self._backup_is_running())
        self.open_folder_action.setEnabled(has_project)
        self.add_chapter_action.setEnabled(has_project)
        self.add_episode_action.setEnabled(chapter_selected)
        self.rename_action.setEnabled(item_selected)
        self.delete_action.setEnabled(item_selected)
        self._set_episode_editors_enabled(bool(episode_selected))
        for index in (0, 1, 2):
            self.tabs.setTabEnabled(index, has_project)
        for index in (3, 4, 5, 6):
            self.tabs.setTabEnabled(index, has_project)

    def _mark_saved(self, source: str) -> None:
        self._dirty_sources.discard(source)
        self._remove_current_recovery(source)

    def _recovery_identity_and_content(self, source: str):
        if source in ("body", "note") and self.current_episode_id:
            text = self.editor_tab.editor.toPlainText() if source == "body" else self.note_tab.editor.toPlainText()
            return self.current_episode_id, text
        if source == "reference" and self.reference_tab.current_id:
            return self.reference_tab.current_id, self.reference_tab.editor.toPlainText()
        if source == "plot" and self.plot_tab.current_id:
            return self.plot_tab.current_id, {
                "title": self.plot_tab.title.text(), "content": self.plot_tab.content.toPlainText(),
                "chapter_id": self.plot_tab.chapter.currentData(), "episode_id": self.plot_tab.episode.currentData(),
            }
        if source == "timeline" and self.timeline_tab.current_id:
            return self.timeline_tab.current_id, {
                "point": self.timeline_tab.point.text(), "title": self.timeline_tab.title.text(),
                "content": self.timeline_tab.content.toPlainText(),
            }
        return None

    def _write_pending_recovery(self) -> None:
        if not self.api.project:
            return
        for source in tuple(self._dirty_sources):
            current = self._recovery_identity_and_content(source)
            if current is not None:
                item_id, content = current
                self.recovery_store.save(self.api.project.root, source, item_id, content)

    def _remove_current_recovery(self, source: str) -> None:
        if not self.api.project:
            return
        current = self._recovery_identity_and_content(source)
        if current is not None:
            self.recovery_store.remove(self.api.project.root, source, current[0])
            store = self._restored_recovery_stores.pop((source, current[0]), None)
            if store is not None:
                store.remove(self.api.project.root, source, current[0])

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
        if not self._ensure_projects_root_available():
            return
        if not self.settings.value(INITIAL_SETUP_COMPLETED_KEY, False, bool):
            selected_root = self._default_projects_parent()
            while True:
                dialog = FirstLaunchDialog(
                    selected_root, self._default_projects_parent(), self
                )
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                selected_root = dialog.selected_root()
                try:
                    if not selected_root.is_absolute():
                        raise ProjectError("有効な保存先を選択してください。")
                    selected_root.mkdir(parents=True, exist_ok=True)
                    if not selected_root.is_dir() or not os.access(selected_root, os.W_OK):
                        raise ProjectError("作品の保存フォルダへ書き込めません。")
                    sample = initialize_sample_project(
                        self.api, self.settings, selected_root
                    )
                    if sample is None or self.api.project is None:
                        raise ProjectError("チュートリアルを開けませんでした。")
                    self._set_projects_parent(selected_root)
                    self._after_project_loaded()
                    self.settings.setValue(INITIAL_SETUP_COMPLETED_KEY, True)
                    self.settings.sync()
                except Exception as exc:
                    self.settings.setValue(INITIAL_SETUP_COMPLETED_KEY, False)
                    self.settings.sync()
                    show_error(self, "サンプル作成失敗", str(exc))
                    continue
                return
        try:
            sample = initialize_sample_project(
                self.api, self.settings, self._tutorial_parent()
            )
        except Exception as exc:
            show_error(self, "サンプル作成失敗", str(exc))
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

    def _content_font_size(self) -> int:
        raw = self.settings.value(CONTENT_FONT_SIZE_KEY, DEFAULT_CONTENT_FONT_SIZE)
        try:
            return max(10, min(32, int(raw)))
        except (TypeError, ValueError):
            return DEFAULT_CONTENT_FONT_SIZE

    def _apply_content_font_size(self, size: int) -> None:
        size = max(10, min(32, size))
        for editor in (self.editor_tab.editor, self.note_tab.editor, self.reference_tab.editor, self.plot_tab.content, self.timeline_tab.content):
            font = editor.font()
            font.setPointSize(size)
            editor.setFont(font)
        self.preview_tab.set_content_font_size(size)

    def _set_content_font_size(self, size: int) -> None:
        size = max(10, min(32, size))
        self.settings.setValue(CONTENT_FONT_SIZE_KEY, size)
        self.settings.sync()
        self._apply_content_font_size(size)
        if self.content_font_size_spin.value() != size:
            self.content_font_size_spin.blockSignals(True)
            self.content_font_size_spin.setValue(size)
            self.content_font_size_spin.blockSignals(False)

    def _set_projects_parent(self, path: Path) -> None:
        self.settings.setValue(PROJECTS_ROOT_KEY, str(path))
        self.settings.sync()

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self._projects_parent(), self._default_projects_parent(), self, content_font_size=self._content_font_size()
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._set_projects_parent(dialog.selected_root())
            self._set_content_font_size(dialog.content_font_size())

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
                show_error(self, "退避失敗", str(exc))
                return

        load_recreated = current is None or tutorial_is_current
        recreate_api = self.api if load_recreated else CoreAPI()
        try:
            recreate_tutorial_project(recreate_api, self._tutorial_parent())
            self.settings.setValue(SAMPLE_INITIALIZED_KEY, True)
            self.settings.sync()
            if load_recreated:
                self._load_project(tutorial_root)
            if archived:
                self.statusBar().showMessage(f"退避先: {archived}")
        except Exception as exc:
            show_error(self, "再作成失敗", str(exc))

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
            show_error(self, "保存失敗", str(exc))
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
            show_error(self, "作成できません", str(exc))
        except Exception as exc:
            show_error(self, "作成失敗", str(exc))

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

    def create_backup(self) -> None:
        if not self.api.project or self._backup_is_running():
            return
        thread = QThread(self)
        worker = BackupWorker(
            self.api.project.root, self._tutorial_parent() / "Backups"
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._backup_succeeded)
        worker.failed.connect(self._backup_failed)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.succeeded.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._backup_finished)
        thread.finished.connect(thread.deleteLater)
        self._backup_thread = thread
        self._backup_worker = worker
        self.backup_action.setEnabled(False)
        self.statusBar().showMessage("バックアップ中...")
        thread.start()

    def _backup_is_running(self) -> bool:
        return self._backup_thread is not None

    def _backup_succeeded(self, destination: Path) -> None:
        QMessageBox.information(
            self,
            "バックアップ完了",
            f"バックアップを作成しました。\n{destination}",
        )
        self.statusBar().showMessage(f"バックアップ: {destination}")

    def _backup_failed(self, message: str) -> None:
        show_error(self, "バックアップ失敗", message)
        self.statusBar().showMessage("バックアップに失敗しました")

    def _backup_finished(self) -> None:
        self._backup_worker = None
        self._backup_thread = None
        try:
            self._update_action_states()
        except RuntimeError:
            # A queued completion may arrive after Qt has destroyed the window.
            pass

    def _load_project(self, root: Path) -> None:
        try:
            self.api.open_project(root)
            self._after_project_loaded()
        except Exception as exc:
            show_error(self, "読込失敗", str(exc))

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
        self.settings.setValue("last_project", str(project.root))
        self.statusBar().showMessage(str(project.root))
        if project.chapters and project.chapters[0].episodes:
            self.tree.select_episode(project.chapters[0].episodes[0].id)
        self._update_action_states()
        self._offer_recovery()

    def _canonical_recovery_content(self, entry: RecoveryEntry):
        project = self.api.project
        if not project:
            raise ProjectError("作品が開かれていません。")
        if entry.source == "body":
            return self.api.load_episode_body(entry.item_id)
        if entry.source == "note":
            return self.api.load_episode_note(entry.item_id)
        if entry.source == "reference":
            return self.api.load_reference(entry.item_id)
        if entry.source == "plot":
            item = project.get_plot_item(entry.item_id)
            return {"title": item.title, "content": item.content, "chapter_id": item.chapter_id, "episode_id": item.episode_id}
        if entry.source == "timeline":
            item = project.get_timeline_item(entry.item_id)
            return {"point": item.point, "title": item.title, "content": item.content}
        raise ProjectError("不明なRecoveryデータです。")

    def _confirm_recovery(self, entry: RecoveryEntry) -> bool:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Question)
        message.setWindowTitle("編集内容の復旧")
        message.setText("異常終了時の未保存内容が見つかりました。")
        message.setInformativeText("復旧しますか？ 正本は復旧内容を保存するまで変更されません。")
        restore_button = message.addButton("復旧する", QMessageBox.ButtonRole.AcceptRole)
        message.addButton("無視する", QMessageBox.ButtonRole.RejectRole)
        message.setDefaultButton(restore_button)
        message.exec()
        return message.clickedButton() is restore_button

    def _offer_recovery(self) -> None:
        if not self.api.project:
            return
        for store in (self.recovery_store, self.legacy_recovery_store):
            for entry in store.load(self.api.project.root):
                try:
                    current = self._canonical_recovery_content(entry)
                except (ProjectError, ProjectContentError):
                    continue
                if current == entry.content:
                    store.remove(self.api.project.root, entry.source, entry.item_id)
                    continue
                if self._confirm_recovery(entry):
                    self._restored_recovery_stores[(entry.source, entry.item_id)] = store
                    self._restore_recovery(entry)
                else:
                    store.remove(self.api.project.root, entry.source, entry.item_id)
                return

    def _restore_recovery(self, entry: RecoveryEntry) -> None:
        if entry.source in ("body", "note"):
            self.tree.select_episode(entry.item_id)
            tab = self.editor_tab if entry.source == "body" else self.note_tab
            tab.set_text(str(entry.content))
        elif entry.source == "reference":
            self.open_reference(entry.item_id)
            self.reference_tab.editor.setPlainText(str(entry.content))
        elif entry.source == "plot" and isinstance(entry.content, dict):
            self.open_plot_item(entry.item_id)
            self.plot_tab.title.setText(str(entry.content.get("title", "")))
            self.plot_tab.content.setPlainText(str(entry.content.get("content", "")))
            self.plot_tab._select_combo_data(self.plot_tab.chapter, entry.content.get("chapter_id"))
            self.plot_tab._select_combo_data(self.plot_tab.episode, entry.content.get("episode_id"))
        elif entry.source == "timeline" and isinstance(entry.content, dict):
            self.open_timeline_item(entry.item_id)
            self.timeline_tab.point.setText(str(entry.content.get("point", "")))
            self.timeline_tab.title.setText(str(entry.content.get("title", "")))
            self.timeline_tab.content.setPlainText(str(entry.content.get("content", "")))
        self._dirty_sources.add(entry.source)
        self.statusBar().showMessage("未保存の編集内容を復旧しました")

    def refresh_tree(self) -> None:
        if self.api.project:
            selected = self.current_episode_id
            self.tree.rebuild(self.api.chapters())
            if selected:
                self.tree.select_episode(selected)
            self._update_action_states()

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
        errors: list[str] = []
        try:
            body = self.api.load_episode_body(episode_id)
        except ProjectContentError as exc:
            body = ""
            errors.append(str(exc))
        try:
            note = self.api.load_episode_note(episode_id)
        except ProjectContentError as exc:
            note = ""
            errors.append(str(exc))
        self.editor_tab.set_text(body)
        self.note_tab.set_text(note)
        episode = self.api.project.get_episode(episode_id)
        self.statusBar().showMessage(episode.title)
        if self.tabs.currentWidget() == self.preview_tab:
            self.preview_tab.set_source_text(self.editor_tab.editor.toPlainText())
        self._update_action_states()
        if errors:
            show_error(self, "データ読込エラー", "\n".join(errors))

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
            show_error(self, "移動できません", str(exc))
            self.refresh_tree()

    def perform_search(self, query: str) -> None:
        if self.api.project:
            self.search_tab.set_results(self.api.search(query))
            errors = self.api.content_errors()
            if errors:
                show_error(
                    self,
                    "データ読込エラー",
                    "\n".join(str(error) for error in errors),
                )

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
        try:
            text = self.api.load_reference(reference_id)
        except ProjectContentError as exc:
            text = ""
            show_error(self, "データ読込エラー", str(exc))
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
        if self._backup_is_running():
            self.statusBar().showMessage(
                "バックアップ中です。完了後にもう一度終了してください。"
            )
            event.ignore()
            return
        if self._has_unsaved_changes():
            if not self._confirm_save_on_close():
                event.ignore()
                return
            if not self.manual_save():
                event.ignore()
                return
        self.settings.sync()
        event.accept()
