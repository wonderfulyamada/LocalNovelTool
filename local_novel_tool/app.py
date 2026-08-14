from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def application_icon_path() -> Path | None:
    candidates = (
        Path(sys.executable).resolve().parent / "resources" / "app.ico",
        Path(__file__).resolve().parents[1] / "build_assets" / "app.ico",
    )
    return next((path for path in candidates if path.is_file()), None)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Local Novel Tool")
    app.setOrganizationName("WonderfulYamada")
    icon_path = application_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.setWindowIcon(app.windowIcon())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
