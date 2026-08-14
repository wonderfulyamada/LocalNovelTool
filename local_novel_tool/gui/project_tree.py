from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

ROLE_KIND = Qt.ItemDataRole.UserRole
ROLE_ID = Qt.ItemDataRole.UserRole + 1


class ProjectTree(QTreeWidget):
    episode_selected = Signal(str)
    structure_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.itemSelectionChanged.connect(self._on_selection)

    def rebuild(self, chapters) -> None:
        self.blockSignals(True)
        self.clear()
        for chapter in chapters:
            ch_item = QTreeWidgetItem([chapter.title])
            ch_item.setData(0, ROLE_KIND, "chapter")
            ch_item.setData(0, ROLE_ID, chapter.id)
            ch_item.setFlags(ch_item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
            self.addTopLevelItem(ch_item)
            for episode in chapter.episodes:
                ep_item = QTreeWidgetItem([episode.title])
                ep_item.setData(0, ROLE_KIND, "episode")
                ep_item.setData(0, ROLE_ID, episode.id)
                ep_item.setFlags((ep_item.flags() | Qt.ItemFlag.ItemIsDragEnabled) & ~Qt.ItemFlag.ItemIsDropEnabled)
                ch_item.addChild(ep_item)
            ch_item.setExpanded(True)
        self.blockSignals(False)

    def _on_selection(self) -> None:
        item = self.currentItem()
        if item and item.data(0, ROLE_KIND) == "episode":
            self.episode_selected.emit(item.data(0, ROLE_ID))

    def selected_identity(self) -> tuple[str | None, str | None]:
        item = self.currentItem()
        if not item:
            return None, None
        return item.data(0, ROLE_KIND), item.data(0, ROLE_ID)

    def select_episode(self, episode_id: str) -> None:
        for index in range(self.topLevelItemCount()):
            chapter_item = self.topLevelItem(index)
            for child_index in range(chapter_item.childCount()):
                item = chapter_item.child(child_index)
                if item.data(0, ROLE_ID) == episode_id:
                    self.setCurrentItem(item)
                    return

    def structure_order(self) -> list[tuple[str, list[str]]] | None:
        result: list[tuple[str, list[str]]] = []
        for index in range(self.topLevelItemCount()):
            chapter_item = self.topLevelItem(index)
            if chapter_item.data(0, ROLE_KIND) != "chapter":
                return None
            chapter_id = chapter_item.data(0, ROLE_ID)
            episodes: list[str] = []
            for child_index in range(chapter_item.childCount()):
                item = chapter_item.child(child_index)
                if item.data(0, ROLE_KIND) != "episode" or item.childCount() > 0:
                    return None
                episodes.append(item.data(0, ROLE_ID))
            result.append((chapter_id, episodes))
        return result

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().dropEvent(event)
        if self.structure_order() is None:
            self.structure_changed.emit()
            return
        self.structure_changed.emit()
