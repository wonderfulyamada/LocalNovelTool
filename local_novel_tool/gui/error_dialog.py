from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget


def _error_parent(parent: QWidget | None) -> QWidget | None:
    """Return a window that can own an application error dialog."""
    if parent is not None:
        return parent.window()
    return QApplication.activeWindow()


def show_error(parent: QWidget | None, title: str, message: str) -> None:
    """Show a frontmost, application-modal error without changing app z-order."""
    window = _error_parent(parent)
    if window is not None:
        if window.isMinimized():
            window.showNormal()
        window.raise_()
        window.activateWindow()

    dialog = QMessageBox(QMessageBox.Icon.Critical, title, message, parent=window)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    dialog.exec()
