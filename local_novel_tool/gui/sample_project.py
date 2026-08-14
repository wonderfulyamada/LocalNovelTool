from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

from PySide6.QtCore import QSettings

from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.project import NovelProject

SAMPLE_INITIALIZED_KEY = "sample_project_initialized"
SAMPLE_PROJECT_TITLE = "LocalNovelTool チュートリアル"


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
