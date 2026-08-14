from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QSettings

from local_novel_tool.core.api import CoreAPI
from local_novel_tool.core.project import NovelProject

SAMPLE_INITIALIZED_KEY = "sample_project_initialized"
SAMPLE_PROJECT_TITLE = "LocalNovelTool チュートリアル"

TUTORIAL_CHAPTERS = (
    (
        "まず触ってみよう",
        (
            (
                "本文を書いてみよう",
                """「本文」タブは、小説の文章を書く場所です。入力した内容は自動保存されます。

【試してみよう】
この下に一文書く → 左の別の話へ移動する → この話へ戻る、の順に操作して、文章が残っていることを確認してください。""",
            ),
            (
                "ルビとプレビュー",
                """ルビは次のように入力します。

｜白雨《しらさめ》

【試してみよう】
上の「プレビュー」タブを開き、白雨にルビが付くことを確認してください。「横書き」「縦書き」も切り替えてみましょう。""",
            ),
            (
                "話メモを使おう",
                """「話メモ」は、本文には書かない展開案や忘れたくないことを話ごとに残す場所です。

【試してみよう】
上の「話メモ」タブを開き、用意されているメモの下に一行追加してください。""",
            ),
            (
                "話を並べ替えてみよう",
                """左側には章と話のツリーがあります。話はドラッグ＆ドロップで並べ替えたり、別の章へ移動できます。

【試してみよう】
この話を上下へ動かすか、「設定を整理しよう」の章へ移動してから、元の場所へ戻してみましょう。""",
            ),
        ),
    ),
    (
        "設定を整理しよう",
        (
            (
                "資料を使おう",
                """「資料」タブには、登場人物・アイテム・世界観・その他の自由メモを置けます。

【試してみよう】
資料タブを開き、用意された4件を選んで内容を確認してください。自分で1件追加しても構いません。""",
            ),
            (
                "展開を整理しよう",
                """「展開」タブでは、物語で起きる出来事を本文の話順とは別に整理できます。章や話との関連付けも任意です。

【試してみよう】
用意された3件を選んで編集し、ドラッグ＆ドロップで順番を変えてみましょう。""",
            ),
            (
                "時系列を整理しよう",
                """「時系列」タブでは、「2年前」「翌朝」など自由な時点で出来事を並べられます。本文の話順とは独立しています。

【試してみよう】
用意された3件を確認し、1件追加するかドラッグ＆ドロップで順番を変えてみましょう。""",
            ),
            (
                "文章検索を使おう",
                """「文章検索」は、本文・話メモ・資料・展開・時系列をまとめて検索します。

【試してみよう】
「白雨」で検索してください。本文と資料の結果が表示されます。結果を選び、元の項目へ移動できることも確認しましょう。""",
            ),
        ),
    ),
)

TUTORIAL_NOTE = """* 次の場面で主人公に何をさせるか考える
* 忘れたくない伏線をここへ書く
* この下に自分のメモを一行追加してみる"""

SAMPLE_REFERENCES = (
    ("登場人物", "サンプル主人公", "町へ来たばかりの旅人。困っている人を放っておけない。"),
    ("アイテム", "白雨", "主人公が持つ刀。読みは「しらさめ」。"),
    ("世界観", "サンプルの町", "旅人が集まる小さな宿場町。最近、不思議な事件が起きている。"),
    ("その他", "自由メモの例", "分類に迷った情報や、あとで整理したい断片を自由に置けます。"),
)

SAMPLE_PLOTS = (
    ("町へ到着", "主人公がサンプルの町へ到着する。"),
    ("事件に巻き込まれる", "町で起きた事件に主人公が巻き込まれる。"),
    ("犯人を追う", "白雨を手に、事件の犯人を追う。"),
)
SAMPLE_TIMELINE = (
    ("2年前", "主人公が故郷を出る", ""),
    ("半年前", "事件が発生", ""),
    ("現在", "物語開始", ""),
)


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
        episodes = {}
        for chapter_title, episode_items in TUTORIAL_CHAPTERS:
            chapter = api.create_chapter(chapter_title)
            for episode_title, body in episode_items:
                episode = api.create_episode(chapter.id, episode_title)
                api.save_episode_body(episode.id, body)
                episodes[episode_title] = episode
        api.save_episode_note(episodes["話メモを使おう"].id, TUTORIAL_NOTE)

        for category, title, content in SAMPLE_REFERENCES:
            reference = api.create_reference(category, title)
            api.save_reference(reference.id, content)

        for title, content in SAMPLE_PLOTS:
            api.create_plot_item(title, content)
        for point, title, content in SAMPLE_TIMELINE:
            api.create_timeline_item(point, title, content)

        settings.setValue(SAMPLE_INITIALIZED_KEY, True)
        settings.sync()
        return project
    except Exception:
        api.project = previous_project
        if sample_root is not None and sample_root.exists():
            shutil.rmtree(sample_root)
        raise
