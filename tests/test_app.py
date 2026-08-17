from pathlib import Path

from local_novel_tool import app as app_module


def test_application_icon_is_available_in_development() -> None:
    icon_path = app_module.application_icon_path()

    assert icon_path == Path("build_assets/app.ico").resolve()
    assert icon_path.stat().st_size > 0


def test_application_icon_prefers_standalone_resources(tmp_path, monkeypatch) -> None:
    executable = tmp_path / "LocalNovelTool.exe"
    icon_path = tmp_path / "resources" / "app.ico"
    icon_path.parent.mkdir()
    icon_path.write_bytes(Path("build_assets/app.ico").read_bytes())
    monkeypatch.setattr(app_module.sys, "executable", str(executable))

    assert app_module.application_icon_path() == icon_path
