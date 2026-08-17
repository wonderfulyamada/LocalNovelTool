from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any


CURRENT_FORMAT_VERSION = 1
LEGACY_FORMAT_VERSION = 1


class FormatVersionError(ValueError):
    pass


Migration = Callable[[dict[str, Any]], dict[str, Any]]
MIGRATIONS: dict[int, Migration] = {}


def detect_format_version(data: dict[str, Any]) -> int:
    """Return the stored version, treating pre-version projects as v1."""
    raw_version = data.get("format_version", LEGACY_FORMAT_VERSION)
    if isinstance(raw_version, bool):
        raise FormatVersionError("format_version が不正です。")
    if isinstance(raw_version, int):
        version = raw_version
    elif isinstance(raw_version, str) and raw_version.strip().isdigit():
        version = int(raw_version)
    else:
        raise FormatVersionError("format_version が不正です。")
    if version < 1:
        raise FormatVersionError("format_version が不正です。")
    return version


def migrate_project_data(
    data: dict[str, Any],
    *,
    backup_before_migration: Callable[[], object] | None = None,
) -> dict[str, Any]:
    """Validate and migrate project metadata without mutating the input mapping.

    A future migration must be registered under its source version. Before the
    first conversion, the supplied callback is run so callers can use the
    existing complete-project backup API.
    """
    version = detect_format_version(data)
    if version > CURRENT_FORMAT_VERSION:
        raise FormatVersionError(
            "未対応の作品データ形式です。"
            f" (format_version={version}, 対応={CURRENT_FORMAT_VERSION})"
        )
    if version == CURRENT_FORMAT_VERSION:
        return data

    migrated = copy.deepcopy(data)
    backed_up = False
    while version < CURRENT_FORMAT_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise FormatVersionError(
                f"format_version {version} からの移行処理がありません。"
            )
        if not backed_up:
            if backup_before_migration is None:
                raise FormatVersionError(
                    "データ移行前のバックアップを作成できません。"
                )
            backup_before_migration()
            backed_up = True
        migrated = migration(migrated)
        next_version = detect_format_version(migrated)
        if next_version != version + 1:
            raise FormatVersionError("移行処理後のformat_versionが不正です。")
        version = next_version
    return migrated
