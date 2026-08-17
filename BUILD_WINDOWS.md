# Windows folder build

正式配布は `pyside6-deploy` の `standalone` モードを使う。

1. x64版Pythonで仮想環境を作成する。
2. `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` を実行する。
3. `.\.venv\Scripts\python.exe -m pytest -q` を実行する。
4. `.\build_windows.ps1` を実行する。
5. `dist\LocalNovelTool_v0.2.1` をZIP化する。

`pysidedeploy.spec` は `standalone` モードで保存済み。ビルドスクリプトは
`pyside6-deploy` を実行後、README、ライセンス表記、`resources/tutorial`を
完成フォルダへ同梱する。

確認項目:
- Python未導入PCで起動
- ネット切断状態で起動・保存・再読込
- Windowsユーザー名が日本語
- 作品フォルダ名が日本語
- パスに空白を含む
- 別章への話のD&D移動
- 自動保存後に強制終了しても直前の保存内容が残る
- ルビプレビュー
- 展開・時系列
- 横断検索
