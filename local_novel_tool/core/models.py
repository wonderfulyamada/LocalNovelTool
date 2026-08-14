from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Episode:
    id: str
    title: str
    body_file: str
    note_file: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Episode":
        return cls(**data)


@dataclass
class Chapter:
    id: str
    title: str
    episodes: list[Episode]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "episodes": [episode.to_dict() for episode in self.episodes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chapter":
        return cls(
            id=data["id"],
            title=data["title"],
            episodes=[Episode.from_dict(item) for item in data.get("episodes", [])],
        )


@dataclass
class Reference:
    id: str
    category: str
    title: str
    file: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Reference":
        return cls(**data)


@dataclass
class PlotItem:
    id: str
    title: str
    content: str
    chapter_id: str | None = None
    episode_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlotItem":
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            content=data.get("content", ""),
            chapter_id=data.get("chapter_id"),
            episode_id=data.get("episode_id"),
        )


@dataclass
class TimelineItem:
    id: str
    point: str
    title: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineItem":
        return cls(
            id=data["id"],
            point=data.get("point", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
        )


@dataclass
class SearchResult:
    kind: str
    source_id: str
    title: str
    category: str
    line: int
    excerpt: str
