from __future__ import annotations

import html
import re

from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

RUBY_PATTERN = re.compile(r"｜([^《》\n]+)《([^《》\n]+)》")

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # 配布構成でWebEngineを外した場合のフォールバック
    QWebEngineView = None


def render_html(text: str) -> str:
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
    return f"""<!doctype html>
<html lang=\"ja\"><head><meta charset=\"utf-8\">
<style>
body {{ font-family: sans-serif; font-size: 18px; line-height: 2.0; padding: 24px; white-space: normal; }}
rt {{ font-size: 0.55em; }}
</style></head><body>{body}</body></html>"""


class PreviewTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if QWebEngineView is not None:
            self.view = QWebEngineView()
            self._webengine = True
        else:
            self.view = QTextBrowser()
            self._webengine = False
        layout.addWidget(self.view)

    def set_source_text(self, text: str) -> None:
        if self._webengine:
            self.view.setHtml(render_html(text))
        else:
            fallback = RUBY_PATTERN.sub(lambda m: f"{m.group(1)}《{m.group(2)}》", text)
            self.view.setPlainText(fallback)
