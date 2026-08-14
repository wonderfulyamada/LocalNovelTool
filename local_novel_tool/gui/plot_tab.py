from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

ITEM_ID_ROLE = 1000


class PlotTab(QWidget):
    open_requested = Signal(str)
    create_requested = Signal(str)
    rename_requested = Signal(str, str)
    delete_requested = Signal(str)
    save_requested = Signal(str, str, str, object, object)
    reorder_requested = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.current_id: str | None = None
        self._loading = False
        self._rebuilding = False

        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.title = QLineEdit()
        self.content = QPlainTextEdit()
        self.chapter = QComboBox()
        self.episode = QComboBox()

        add_button = QPushButton("追加")
        rename_button = QPushButton("名前変更")
        delete_button = QPushButton("削除")
        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(rename_button)
        buttons.addWidget(delete_button)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addLayout(buttons)
        left_layout.addWidget(self.list)

        form = QFormLayout()
        form.addRow("タイトル", self.title)
        form.addRow("関連する章", self.chapter)
        form.addRow("関連する話", self.episode)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addLayout(form)
        right_layout.addWidget(self.content)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 720])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._save)
        self.title.textChanged.connect(self._changed)
        self.content.textChanged.connect(self._changed)
        self.chapter.currentIndexChanged.connect(self._changed)
        self.episode.currentIndexChanged.connect(self._changed)
        self.list.currentItemChanged.connect(self._current_changed)
        self.list.model().rowsMoved.connect(self._rows_moved)
        add_button.clicked.connect(self._add)
        rename_button.clicked.connect(self._rename)
        delete_button.clicked.connect(self._delete)

    def set_items(self, items, chapters) -> None:
        selected = self.current_id
        self._rebuilding = True
        self.list.clear()
        for item in items:
            widget_item = QListWidgetItem(item.title)
            widget_item.setData(ITEM_ID_ROLE, item.id)
            self.list.addItem(widget_item)

        self.chapter.clear()
        self.chapter.addItem("指定なし", None)
        self.episode.clear()
        self.episode.addItem("指定なし", None)
        for chapter in chapters:
            self.chapter.addItem(chapter.title, chapter.id)
            for episode in chapter.episodes:
                self.episode.addItem(f"{chapter.title} / {episode.title}", episode.id)
        self._rebuilding = False
        if selected:
            self.select_item(selected)

    def show_item(self, item) -> None:
        self.timer.stop()
        self.current_id = item.id
        self._loading = True
        self.title.setText(item.title)
        self.content.setPlainText(item.content)
        self._select_combo_data(self.chapter, item.chapter_id)
        self._select_combo_data(self.episode, item.episode_id)
        self._loading = False

    @staticmethod
    def _select_combo_data(combo: QComboBox, value) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def select_item(self, item_id: str) -> None:
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.data(ITEM_ID_ROLE) == item_id:
                self.list.setCurrentItem(item)
                return
        self.open_requested.emit(item_id)

    def update_item_label(self, item_id: str, title: str) -> None:
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.data(ITEM_ID_ROLE) == item_id:
                item.setText(title)
                return

    def _current_changed(self, current, _previous) -> None:
        if current is not None and not self._rebuilding:
            self.open_requested.emit(current.data(ITEM_ID_ROLE))

    def _changed(self, *_args) -> None:
        if not self._loading and not self._rebuilding and self.current_id:
            self.timer.start()

    def _add(self) -> None:
        title, ok = QInputDialog.getText(self, "展開追加", "タイトル")
        if ok and title.strip():
            self.create_requested.emit(title.strip())

    def _rename(self) -> None:
        if not self.current_id:
            return
        title, ok = QInputDialog.getText(
            self, "名前変更", "新しい名前", text=self.title.text()
        )
        if ok and title.strip():
            self.rename_requested.emit(self.current_id, title.strip())

    def _delete(self) -> None:
        if not self.current_id:
            return
        if QMessageBox.question(
            self, "削除", "この展開を削除しますか？"
        ) == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(self.current_id)
            self.current_id = None
            self._clear_editor()

    def _clear_editor(self) -> None:
        self._loading = True
        self.title.clear()
        self.content.clear()
        self.chapter.setCurrentIndex(0)
        self.episode.setCurrentIndex(0)
        self._loading = False

    def _save(self) -> None:
        if self.current_id:
            self.save_requested.emit(
                self.current_id,
                self.title.text(),
                self.content.toPlainText(),
                self.chapter.currentData(),
                self.episode.currentData(),
            )

    def _rows_moved(self, *_args) -> None:
        if not self._rebuilding:
            self.reorder_requested.emit(
                [self.list.item(i).data(ITEM_ID_ROLE) for i in range(self.list.count())]
            )

    def flush(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self._save()
