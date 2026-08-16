from __future__ import annotations

import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings

from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.project import NovelProject

SAMPLE_INITIALIZED_KEY = "sample_project_initialized"
SAMPLE_PROJECT_TITLE = "LocalNovelTool チュートリアル"
SAVED_TUTORIAL_TITLE = f"{SAMPLE_PROJECT_TITLE} - 保存"


def tutorial_resource_path() -> Path:
    candidates = (
        Path(sys.executable).resolve().parent / "resources" / "tutorial",
        Path(__file__).resolve().parents[2] / "resources" / "tutorial",
    )
    for candidate in candidates:
        if (candidate / "project.json").is_file():
            return candidate
    raise FileNotFoundError("同梱チュートリアルが見つかりません。")


def initialize_sample_project(
    api: CoreAPI,
    settings: QSettings,
    parent: Path,
    source: Path | None = None,
) -> NovelProject | None:
    if settings.value(SAMPLE_INITIALIZED_KEY, False, bool):
        return None

    parent.mkdir(parents=True, exist_ok=True)
    previous_project = api.project
    target = parent / SAMPLE_PROJECT_TITLE
    copied = False
    try:
        shutil.copytree(source or tutorial_resource_path(), target)
        copied = True
        project = api.open_project(target)
        settings.setValue(SAMPLE_INITIALIZED_KEY, True)
        settings.sync()
        return project
    except Exception:
        api.project = previous_project
        if copied and target.exists():
            shutil.rmtree(target)
        raise


def archive_tutorial_project(
    tutorial_root: Path,
    projects_root: Path,
    saved_at: datetime | None = None,
) -> Path:
    """Copy a tutorial to a new, collision-free user project folder."""
    tutorial_root = tutorial_root.resolve()
    projects_root = projects_root.resolve()
    if not (tutorial_root / "project.json").is_file():
        raise FileNotFoundError("保存するチュートリアルが見つかりません。")
    if projects_root == tutorial_root or projects_root.is_relative_to(tutorial_root):
        raise ValueError("チュートリアルの中は保存先に指定できません。")
    projects_root.mkdir(parents=True, exist_ok=True)
    if not projects_root.is_dir():
        raise NotADirectoryError("作品の保存フォルダが無効です。")

    timestamp = (saved_at or datetime.now()).strftime("%Y-%m-%d %H%M")
    base_name = f"{SAVED_TUTORIAL_TITLE} {timestamp}"
    number = 1
    while True:
        name = base_name if number == 1 else f"{base_name} ({number})"
        destination = projects_root / name
        try:
            shutil.copytree(tutorial_root, destination)
            break
        except FileExistsError:
            number += 1
        except Exception:
            if destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            raise

    source_manifest = {
        (path.relative_to(tutorial_root), path.stat().st_size)
        for path in tutorial_root.rglob("*")
        if path.is_file()
    }
    destination_manifest = {
        (path.relative_to(destination), path.stat().st_size)
        for path in destination.rglob("*")
        if path.is_file()
    }
    if source_manifest != destination_manifest:
        shutil.rmtree(destination, ignore_errors=True)
        raise OSError("チュートリアルの退避コピーを確認できませんでした。")
    return destination


def recreate_tutorial_project(
    api: CoreAPI, parent: Path, source: Path | None = None
) -> NovelProject:
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / SAMPLE_PROJECT_TITLE
    suffix = uuid.uuid4().hex
    staged = parent / f".tutorial-new-{suffix}"
    backup = parent / f".tutorial-old-{suffix}"
    previous_project = api.project
    replaced_existing = False
    installed_new = False

    try:
        shutil.copytree(source or tutorial_resource_path(), staged)
        if target.exists():
            target.rename(backup)
            replaced_existing = True
        staged.rename(target)
        installed_new = True
        project = api.open_project(target)
        if backup.exists():
            shutil.rmtree(backup)
        return project
    except Exception:
        api.project = previous_project
        if installed_new and target.exists():
            shutil.rmtree(target)
        if replaced_existing and backup.exists():
            backup.rename(target)
        if staged.exists():
            shutil.rmtree(staged)
        raise
