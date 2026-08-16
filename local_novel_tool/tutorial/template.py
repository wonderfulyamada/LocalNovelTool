from __future__ import annotations

# Built-in source of truth for the v0.2.1 tutorial content.
TUTORIAL_PROJECT = {'format_version': 1,
 'title': 'LocalNovelTool チュートリアル',
 'chapters': [{'id': 'ch_927909f8738f',
               'title': 'まず触ってみよう',
               'episodes': [{'id': 'ep_c63ffb49978a',
                             'title': '本文を書いてみよう',
                             'body_file': 'manuscript/ep_c63ffb49978a.txt',
                             'note_file': 'episode_notes/ep_c63ffb49978a.txt'},
                            {'id': 'ep_c22ec88b6044',
                             'title': 'ルビとプレビュー',
                             'body_file': 'manuscript/ep_c22ec88b6044.txt',
                             'note_file': 'episode_notes/ep_c22ec88b6044.txt'},
                            {'id': 'ep_524b3cfa827d',
                             'title': '話メモを使おう',
                             'body_file': 'manuscript/ep_524b3cfa827d.txt',
                             'note_file': 'episode_notes/ep_524b3cfa827d.txt'},
                            {'id': 'ep_c1b48c8b40f2',
                             'title': '話を並べ替えてみよう',
                             'body_file': 'manuscript/ep_c1b48c8b40f2.txt',
                             'note_file': 'episode_notes/ep_c1b48c8b40f2.txt'}]},
              {'id': 'ch_9f49a95157c9',
               'title': '設定を整理しよう',
               'episodes': [{'id': 'ep_f7f320fdae0b',
                             'title': '資料を使おう',
                             'body_file': 'manuscript/ep_f7f320fdae0b.txt',
                             'note_file': 'episode_notes/ep_f7f320fdae0b.txt'},
                            {'id': 'ep_b91e0fc2c632',
                             'title': '展開を整理しよう',
                             'body_file': 'manuscript/ep_b91e0fc2c632.txt',
                             'note_file': 'episode_notes/ep_b91e0fc2c632.txt'},
                            {'id': 'ep_207c62d33433',
                             'title': '時系列を整理しよう',
                             'body_file': 'manuscript/ep_207c62d33433.txt',
                             'note_file': 'episode_notes/ep_207c62d33433.txt'},
                            {'id': 'ep_037e1b8a80a0',
                             'title': '文章検索を使おう',
                             'body_file': 'manuscript/ep_037e1b8a80a0.txt',
                             'note_file': 'episode_notes/ep_037e1b8a80a0.txt'}]},
              {'id': 'ch_d7518ff94181',
               'title': '練習用の章',
               'episodes': [{'id': 'ep_e33499cc5180',
                             'title': 'この話を動かしてみよう',
                             'body_file': 'manuscript/ep_e33499cc5180.txt',
                             'note_file': 'episode_notes/ep_e33499cc5180.txt'}]}],
 'references': [{'id': 'ref_d96af9993972',
                 'category': '登場人物',
                 'title': 'サンプル主人公',
                 'file': 'references/ref_d96af9993972.txt'},
                {'id': 'ref_526d374a4bb0',
                 'category': 'アイテム',
                 'title': '白雨',
                 'file': 'references/ref_526d374a4bb0.txt'},
                {'id': 'ref_99b40084f87a',
                 'category': '世界観',
                 'title': 'サンプルの町',
                 'file': 'references/ref_99b40084f87a.txt'},
                {'id': 'ref_dde2cfa0e2f6',
                 'category': 'その他',
                 'title': '自由メモの例',
                 'file': 'references/ref_dde2cfa0e2f6.txt'}],
 'recent_references': [],
 'plot_items': [{'id': 'plot_37c72ea3f7ac',
                 'title': '町へ到着',
                 'content': '主人公がサンプルの町へ到着する。',
                 'chapter_id': None,
                 'episode_id': None},
                {'id': 'plot_45047e46e58e',
                 'title': '事件に巻き込まれる',
                 'content': '町で起きた事件に主人公が巻き込まれる。',
                 'chapter_id': None,
                 'episode_id': None},
                {'id': 'plot_7ca02956d1c6',
                 'title': '犯人を追う',
                 'content': '白雨を手に、事件の犯人を追う。',
                 'chapter_id': None,
                 'episode_id': None}],
 'timeline_items': [{'id': 'time_db9c62d2da7a',
                     'point': '2年前',
                     'title': '主人公が故郷を出る',
                     'content': ''},
                    {'id': 'time_85901c5f1cc2', 'point': '半年前', 'title': '事件が発生', 'content': ''},
                    {'id': 'time_434c505c445b', 'point': '現在', 'title': '物語開始', 'content': ''}]}

