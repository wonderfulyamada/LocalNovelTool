from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TextEditorTab(QWidget):
    save_requested = Signal(str)

    def __init__(self, show_ruby_button: bool = False) -> None:
        super().__init__()
        self._loading = False
        self.editor = QPlainTextEdit()
        self.editor.setTabStopDistance(32)
        self.count_label = QLabel("0文字")
        self.save_label = QLabel("")

        top = QHBoxLayout()
        if show_ruby_button:
            ruby_button = QPushButton("ルビ")
            ruby_button.clicked.connect(self.insert_ruby)
            top.addWidget(ruby_button)
        top.addStretch(1)
        top.addWidget(self.count_label)
        top.addWidget(self.save_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(top)
        layout.addWidget(self.editor)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._request_save)
        self.editor.textChanged.connect(self._changed)

    def _changed(self) -> None:
        self.count_label.setText(f"{len(self.editor.toPlainText())}文字")
        if not self._loading:
            self.save_label.setText("未保存")
            self.timer.start()

    def _request_save(self) -> None:
        if self._loading:
            return
        self.save_requested.emit(self.editor.toPlainText())
        self.save_label.setText("保存済み")

    def set_text(self, text: str) -> None:
        self.timer.stop()
        self._loading = True
        self.editor.setPlainText(text)
        self._loading = False
        self.count_label.setText(f"{len(text)}文字")
        self.save_label.setText("保存済み")

    def flush(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self._request_save()

    def mark_saved(self) -> None:
        self.timer.stop()
        self.save_label.setText("保存済み")

    def insert_ruby(self) -> None:
        cursor = self.editor.textCursor()
        selected = cursor.selectedText()
        if not selected:
            return
        reading, ok = QInputDialog.getText(self, "ルビ", f"「{selected}」の読み")
        if not ok or not reading.strip():
            return
        cursor.insertText(f"｜{selected}《{reading.strip()}》")
        self.editor.setTextCursor(cursor)

    def go_to_line(self, line_number: int) -> None:
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(max(0, line_number - 1)):
            cursor.movePosition(QTextCursor.MoveOperation.Down)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()
