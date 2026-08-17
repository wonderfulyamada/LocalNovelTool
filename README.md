# Local Novel Tool v0.2 source

完全ローカルで動く、長編小説向けの軽量執筆・資料確認ツールです。

## Screenshot

![LocalNovelTool](docs/screenshot.png)

## 現在の機能

- 作品フォルダの新規作成 / 読み込み
- 初回起動時に開く操作チュートリアル作品
- 章・話の追加 / 名前変更 / 削除
- 章・話のドラッグ＆ドロップ並び替え
- 話を別の章へ差し込み
- 本文エディタ + 500ms 自動保存
- 話メモ + 自動保存
- 展開メモ + 章・話との任意の関連付け
- 自由文字列で管理する時系列
- ルビ記法 `｜白雨《しらさめ》` の入力補助
- ルビ付きプレビュー（Qt WebEngineが利用可能な場合）
- 本文 / 話メモ / 資料 / 展開 / 時系列の横断検索
- 資料: 登場人物 / アイテム / 世界観 / その他
- 最近開いた資料
- UTF-8の普通のテキストとして作品データを保存

## 開発実行

Windows PowerShell例:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## 作品データ

作品フォルダの中に以下を作ります。

```text
project.json
manuscript/
episode_notes/
references/
backups/
```

本文・メモ・資料はUTF-8テキストなので、アプリがなくても直接救出できます。

## 配布方針

最終配布はWindows向けフォルダ版ZIPを想定。Pythonを利用者側に要求しない構成にします。

## フォルダ版ビルド方針

Qt公式の `pyside6-deploy` を使用し、`pysidedeploy.spec` の `nuitka.mode` を `standalone` にしてフォルダ配布します。
正式配布前にWindows 10/11のクリーン環境、日本語パス、空白入りパスで動作確認します。
