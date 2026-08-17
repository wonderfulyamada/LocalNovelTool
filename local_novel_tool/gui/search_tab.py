from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SearchTab(QWidget):
    search_requested = Signal(str)
    result_activated = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.input = QLineEdit()
        self.input.setPlaceholderText("本文・話メモ・資料を横断検索")
        button = QPushButton("検索")
        self.results = QTreeWidget()
        self.results.setHeaderLabels(["種類", "場所", "行", "内容"])
        self.results.setRootIsDecorated(False)

        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.results)

        button.clicked.connect(self._emit_search)
        self.input.returnPressed.connect(self._emit_search)
        self.results.itemDoubleClicked.connect(self._activate)

    def _emit_search(self) -> None:
        self.search_requested.emit(self.input.text())

    def set_results(self, results) -> None:
        self.results.clear()
        kind_names = {"episode": "本文", "episode_note": "話メモ", "reference": "資料"}
        for result in results:
            where = f"{result.category} / {result.title}" if result.category else result.title
            item = QTreeWidgetItem([
                kind_names.get(result.kind, result.kind),
                where,
                str(result.line),
                result.excerpt,
            ])
            item.setData(0, 1000, result)
            self.results.addTopLevelItem(item)
        for col in range(3):
            self.results.resizeColumnToContents(col)

    def _activate(self, item: QTreeWidgetItem) -> None:
        result = item.data(0, 1000)
        if result is not None:
            self.result_activated.emit(result)
