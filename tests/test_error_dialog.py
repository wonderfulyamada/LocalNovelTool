from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow

import local_novel_tool.gui.error_dialog as error_dialog
import local_novel_tool.gui.main_window as main_window_module


def test_error_dialog_is_parented_modal_and_temporarily_frontmost(monkeypatch) -> None:
    QApplication.instance() or QApplication([])
    window = QMainWindow()
    original_flags = window.windowFlags()
    calls: dict[str, object] = {}

    class FakeMessageBox:
        class Icon:
            Critical = object()

        def __init__(self, icon, title, message, parent=None) -> None:
            calls.update(icon=icon, title=title, message=message, parent=parent)

        def setWindowModality(self, modality) -> None:  # noqa: N802
            calls["modality"] = modality

        def setWindowFlag(self, flag, enabled=True) -> None:  # noqa: N802
            calls.setdefault("flags", []).append((flag, enabled))

        def exec(self) -> int:
            calls["executed"] = True
            return 0

    monkeypatch.setattr(error_dialog, "QMessageBox", FakeMessageBox)
    error_dialog.show_error(window, "保存失敗", "書き込めません")

    assert calls["parent"] is window
    assert calls["modality"] == Qt.WindowModality.ApplicationModal
    assert (Qt.WindowType.WindowStaysOnTopHint, True) in calls["flags"]
    assert calls["executed"] is True
    assert window.windowFlags() == original_flags
    window.close()


def test_project_load_failure_uses_shared_error_dialog(monkeypatch) -> None:
    shown: list[tuple[object, str, str]] = []
    window = SimpleNamespace(
        api=SimpleNamespace(
            open_project=lambda _root: (_ for _ in ()).throw(OSError("読込不可"))
        )
    )
    monkeypatch.setattr(
        main_window_module,
        "show_error",
        lambda parent, title, message: shown.append((parent, title, message)),
    )

    main_window_module.MainWindow._load_project(window, Path("invalid"))

    assert shown == [(window, "読込失敗", "読込不可")]
