from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QSettings

from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.project import NovelProject

SAMPLE_INITIALIZED_KEY = "sample_project_initialized"
SAMPLE_PROJECT_TITLE = "LocalNovelTool サンプル"

WELCOME_BODY = """LocalNovelToolへようこそ。

このソフトは、小説を書きながら「次の展開どうするんだっけ？」「この設定どこに書いたっけ？」をすぐ確認するための、シンプルなローカル執筆ツールです。

左側には章と話が並びます。
話を選ぶと、この「本文」タブで文章を編集できます。

文章は自動保存されるので、基本的に保存ボタンを気にする必要はありません。

ルビは、たとえば

｜白雨《しらさめ》

のように入力できます。

「プレビュー」タブでは、ルビを反映した状態で文章を確認できます。
横書きと縦書きも切り替えられます。

このサンプル作品は自由に編集・削除してください。"""

TABS_BODY = """上にあるタブを切り替えて、各機能を試してみてください。

「話メモ」には、その話で書きたい展開や忘れたくない内容を残せます。

「文章検索」では、本文や資料から言葉を横断検索できます。

「資料」には、登場人物やアイテム、世界観などを保存できます。

「展開」と「時系列」では、物語の流れを本文とは別に確認できます。

左側の話はドラッグ＆ドロップで並び替えたり、別の章へ移動したりできます。

この第2話を動かして試してみるのもおすすめです。"""

WELCOME_NOTE = """* このタブは話ごとの展開メモに使えます
* 箇条書きでも文章でも自由
* 本文を書きながら「次に何を書くか」を置いておく用途を想定"""

SAMPLE_REFERENCES = (
    ("登場人物", "サンプル主人公", "資料タブでは登場人物の設定などを自由に保存できます。"),
    ("アイテム", "サンプルアイテム", "作中に登場する道具や持ち物のメモを置けます。"),
    ("世界観", "サンプル世界", "場所、組織、能力、用語など、本文とは別に確認したい情報を置けます。"),
    ("その他", "使い方メモ", "分類に迷った情報はここへ置けます。"),
)

SAMPLE_PLOT = (
    "サンプル作品を書く",
    "各タブを試したあと、自分の作品を作ってみましょう。",
)
SAMPLE_TIMELINE = ("現在", "LocalNovelToolを使い始める")


def initialize_sample_project(
    api: CoreAPI, settings: QSettings, parent: Path
) -> NovelProject | None:
    if settings.value(SAMPLE_INITIALIZED_KEY, False, bool):
        return None

    parent.mkdir(parents=True, exist_ok=True)
    previous_project = api.project
    sample_root: Path | None = None
    try:
        project = api.create_project(parent, SAMPLE_PROJECT_TITLE)
        sample_root = project.root
        chapter = api.create_chapter("はじめに")
        welcome = api.create_episode(chapter.id, "ようこそ")
        tabs = api.create_episode(chapter.id, "各タブを試してみる")
        api.save_episode_body(welcome.id, WELCOME_BODY)
        api.save_episode_body(tabs.id, TABS_BODY)
        api.save_episode_note(welcome.id, WELCOME_NOTE)

        for category, title, content in SAMPLE_REFERENCES:
            reference = api.create_reference(category, title)
            api.save_reference(reference.id, content)

        api.create_plot_item(SAMPLE_PLOT[0], SAMPLE_PLOT[1])
        api.create_timeline_item(SAMPLE_TIMELINE[0], SAMPLE_TIMELINE[1])

        settings.setValue(SAMPLE_INITIALIZED_KEY, True)
        settings.sync()
        return project
    except Exception:
        api.project = previous_project
        if sample_root is not None and sample_root.exists():
            shutil.rmtree(sample_root)
        raise
