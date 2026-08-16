from __future__ import annotations

import copy
import json
import shutil
import uuid
from pathlib import Path

from .template import TUTORIAL_PROJECT, TUTORIAL_TEXT_FILES


def tutorial_snapshot(root: Path) -> tuple[dict, dict[str, bytes]]:
    metadata = json.loads((root / "project.json").read_text(encoding="utf-8"))
    metadata.pop("recent_references", None)
    content_paths: set[str] = set()
    for chapter in metadata.get("chapters", []):
        for episode in chapter.get("episodes", []):
            content_paths.add(str(episode["body_file"]))
            content_paths.add(str(episode["note_file"]))
    for reference in metadata.get("references", []):
        content_paths.add(str(reference["file"]))
    return metadata, {
        relative: (root / relative).read_bytes() for relative in sorted(content_paths)
    }


def template_snapshot() -> tuple[dict, dict[str, bytes]]:
    metadata = copy.deepcopy(TUTORIAL_PROJECT)
    metadata.pop("recent_references", None)
    return metadata, {
        path: text.encode("utf-8") for path, text in sorted(TUTORIAL_TEXT_FILES.items())
    }


def tutorial_matches_template(root: Path) -> bool:
    try:
        return tutorial_snapshot(root.resolve()) == template_snapshot()
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def generate_tutorial(destination: Path) -> Path:
    """Atomically generate a complete normal project from the built-in template."""
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    staged = destination.parent / f".tutorial-generate-{uuid.uuid4().hex}"
    try:
        staged.mkdir()
        project_text = json.dumps(TUTORIAL_PROJECT, ensure_ascii=False, indent=2)
        (staged / "project.json").write_bytes(project_text.encode("utf-8"))
        for relative, text in TUTORIAL_TEXT_FILES.items():
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        if not tutorial_matches_template(staged):
            raise OSError("生成したチュートリアルを検証できませんでした。")
        staged.rename(destination)
        return destination
    except Exception:
        if staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
        raise
