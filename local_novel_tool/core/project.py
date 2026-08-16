from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models import Chapter, Episode, PlotItem, Reference, SearchResult, TimelineItem
from .migration import CURRENT_FORMAT_VERSION, FormatVersionError, migrate_project_data

PROJECT_FILE = "project.json"
FORMAT_VERSION = CURRENT_FORMAT_VERSION
REFERENCE_CATEGORIES = ("登場人物", "アイテム", "世界観", "その他")
LEGACY_REFERENCE_CATEGORIES = {"キャラ": "登場人物", "展開": "その他"}
PROJECT_FOLDERS = ("manuscript", "episode_notes", "references", "backups")
INVALID_PROJECT_NAME_CHARS = frozenset('<>:"/\\|?*')
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class ProjectError(RuntimeError):
    pass


class ProjectContentError(ProjectError):
    pass


class NovelProject:
    def __init__(self, root: Path, data: dict[str, Any]) -> None:
        self.root = root.resolve()
        self.title = str(data.get("title", self.root.name))
        self.chapters = [Chapter.from_dict(item) for item in data.get("chapters", [])]
        self.references = [Reference.from_dict(item) for item in data.get("references", [])]
        for reference in self.references:
            reference.category = LEGACY_REFERENCE_CATEGORIES.get(
                reference.category, reference.category
            )
        self.recent_references: list[str] = list(data.get("recent_references", []))
        self.plot_items = [PlotItem.from_dict(item) for item in data.get("plot_items", [])]
        self.timeline_items = [
            TimelineItem.from_dict(item) for item in data.get("timeline_items", [])
        ]
        self.last_content_errors: list[ProjectContentError] = []

    @classmethod
    def create(cls, parent: Path, title: str) -> "NovelProject":
        """Create a new project in a new ``parent / title`` directory."""
        title = title.strip()
        cls._validate_project_name(title)
        parent = parent.resolve()
        if not parent.is_dir():
            raise ProjectError("保存先の親フォルダが見つかりません。")

        root = parent / title
        try:
            # exist_ok=False makes this the overwrite guard, including races between
            # checking the name in the GUI and actually creating the directory.
            root.mkdir(exist_ok=False)
        except FileExistsError as exc:
            raise ProjectError(f"同名のフォルダが既に存在します: {title}") from exc
        except OSError as exc:
            raise ProjectError(f"作品フォルダを作成できませんでした: {exc}") from exc

        try:
            for folder in PROJECT_FOLDERS:
                (root / folder).mkdir()
            project = cls(root, {"title": title, "chapters": [], "references": []})
            project.save_metadata()
            return project
        except Exception:
            # The directory was created by this method and was never pre-existing.
            # Remove a partial project so the user can safely retry.
            shutil.rmtree(root, ignore_errors=True)
            raise

    @staticmethod
    def _validate_project_name(title: str) -> None:
        if not title:
            raise ProjectError("作品名を入力してください。")
        if title in {".", ".."} or any(
            char in INVALID_PROJECT_NAME_CHARS or ord(char) < 32 for char in title
        ):
            raise ProjectError("作品名にフォルダ名として使用できない文字が含まれています。")
        if title.endswith((" ", ".")):
            raise ProjectError("作品名の末尾に空白またはピリオドは使用できません。")
        if title.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
            raise ProjectError("この作品名はフォルダ名として使用できません。")

    @classmethod
    def open(
        cls,
        root: Path,
        *,
        backup_before_migration: Callable[[], object] | None = None,
    ) -> "NovelProject":
        root = root.resolve()
        project_path = root / PROJECT_FILE
        if not project_path.exists():
            raise ProjectError(f"作品データが見つかりません: {project_path}")
        try:
            with project_path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
        except json.JSONDecodeError as exc:
            raise ProjectError(
                f"project.json が壊れています: {project_path} "
                f"(行 {exc.lineno}, 列 {exc.colno}: {exc.msg})"
            ) from exc
        except (OSError, UnicodeError) as exc:
            raise ProjectError(
                f"project.json を読み込めません: {project_path}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise ProjectError(f"project.json の構造が不正です: {project_path}")
        try:
            data = migrate_project_data(
                data, backup_before_migration=backup_before_migration
            )
        except FormatVersionError as exc:
            raise ProjectError(f"{project_path}: {exc}") from exc
        try:
            project = cls(root, data)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectError(
                f"project.json の構造が不正です: {project_path}: {exc}"
            ) from exc
        for folder in PROJECT_FOLDERS:
            (root / folder).mkdir(exist_ok=True)
        return project

    def _metadata(self) -> dict[str, Any]:
        return {
            "format_version": FORMAT_VERSION,
            "title": self.title,
            "chapters": [chapter.to_dict() for chapter in self.chapters],
            "references": [ref.to_dict() for ref in self.references],
            "recent_references": self.recent_references[:20],
            "plot_items": [item.to_dict() for item in self.plot_items],
            "timeline_items": [item.to_dict() for item in self.timeline_items],
        }

    def save_metadata(self) -> None:
        tmp = self.root / f"{PROJECT_FILE}.tmp"
        with tmp.open("w", encoding="utf-8", newline="\n") as fp:
            json.dump(self._metadata(), fp, ensure_ascii=False, indent=2)
        tmp.replace(self.root / PROJECT_FILE)

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def get_chapter(self, chapter_id: str) -> Chapter:
        for chapter in self.chapters:
            if chapter.id == chapter_id:
                return chapter
        raise ProjectError("章が見つかりません。")

    def get_episode(self, episode_id: str) -> Episode:
        for chapter in self.chapters:
            for episode in chapter.episodes:
                if episode.id == episode_id:
                    return episode
        raise ProjectError("話が見つかりません。")

    def find_episode_parent(self, episode_id: str) -> Chapter:
        for chapter in self.chapters:
            if any(ep.id == episode_id for ep in chapter.episodes):
                return chapter
        raise ProjectError("話が見つかりません。")

    def create_chapter(self, title: str) -> Chapter:
        chapter = Chapter(id=self._new_id("ch"), title=title.strip() or "新しい章", episodes=[])
        self.chapters.append(chapter)
        self.save_metadata()
        return chapter

    def rename_chapter(self, chapter_id: str, title: str) -> None:
        chapter = self.get_chapter(chapter_id)
        chapter.title = title.strip() or chapter.title
        self.save_metadata()

    def delete_chapter(self, chapter_id: str) -> None:
        chapter = self.get_chapter(chapter_id)
        for episode in list(chapter.episodes):
            self._delete_episode_files(episode)
        self.chapters = [item for item in self.chapters if item.id != chapter_id]
        self.save_metadata()

    def create_episode(self, chapter_id: str, title: str) -> Episode:
        chapter = self.get_chapter(chapter_id)
        episode_id = self._new_id("ep")
        episode = Episode(
            id=episode_id,
            title=title.strip() or "新しい話",
            body_file=f"manuscript/{episode_id}.txt",
            note_file=f"episode_notes/{episode_id}.txt",
        )
        chapter.episodes.append(episode)
        self.write_text(episode.body_file, "")
        self.write_text(episode.note_file, "")
        self.save_metadata()
        return episode

    def rename_episode(self, episode_id: str, title: str) -> None:
        episode = self.get_episode(episode_id)
        episode.title = title.strip() or episode.title
        self.save_metadata()

    def _delete_episode_files(self, episode: Episode) -> None:
        for relative in (episode.body_file, episode.note_file):
            path = self.root / relative
            if path.exists():
                path.unlink()

    def delete_episode(self, episode_id: str) -> None:
        chapter = self.find_episode_parent(episode_id)
        episode = self.get_episode(episode_id)
        self._delete_episode_files(episode)
        chapter.episodes = [item for item in chapter.episodes if item.id != episode_id]
        self.save_metadata()

    def reorder_structure(self, ordered: list[tuple[str, list[str]]]) -> None:
        chapter_map = {chapter.id: chapter for chapter in self.chapters}
        episode_map = {
            episode.id: episode
            for chapter in self.chapters
            for episode in chapter.episodes
        }
        chapter_ids = [chapter_id for chapter_id, _ in ordered]
        if set(chapter_ids) != set(chapter_map):
            raise ProjectError("章の並び替え情報が不正です。")
        episode_ids = [episode_id for _, ids in ordered for episode_id in ids]
        if len(episode_ids) != len(set(episode_ids)) or set(episode_ids) != set(episode_map):
            raise ProjectError("話の並び替え情報が不正です。")

        new_chapters: list[Chapter] = []
        for chapter_id, ids in ordered:
            chapter = chapter_map[chapter_id]
            chapter.episodes = [episode_map[episode_id] for episode_id in ids]
            new_chapters.append(chapter)
        self.chapters = new_chapters
        self.save_metadata()

    def read_text(self, relative_path: str) -> str:
        path = (self.root / relative_path).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ProjectContentError(
                f"作品フォルダ外のファイルは読み込めません: {relative_path}"
            ) from exc
        if not path.is_file():
            raise ProjectContentError(f"ファイルが見つかりません: {path}")
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ProjectContentError(
                f"ファイルを読み込めません: {path}: {exc}"
            ) from exc

    def write_text(self, relative_path: str, text: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        tmp.replace(path)

    def load_episode_body(self, episode_id: str) -> str:
        return self.read_text(self.get_episode(episode_id).body_file)

    def save_episode_body(self, episode_id: str, text: str) -> None:
        episode = self.get_episode(episode_id)
        self.write_text(episode.body_file, text)

    def load_episode_note(self, episode_id: str) -> str:
        return self.read_text(self.get_episode(episode_id).note_file)

    def save_episode_note(self, episode_id: str, text: str) -> None:
        episode = self.get_episode(episode_id)
        self.write_text(episode.note_file, text)

    def create_reference(self, category: str, title: str) -> Reference:
        if category not in REFERENCE_CATEGORIES:
            raise ProjectError("不明な資料カテゴリです。")
        ref_id = self._new_id("ref")
        ref = Reference(
            id=ref_id,
            category=category,
            title=title.strip() or "新しい資料",
            file=f"references/{ref_id}.txt",
        )
        self.references.append(ref)
        self.write_text(ref.file, "")
        self.save_metadata()
        return ref

    def get_reference(self, reference_id: str) -> Reference:
        for ref in self.references:
            if ref.id == reference_id:
                return ref
        raise ProjectError("資料が見つかりません。")

    def rename_reference(self, reference_id: str, title: str) -> None:
        ref = self.get_reference(reference_id)
        ref.title = title.strip() or ref.title
        self.save_metadata()

    def delete_reference(self, reference_id: str) -> None:
        ref = self.get_reference(reference_id)
        path = self.root / ref.file
        if path.exists():
            path.unlink()
        self.references = [item for item in self.references if item.id != reference_id]
        self.recent_references = [item for item in self.recent_references if item != reference_id]
        self.save_metadata()

    def load_reference(self, reference_id: str) -> str:
        ref = self.get_reference(reference_id)
        text = self.read_text(ref.file)
        if reference_id in self.recent_references:
            self.recent_references.remove(reference_id)
        self.recent_references.insert(0, reference_id)
        self.recent_references = self.recent_references[:20]
        self.save_metadata()
        return text

    def save_reference(self, reference_id: str, text: str) -> None:
        ref = self.get_reference(reference_id)
        self.write_text(ref.file, text)

    def recent_reference_items(self) -> list[Reference]:
        mapping = {ref.id: ref for ref in self.references}
        return [mapping[item] for item in self.recent_references if item in mapping]

    def create_plot_item(
        self,
        title: str,
        content: str = "",
        chapter_id: str | None = None,
        episode_id: str | None = None,
    ) -> PlotItem:
        item = PlotItem(
            id=self._new_id("plot"),
            title=title.strip() or "新しい展開",
            content=content,
            chapter_id=chapter_id,
            episode_id=episode_id,
        )
        self.plot_items.append(item)
        self.save_metadata()
        return item

    def get_plot_item(self, plot_id: str) -> PlotItem:
        for item in self.plot_items:
            if item.id == plot_id:
                return item
        raise ProjectError("展開が見つかりません。")

    def update_plot_item(
        self,
        plot_id: str,
        title: str,
        content: str,
        chapter_id: str | None,
        episode_id: str | None,
    ) -> None:
        item = self.get_plot_item(plot_id)
        item.title = title.strip() or item.title
        item.content = content
        item.chapter_id = chapter_id
        item.episode_id = episode_id
        self.save_metadata()

    def delete_plot_item(self, plot_id: str) -> None:
        self.get_plot_item(plot_id)
        self.plot_items = [item for item in self.plot_items if item.id != plot_id]
        self.save_metadata()

    def reorder_plot_items(self, ordered_ids: list[str]) -> None:
        mapping = {item.id: item for item in self.plot_items}
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(mapping):
            raise ProjectError("展開の並び替え情報が不正です。")
        self.plot_items = [mapping[item_id] for item_id in ordered_ids]
        self.save_metadata()

    def create_timeline_item(
        self, point: str, title: str, content: str = ""
    ) -> TimelineItem:
        item = TimelineItem(
            id=self._new_id("time"),
            point=point.strip(),
            title=title.strip() or "新しい時系列",
            content=content,
        )
        self.timeline_items.append(item)
        self.save_metadata()
        return item

    def get_timeline_item(self, timeline_id: str) -> TimelineItem:
        for item in self.timeline_items:
            if item.id == timeline_id:
                return item
        raise ProjectError("時系列が見つかりません。")

    def update_timeline_item(
        self, timeline_id: str, point: str, title: str, content: str
    ) -> None:
        item = self.get_timeline_item(timeline_id)
        item.point = point.strip()
        item.title = title.strip() or item.title
        item.content = content
        self.save_metadata()

    def delete_timeline_item(self, timeline_id: str) -> None:
        self.get_timeline_item(timeline_id)
        self.timeline_items = [
            item for item in self.timeline_items if item.id != timeline_id
        ]
        self.save_metadata()

    def reorder_timeline_items(self, ordered_ids: list[str]) -> None:
        mapping = {item.id: item for item in self.timeline_items}
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(mapping):
            raise ProjectError("時系列の並び替え情報が不正です。")
        self.timeline_items = [mapping[item_id] for item_id in ordered_ids]
        self.save_metadata()

    def search(self, query: str) -> list[SearchResult]:
        self.last_content_errors = []
        needle = query.strip().casefold()
        if not needle:
            return []
        results: list[SearchResult] = []

        def safe_read(relative_path: str) -> str:
            try:
                return self.read_text(relative_path)
            except ProjectContentError as exc:
                self.last_content_errors.append(exc)
                return ""

        def scan(kind: str, source_id: str, title: str, category: str, text: str) -> None:
            for line_no, line in enumerate(text.splitlines(), start=1):
                if needle in line.casefold():
                    results.append(
                        SearchResult(
                            kind=kind,
                            source_id=source_id,
                            title=title,
                            category=category,
                            line=line_no,
                            excerpt=line.strip()[:240],
                        )
                    )

        for chapter in self.chapters:
            for episode in chapter.episodes:
                scan(
                    "episode",
                    episode.id,
                    episode.title,
                    chapter.title,
                    safe_read(episode.body_file),
                )
                scan(
                    "episode_note",
                    episode.id,
                    f"{episode.title} / 話メモ",
                    chapter.title,
                    safe_read(episode.note_file),
                )
        for ref in self.references:
            scan(
                "reference",
                ref.id,
                ref.title,
                ref.category,
                f"{ref.title}\n{safe_read(ref.file)}",
            )
        for item in self.plot_items:
            related = self._plot_related_label(item)
            scan("plot", item.id, item.title, related, f"{item.title}\n{item.content}")
        for item in self.timeline_items:
            scan(
                "timeline",
                item.id,
                item.title,
                item.point,
                f"{item.title}\n{item.content}",
            )
        return results

    def _plot_related_label(self, item: PlotItem) -> str:
        chapter = next(
            (chapter for chapter in self.chapters if chapter.id == item.chapter_id), None
        )
        episode = next(
            (
                episode
                for chapter_item in self.chapters
                for episode in chapter_item.episodes
                if episode.id == item.episode_id
            ),
            None,
        )
        return " / ".join(
            label for label in (
                chapter.title if chapter else "",
                episode.title if episode else "",
            ) if label
        )

    def backup(self) -> Path:
        backup_dir = self.root / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / "latest"
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.copytree(self.root, backup_path, ignore=shutil.ignore_patterns("backups"))
        return backup_path