TUTORIAL_TEXT_FILES = {'episode_notes/ep_037e1b8a80a0.txt': '',
 'episode_notes/ep_207c62d33433.txt': '',
 'episode_notes/ep_524b3cfa827d.txt': '* 次の場面で主人公に何をさせるか考える\n'
                                      '* 忘れたくない伏線をここへ書く\n'
                                      '* この下に自分のメモを一行追加してみる',
 'episode_notes/ep_b91e0fc2c632.txt': '',
 'episode_notes/ep_c1b48c8b40f2.txt': '',
 'episode_notes/ep_c22ec88b6044.txt': '',
 'episode_notes/ep_c63ffb49978a.txt': '',
 'episode_notes/ep_e33499cc5180.txt': '',
 'episode_notes/ep_f7f320fdae0b.txt': '',
 'manuscript/ep_037e1b8a80a0.txt': '「文章検索」は、本文・話メモ・資料・展開・時系列をまとめて検索します。\n'
                                   '\n'
                                   '【試してみよう】\n'
                                   '「白雨」で検索してください。本文と資料の結果が表示されます。結果を選び、元の項目へ移動できることも確認しましょう。',
 'manuscript/ep_207c62d33433.txt': '「時系列」タブでは、「2年前」「翌朝」など自由な時点で出来事を並べられます。本文の話順とは独立しています。\n'
                                   '\n'
                                   '【試してみよう】\n'
                                   '用意された3件を確認し、1件追加するかドラッグ＆ドロップで順番を変えてみましょう。',
 'manuscript/ep_524b3cfa827d.txt': '「話メモ」は、本文には書かない展開案や忘れたくないことを話ごとに残す場所です。\n'
                                   '\n'
                                   '【試してみよう】\n'
                                   '上の「話メモ」タブを開き、用意されているメモの下に一行追加してください。',
 'manuscript/ep_b91e0fc2c632.txt': '「展開」タブでは、物語で起きる出来事を本文の話順とは別に整理できます。章や話との関連付けも任意です。\n'
                                   '\n'
                                   '【試してみよう】\n'
                                   '用意された3件を選んで編集し、ドラッグ＆ドロップで順番を変えてみましょう。',
 'manuscript/ep_c1b48c8b40f2.txt': '左のツリーで章・話を選択できます。上部の「章追加」で章を、「話追加」で選択中の章に話を追加できます。\n'
                                   '\n'
                                   '【試してみよう】\n'
                                   '話をドラッグして順番を変えたり、別の章へ移動したりしてみましょう。章自体もドラッグで並べ替えられます。名前変更・削除は上部ボタンから操作できます。',
 'manuscript/ep_c22ec88b6044.txt': 'ルビは次のように入力します。\n'
                                   '\n'
                                   '｜白雨《しらさめ》\n'
                                   '\n'
                                   '【試してみよう】\n'
                                   '上の「プレビュー」タブを開き、白雨にルビが付くことを確認してください。「横書き」「縦書き」も切り替えてみましょう。',
 'manuscript/ep_c63ffb49978a.txt': '「本文」タブは、小説の文章を書く場所です。入力した内容は自動保存されます。\n'
                                   '\n'
                                   '【試してみよう】\n'
                                   'この下に一文書く → 左の別の話へ移動する → この話へ戻る、の順に操作して、文章が残っていることを確認してください。',
 'manuscript/ep_e33499cc5180.txt': 'この章と話は練習用です。\n'
                                   '左のツリーでこの話を別の章へドラッグしてみてください。\n'
                                   '章そのものもドラッグして順番を変えられます。\n'
                                   '不要になったら削除して構いません。',
 'manuscript/ep_f7f320fdae0b.txt': '「資料」タブには、登場人物・アイテム・世界観・その他の自由メモを置けます。\n'
                                   '\n'
                                   '【試してみよう】\n'
                                   '資料タブを開き、用意された4件を選んで内容を確認してください。自分で1件追加しても構いません。',
 'references/ref_526d374a4bb0.txt': '主人公が持つ刀。読みは「しらさめ」。',
 'references/ref_99b40084f87a.txt': '旅人が集まる小さな宿場町。最近、不思議な事件が起きている。',
 'references/ref_d96af9993972.txt': '町へ来たばかりの旅人。困っている人を放っておけない。',
 'references/ref_dde2cfa0e2f6.txt': '分類に迷った情報や、あとで整理したい断片を自由に置けます。'}
