from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtWidgets import QDialog

import local_novel_tool.gui.main_window as main_window_module


def make_settings(path: Path) -> QSettings:
    return QSettings(str(path / "settings.ini"), QSettings.Format.IniFormat)


def make_window(settings: QSettings, root: Path, root_available: bool = True):
    calls: list[str] = []
    window = SimpleNamespace(
        settings=settings,
        api=SimpleNamespace(project=None),
        _ensure_projects_root_available=lambda: root_available,
        _default_projects_parent=lambda: root,
        _set_projects_parent=lambda _root: calls.append("set_root"),
        _after_project_loaded=lambda: calls.append("loaded"),
        _tutorial_parent=lambda: root.parent / "tutorial",
        _try_open_last_project=lambda: calls.append("last_project"),
    )
    return window, calls


class FakeFirstLaunchDialog:
    responses: list[object] = []
    roots: list[Path] = []
    created = 0

    def __init__(self, *_args, **_kwargs) -> None:
        type(self).created += 1

    def exec(self):
        return type(self).responses.pop(0)

    def selected_root(self) -> Path:
        return type(self).roots.pop(0)


def configure_dialog(responses: list[object], roots: list[Path]) -> None:
    FakeFirstLaunchDialog.responses = responses
    FakeFirstLaunchDialog.roots = roots
    FakeFirstLaunchDialog.created = 0


@pytest.mark.parametrize("completed", [None, False])
def test_missing_or_false_flag_shows_initial_setup(
    tmp_path: Path, monkeypatch, completed: bool | None
) -> None:
    settings = make_settings(tmp_path)
    if completed is not None:
        settings.setValue(main_window_module.INITIAL_SETUP_COMPLETED_KEY, completed)
    window, _calls = make_window(settings, tmp_path / "作品")
    configure_dialog([QDialog.DialogCode.Rejected], [])
    monkeypatch.setattr(main_window_module, "FirstLaunchDialog", FakeFirstLaunchDialog)

    main_window_module.MainWindow._try_open_initial_project(window)

    assert FakeFirstLaunchDialog.created == 1
    assert not settings.value(main_window_module.INITIAL_SETUP_COMPLETED_KEY, False, bool)


def test_successful_setup_marks_flag_only_after_tutorial_load(
    tmp_path: Path, monkeypatch
) -> None:
    settings = make_settings(tmp_path)
    root = (tmp_path / "作品").resolve()
    window, calls = make_window(settings, root)
    project = SimpleNamespace(root=root / "LocalNovelTool チュートリアル")
    configure_dialog([QDialog.DialogCode.Accepted], [root])
    monkeypatch.setattr(main_window_module, "FirstLaunchDialog", FakeFirstLaunchDialog)

    def create_tutorial(api, _settings, selected_root):
        assert not settings.value(main_window_module.INITIAL_SETUP_COMPLETED_KEY, False, bool)
        assert selected_root == root
        api.project = project
        return project

    monkeypatch.setattr(main_window_module, "initialize_sample_project", create_tutorial)

    main_window_module.MainWindow._try_open_initial_project(window)

    assert settings.value(main_window_module.INITIAL_SETUP_COMPLETED_KEY, False, bool)
    assert calls == ["set_root", "loaded"]


@pytest.mark.parametrize("result", ["generation_failure", "load_failure"])
def test_setup_failure_keeps_flag_false_and_can_cancel_retry(
    tmp_path: Path, monkeypatch, result: str
) -> None:
    settings = make_settings(tmp_path)
    root = (tmp_path / "作品").resolve()
    window, calls = make_window(settings, root)
    configure_dialog(
        [QDialog.DialogCode.Accepted, QDialog.DialogCode.Rejected], [root]
    )
    errors: list[str] = []
    monkeypatch.setattr(main_window_module, "FirstLaunchDialog", FakeFirstLaunchDialog)
    monkeypatch.setattr(
        main_window_module, "show_error", lambda _parent, _title, text: errors.append(text)
    )
    if result == "generation_failure":
        monkeypatch.setattr(
            main_window_module,
            "initialize_sample_project",
            lambda *_args: (_ for _ in ()).throw(OSError("生成失敗")),
        )
    else:
        monkeypatch.setattr(
            main_window_module, "initialize_sample_project", lambda *_args: None
        )

    main_window_module.MainWindow._try_open_initial_project(window)

    assert not settings.value(main_window_module.INITIAL_SETUP_COMPLETED_KEY, False, bool)
    assert calls == []
    assert errors
    assert FakeFirstLaunchDialog.created == 2


