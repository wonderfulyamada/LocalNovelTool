from pathlib import Path

import pytest

from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.project import ProjectError


def test_create_save_search_and_reorder(tmp_path: Path) -> None:
    api = CoreAPI()
    project = api.create_project(tmp_path, "作品 日本語")
    assert project.root == (tmp_path / "作品 日本語").resolve()
    assert (project.root / "project.json").is_file()
    for folder in ("manuscript", "episode_notes", "references", "backups"):
        assert (project.root / folder).is_dir()
    ch1 = api.create_chapter("第一章")
    ch2 = api.create_chapter("第二章")
    ep1 = api.create_episode(ch1.id, "第一話")
    ep2 = api.create_episode(ch1.id, "第二話")
    api.save_episode_body(ep1.id, "｜白雨《しらさめ》を抜いた。")
    api.save_episode_note(ep2.id, "次は港へ行く")
    ref = api.create_reference("登場人物", "クイナ")
    api.save_reference(ref.id, "愛刀は白雨")

    hits = api.search("白雨")
    assert len(hits) == 2

    api.reorder_structure([
        (ch2.id, [ep2.id]),
        (ch1.id, [ep1.id]),
    ])
    assert api.chapters()[0].id == ch2.id
    assert api.chapters()[0].episodes[0].id == ep2.id

    reopened = CoreAPI()
    reopened.open_project(tmp_path / "作品 日本語")
    assert reopened.load_episode_body(ep1.id) == "｜白雨《しらさめ》を抜いた。"
    assert reopened.chapters()[0].episodes[0].id == ep2.id


def test_create_project_refuses_existing_same_name_folder(tmp_path: Path) -> None:
    existing = tmp_path / "同名 作品"
    existing.mkdir()
    marker = existing / "消してはいけない.txt"
    marker.write_text("既存データ", encoding="utf-8")

    api = CoreAPI()
    with pytest.raises(ProjectError, match="同名のフォルダ"):
        api.create_project(tmp_path, "同名 作品")

    assert marker.read_text(encoding="utf-8") == "既存データ"
    assert not (existing / "project.json").exists()


@pytest.mark.parametrize(
    "title", ["", "../作品", "作品/別名", "作品\\別名", "CON", "作品\x01名"]
)
def test_create_project_rejects_invalid_folder_names(tmp_path: Path, title: str) -> None:
    with pytest.raises(ProjectError):
        CoreAPI().create_project(tmp_path, title)


def test_search_keeps_existing_scope_order_lines_and_excerpts(tmp_path: Path) -> None:
    api = CoreAPI()
    api.create_project(tmp_path, "検索順序")
    chapter = api.create_chapter("章")
    first = api.create_episode(chapter.id, "一話")
    second = api.create_episode(chapter.id, "二話")
    api.save_episode_body(first.id, "前置き\nNeedle 本文一")
    api.save_episode_note(first.id, "needle メモ一")
    api.save_episode_body(second.id, "NEEDLE 本文二")
    api.save_episode_note(second.id, "前置き\nneedle メモ二")
    reference = api.create_reference("世界観", "資料")
    api.save_reference(reference.id, "needle 資料")
    plot = api.create_plot_item("展開", "needle プロット")
    timeline = api.create_timeline_item("一日目", "時系列", "needle 時系列")

    results = api.search("nEeDlE")

    assert [(item.kind, item.source_id, item.line) for item in results] == [
        ("episode", first.id, 2),
        ("episode_note", first.id, 1),
        ("episode", second.id, 1),
        ("episode_note", second.id, 2),
        ("reference", reference.id, 2),
        ("plot", plot.id, 2),
        ("timeline", timeline.id, 2),
    ]
    assert [item.excerpt for item in results] == [
        "Needle 本文一",
        "needle メモ一",
        "NEEDLE 本文二",
        "needle メモ二",
        "needle 資料",
        "needle プロット",
        "needle 時系列",
    ]
