from __future__ import annotations

from pathlib import Path

from .backup import create_project_backup
from .models import Chapter, Episode, PlotItem, Reference, SearchResult, TimelineItem
from .project import NovelProject


class CoreAPI:
    """GUIなど外側の層から触る公開API。GUIは保存ファイルを直接操作しない。"""

    def __init__(self) -> None:
        self.project: NovelProject | None = None

    def _require(self) -> NovelProject:
        if self.project is None:
            raise RuntimeError("作品が開かれていません。")
        return self.project

    def create_project(self, parent: Path, title: str) -> NovelProject:
        self.project = NovelProject.create(parent, title)
        return self.project

    def open_project(self, root: Path) -> NovelProject:
        self.project = NovelProject.open(root)
        return self.project

    def create_backup(self, backups_root: Path) -> Path:
        return create_project_backup(self._require().root, backups_root)

    def chapters(self) -> list[Chapter]:
        return self._require().chapters

    def references(self) -> list[Reference]:
        return self._require().references

    def create_chapter(self, title: str) -> Chapter:
        return self._require().create_chapter(title)

    def rename_chapter(self, chapter_id: str, title: str) -> None:
        self._require().rename_chapter(chapter_id, title)

    def delete_chapter(self, chapter_id: str) -> None:
        self._require().delete_chapter(chapter_id)

    def create_episode(self, chapter_id: str, title: str) -> Episode:
        return self._require().create_episode(chapter_id, title)

    def rename_episode(self, episode_id: str, title: str) -> None:
        self._require().rename_episode(episode_id, title)

    def delete_episode(self, episode_id: str) -> None:
        self._require().delete_episode(episode_id)

    def reorder_structure(self, ordered: list[tuple[str, list[str]]]) -> None:
        self._require().reorder_structure(ordered)

    def load_episode_body(self, episode_id: str) -> str:
        return self._require().load_episode_body(episode_id)

    def save_episode_body(self, episode_id: str, text: str) -> None:
        self._require().save_episode_body(episode_id, text)

    def load_episode_note(self, episode_id: str) -> str:
        return self._require().load_episode_note(episode_id)

    def save_episode_note(self, episode_id: str, text: str) -> None:
        self._require().save_episode_note(episode_id, text)

    def create_reference(self, category: str, title: str) -> Reference:
        return self._require().create_reference(category, title)

    def rename_reference(self, reference_id: str, title: str) -> None:
        self._require().rename_reference(reference_id, title)

    def delete_reference(self, reference_id: str) -> None:
        self._require().delete_reference(reference_id)

    def load_reference(self, reference_id: str) -> str:
        return self._require().load_reference(reference_id)

    def save_reference(self, reference_id: str, text: str) -> None:
        self._require().save_reference(reference_id, text)

    def recent_references(self) -> list[Reference]:
        return self._require().recent_reference_items()

    def plot_items(self) -> list[PlotItem]:
        return self._require().plot_items

    def create_plot_item(
        self,
        title: str,
        content: str = "",
        chapter_id: str | None = None,
        episode_id: str | None = None,
    ) -> PlotItem:
        return self._require().create_plot_item(
            title, content, chapter_id, episode_id
        )

    def update_plot_item(
        self,
        plot_id: str,
        title: str,
        content: str,
        chapter_id: str | None,
        episode_id: str | None,
    ) -> None:
        self._require().update_plot_item(
            plot_id, title, content, chapter_id, episode_id
        )

    def delete_plot_item(self, plot_id: str) -> None:
        self._require().delete_plot_item(plot_id)

    def reorder_plot_items(self, ordered_ids: list[str]) -> None:
        self._require().reorder_plot_items(ordered_ids)

    def timeline_items(self) -> list[TimelineItem]:
        return self._require().timeline_items

    def create_timeline_item(
        self, point: str, title: str, content: str = ""
    ) -> TimelineItem:
        return self._require().create_timeline_item(point, title, content)

    def update_timeline_item(
        self, timeline_id: str, point: str, title: str, content: str
    ) -> None:
        self._require().update_timeline_item(timeline_id, point, title, content)

    def delete_timeline_item(self, timeline_id: str) -> None:
        self._require().delete_timeline_item(timeline_id)

    def reorder_timeline_items(self, ordered_ids: list[str]) -> None:
        self._require().reorder_timeline_items(ordered_ids)

    def search(self, query: str) -> list[SearchResult]:
        return self._require().search(query)
