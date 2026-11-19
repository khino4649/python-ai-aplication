# ✍️ AI ライティングツール（個人用）

Python + Streamlit + Gemini API で作った、ライティング系 AI ツールのまとめアプリです。

## 機能

| ツール | 内容 |
|---|---|
| 📝 ブログ記事作成 | テーマ・読者・文体・文字数から構成付きの記事を執筆 |
| ✉️ メール返信 | 受信メールと伝えたいことから返信文を作成（最大3パターン） |
| 📋 文章要約 | 箇条書き / 3行 / 1行 / レポート形式などで要約 |
| 🔍 校正・推敲 | 誤字脱字修正〜ブラッシュアップ＋修正点の説明 |
| 🔄 文体変換 | 敬語・カジュアル・やさしい日本語などに書き換え |
| 🌐 翻訳 | 多言語への自然な翻訳 |
| 📣 SNS投稿作成 | X / Instagram などの投稿文を複数案作成 |
| 💡 タイトル・コピー案 | タイトルやキャッチコピーを大量に提案 |
| ✨ 自由入力 | 何でも依頼できる汎用モード |

共通機能: ストリーミング表示、追加の指示で書き直し、Markdown ダウンロード、セッション内の履歴。

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # .env に GEMINI_API_KEY を記入
python -m streamlit run app.py
```

※ 環境によっては `streamlit.exe` がアプリ制御ポリシーでブロックされるため、`python -m streamlit` で起動しています。

API キーは https://aistudio.google.com/apikey で取得できます（サイドバーで直接入力することもできます）。

## ファイル構成

- `app.py` — 画面（サイドバー、生成、結果表示）
- `tools.py` — 各ツールの入力フォームとプロンプト。**ツールを追加するときはここに `render_xxx` を書いて `TOOLS` に登録するだけ**
- `gemini_client.py` — Gemini API のストリーミング呼び出し
