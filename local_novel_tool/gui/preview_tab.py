from __future__ import annotations

import html
import re

from PySide6.QtWidgets import QHBoxLayout, QRadioButton, QTextBrowser, QVBoxLayout, QWidget

RUBY_PATTERN = re.compile(r"｜([^《》\n]+)《([^《》\n]+)》")

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # 配布構成でWebEngineを外した場合のフォールバック
    QWebEngineView = None


def render_html(text: str, vertical: bool = False, font_size: int = 14) -> str:
    parts: list[str] = []
    pos = 0
    for match in RUBY_PATTERN.finditer(text):
        parts.append(html.escape(text[pos:match.start()]))
        base = html.escape(match.group(1))
        reading = html.escape(match.group(2))
        parts.append(f"<ruby>{base}<rt>{reading}</rt></ruby>")
        pos = match.end()
    parts.append(html.escape(text[pos:]))
    body = "".join(parts).replace("\n", "<br>\n")
    body_class = ' class="vertical"' if vertical else ""
    return f"""<!doctype html>
<html lang=\"ja\"><head><meta charset=\"utf-8\">
<style>
body {{ font-family: sans-serif; font-size: {font_size}pt; line-height: 2.0; padding: 24px; white-space: normal; }}
body.vertical {{ writing-mode: vertical-rl; text-orientation: mixed; height: calc(100vh - 48px); overflow-x: auto; overflow-y: hidden; box-sizing: border-box; }}
rt {{ font-size: 0.55em; }}
</style></head><body{body_class}>{body}</body></html>"""


class PreviewTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._source_text = ""
        self._content_font_size = 14
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        writing_controls = QHBoxLayout()
        writing_controls.setContentsMargins(6, 6, 6, 0)
        self.horizontal_button = QRadioButton("横書き")
        self.vertical_button = QRadioButton("縦書き")
        self.horizontal_button.setChecked(True)
        writing_controls.addWidget(self.horizontal_button)
        writing_controls.addWidget(self.vertical_button)
        writing_controls.addStretch(1)
        layout.addLayout(writing_controls)

        if QWebEngineView is not None:
            self.view = QWebEngineView()
            self._webengine = True
        else:
            self.view = QTextBrowser()
            self._webengine = False
        layout.addWidget(self.view)
        self.horizontal_button.toggled.connect(self._writing_mode_changed)

    def set_source_text(self, text: str) -> None:
        self._source_text = text
        self._render()

    def set_content_font_size(self, size: int) -> None:
        self._content_font_size = size
        self._render()

    def _writing_mode_changed(self, _checked: bool) -> None:
        self._render()

    def _render(self) -> None:
        if self._webengine:
            self.view.setHtml(render_html(self._source_text, self.vertical_button.isChecked(), self._content_font_size))
        else:
            fallback = RUBY_PATTERN.sub(
                lambda m: f"{m.group(1)}《{m.group(2)}》", self._source_text
            )
            self.view.setPlainText(fallback)
