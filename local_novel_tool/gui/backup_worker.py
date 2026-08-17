from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from local_novel_tool.core.backup import create_project_backup


class BackupWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, project_root: Path, backups_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.backups_root = backups_root

    @Slot()
    def run(self) -> None:
        try:
            destination = create_project_backup(
                self.project_root, self.backups_root
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(destination)
