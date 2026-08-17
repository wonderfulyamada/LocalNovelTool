from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget

import local_novel_tool.gui.preview_tab as preview_module
from local_novel_tool.gui.preview_tab import render_html


def test_horizontal_preview_preserves_mixed_japanese_text() -> None:
    source = "第一行。『括弧』とABC123\n第二行、終わり。"
    rendered = render_html(source)

    assert "<body>" in rendered
    assert 'class="vertical"' not in rendered
    assert "第一行。『括弧』とABC123<br>\n第二行、終わり。" in rendered


def test_vertical_preview_uses_vertical_rl_and_ruby() -> None:
    rendered = render_html("｜白雨《しらさめ》を抜いた。", vertical=True)

    assert 'class="vertical"' in rendered
    assert "writing-mode: vertical-rl" in rendered
    assert "<ruby>白雨<rt>しらさめ</rt></ruby>を抜いた。" in rendered


def test_preview_uses_configured_content_font_size_in_both_modes() -> None:
    assert "font-size: 21pt" in render_html("本文", font_size=21)
    assert "font-size: 21pt" in render_html("本文", vertical=True, font_size=21)


def test_preview_default_and_configured_sizes_are_explicit() -> None:
    assert "font-size: 14pt" in render_html("本文")


def test_preview_escapes_html_and_handles_empty_text() -> None:
    assert "<body></body>" in render_html("")
    rendered = render_html("<本文>&｜A1《えーわん》")
    assert "&lt;本文&gt;&amp;" in rendered
    assert "<ruby>A1<rt>えーわん</rt></ruby>" in rendered


def test_preview_tab_switches_writing_mode(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])

    class FakeWebView(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.rendered = ""

        def setHtml(self, rendered: str) -> None:  # noqa: N802
            self.rendered = rendered

    monkeypatch.setattr(preview_module, "QWebEngineView", FakeWebView)
    tab = preview_module.PreviewTab()
    tab.set_source_text("縦横｜白雨《しらさめ》\nABC123。『括弧』")

    assert tab.horizontal_button.isChecked()
    assert 'class="vertical"' not in tab.view.rendered

    tab.vertical_button.click()
    app.processEvents()
    assert tab.vertical_button.isChecked()
    assert 'class="vertical"' in tab.view.rendered
    assert "<ruby>白雨<rt>しらさめ</rt></ruby><br>" in tab.view.rendered