def test_completed_flag_skips_onboarding(tmp_path: Path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    settings.setValue(main_window_module.INITIAL_SETUP_COMPLETED_KEY, True)
    window, calls = make_window(settings, tmp_path / "作品")
    monkeypatch.setattr(
        main_window_module,
        "FirstLaunchDialog",
        lambda *_args: pytest.fail("onboarding should be skipped"),
    )
    monkeypatch.setattr(main_window_module, "initialize_sample_project", lambda *_args: None)

    main_window_module.MainWindow._try_open_initial_project(window)

    assert calls == ["last_project"]


def test_completed_flag_with_missing_root_skips_onboarding(
    tmp_path: Path, monkeypatch
) -> None:
    settings = make_settings(tmp_path)
    settings.setValue(main_window_module.INITIAL_SETUP_COMPLETED_KEY, True)
    window, calls = make_window(settings, tmp_path / "missing", root_available=False)
    monkeypatch.setattr(
        main_window_module,
        "FirstLaunchDialog",
        lambda *_args: pytest.fail("missing root must not start onboarding"),
    )

    main_window_module.MainWindow._try_open_initial_project(window)

    assert calls == []


def test_existing_portable_sample_flag_migrates_to_initial_setup_flag(tmp_path: Path) -> None:
    application_root = tmp_path / "app"
    application_root.mkdir()
    settings = QSettings(str(application_root / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue(main_window_module.SAMPLE_INITIALIZED_KEY, True)
    settings.sync()

    migrated = main_window_module.MainWindow._load_portable_settings(
        SimpleNamespace(application_root=application_root)
    )

    assert migrated.value(main_window_module.INITIAL_SETUP_COMPLETED_KEY, False, bool)


def test_legacy_initialized_user_migrates_to_initial_setup_flag(
    tmp_path: Path, monkeypatch
) -> None:
    application_root = tmp_path / "app"
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    legacy = QSettings(str(legacy_root / "settings.ini"), QSettings.Format.IniFormat)
    legacy.setValue(main_window_module.SAMPLE_INITIALIZED_KEY, True)
    legacy.sync()

    class FakePaths:
        StandardLocation = QStandardPaths.StandardLocation

        @staticmethod
        def writableLocation(_location):
            return str(legacy_root)

    monkeypatch.setattr(main_window_module, "QStandardPaths", FakePaths)

    migrated = main_window_module.MainWindow._load_portable_settings(
        SimpleNamespace(application_root=application_root)
    )

    assert migrated.value(main_window_module.SAMPLE_INITIALIZED_KEY, False, bool)
    assert migrated.value(main_window_module.INITIAL_SETUP_COMPLETED_KEY, False, bool)


def test_clean_portable_settings_has_no_initial_setup_flag(
    tmp_path: Path, monkeypatch
) -> None:
    application_root = tmp_path / "app"
    application_root.mkdir()
    legacy_root = tmp_path / "empty-legacy"

    class FakePaths:
        StandardLocation = QStandardPaths.StandardLocation

        @staticmethod
        def writableLocation(_location):
            return str(legacy_root)

    monkeypatch.setattr(main_window_module, "QStandardPaths", FakePaths)
    settings = main_window_module.MainWindow._load_portable_settings(
        SimpleNamespace(application_root=application_root)
    )

    assert not settings.contains(main_window_module.INITIAL_SETUP_COMPLETED_KEY)
