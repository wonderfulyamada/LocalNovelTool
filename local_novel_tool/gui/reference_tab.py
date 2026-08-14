from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from local_novel_tool.core.project import REFERENCE_CATEGORIES


class ReferenceTab(QWidget):
    open_requested = Signal(str)
    create_requested = Signal(str, str)
    rename_requested = Signal(str, str)
    delete_requested = Signal(str)
    save_requested = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.current_id: str | None = None
        self._loading = False
        self.category = QComboBox()
        self.category.addItem("すべて")
        self.category.addItems(REFERENCE_CATEGORIES)
        self.list = QListWidget()
        self.recent = QListWidget()
        self.recent.setMaximumHeight(110)
        self.editor = QPlainTextEdit()
        self.title = QLabel("資料未選択")

        add_button = QPushButton("追加")
        rename_button = QPushButton("名前変更")
        delete_button = QPushButton("削除")
        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(rename_button)
        buttons.addWidget(delete_button)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("カテゴリ"))
        left_layout.addWidget(self.category)
        left_layout.addLayout(buttons)
        left_layout.addWidget(self.list, 1)
        left_layout.addWidget(QLabel("最近開いた資料"))
        left_layout.addWidget(self.recent)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.title)
        right_layout.addWidget(self.editor)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 740])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._save)
        self.editor.textChanged.connect(lambda: (not self._loading) and self.timer.start())
        self.list.itemDoubleClicked.connect(lambda item, _column: self._open_item(item))
        self.list.currentItemChanged.connect(lambda current, _: self._open_item(current) if current else None)
        self.recent.itemDoubleClicked.connect(lambda item, _column: self._open_item(item))
        add_button.clicked.connect(self._add)
        rename_button.clicked.connect(self._rename)
        delete_button.clicked.connect(self._delete)
        self.category.currentTextChanged.connect(lambda _: self.filter_current())
        self._all_refs = []

    def set_references(self, refs, recent_refs) -> None:
        self._all_refs = list(refs)
        self.filter_current()
        self.recent.clear()
        for ref in recent_refs:
            item = QListWidgetItem(f"[{ref.category}] {ref.title}")
            item.setData(1000, ref.id)
            self.recent.addItem(item)

    def filter_current(self) -> None:
        current = self.category.currentText()
        self.list.clear()
        for ref in self._all_refs:
            if current != "すべて" and ref.category != current:
                continue
            item = QListWidgetItem(f"[{ref.category}] {ref.title}")
            item.setData(1000, ref.id)
            self.list.addItem(item)

    def _open_item(self, item) -> None:
        if item is not None:
            self.open_requested.emit(item.data(1000))

    def show_reference(self, ref, text: str) -> None:
        self.timer.stop()
        self.current_id = ref.id
        self.title.setText(f"[{ref.category}] {ref.title}")
        self._loading = True
        self.editor.setPlainText(text)
        self._loading = False

    def select_reference(self, reference_id: str) -> None:
        for widget in (self.list, self.recent):
            for i in range(widget.count()):
                item = widget.item(i)
                if item.data(1000) == reference_id:
                    widget.setCurrentItem(item)
                    return
        self.open_requested.emit(reference_id)

    def _add(self) -> None:
        category, ok = QInputDialog.getItem(self, "資料追加", "カテゴリ", REFERENCE_CATEGORIES, 0, False)
        if not ok:
            return
        title, ok = QInputDialog.getText(self, "資料追加", "名前")
        if ok and title.strip():
            self.create_requested.emit(category, title.strip())

    def _rename(self) -> None:
        if not self.current_id:
            return
        title, ok = QInputDialog.getText(self, "名前変更", "新しい名前")
        if ok and title.strip():
            self.rename_requested.emit(self.current_id, title.strip())

    def _delete(self) -> None:
        if not self.current_id:
            return
        if QMessageBox.question(self, "削除", "この資料を削除しますか？") == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(self.current_id)
            self.current_id = None
            self.title.setText("資料未選択")
            self.editor.clear()

    def _save(self) -> None:
        if self.current_id:
            self.save_requested.emit(self.current_id, self.editor.toPlainText())

    def flush(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self._save()
