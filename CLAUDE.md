# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

Python + Streamlit + Gemini API（`google-genai` SDK）で作った個人用の AI ライティングツール（UI は日本語）。データベースと認証は意図的に持たない。状態はブラウザのセッション中だけ `st.session_state` に保持する。

## コマンド

```powershell
# セットアップ（.venv は作成済み）
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt

# 起動（http://localhost:8501）
.\.venv\Scripts\python -m streamlit run app.py
```

`gemini_client.py` や `tools.py` を変更したら、ブラウザの再読み込みだけでは古いモジュールが残ることがある（`ImportError: cannot import name ...` になる）ので、Streamlit サーバーを再起動すること。

起動は必ず `python -m streamlit` 経由で行うこと。このマシンでは `.venv\Scripts\streamlit.exe` が Windows のアプリ制御ポリシーでブロックされる。

このマシンでは Smart App Control が有効で、公開直後のライブラリの未署名バイナリ（`.pyd`）は評判不足でブロックされる（`ImportError: DLL load failed ... アプリケーション制御ポリシーによって...`）。そのため `requirements.txt` で numpy / pandas / pyarrow をブロックされないバージョンに固定している。これらを上げるときは、新しい `.venv` 内の全 `.pyd` を import してブロックされないことを確認してからにすること。Smart App Control は無効にしない。

テストスイートやリンターは未設定。ヘッドレスでの動作確認には `streamlit.testing.v1.AppTest.from_file(<app.py の絶対パス>)` を使い、`at.sidebar.radio[0]` で各ツールを切り替えながら `not at.exception` を確認する（フォームの描画だけなら Gemini を呼ばないので API キー不要）。

API キー: `.env` の `GEMINI_API_KEY`（`.env.example` 参照）を python-dotenv で読み込む。`.env` にキーがないときだけ、サイドバーの設定欄に入力欄を出す。`.env` のキーをウィジェットの `value=` に入れないこと（`type="password"` でも値はブラウザに送られる）。

`.streamlit/config.toml` の `server.address = "localhost"` で、自分の PC からの接続だけを受け付けている（未設定だと同じ LAN の他の端末からも開ける）。

## アーキテクチャ

3 つのモジュールで、依存は一方向: `app.py` → `tools.py`, `gemini_client.py`。

- **`tools.py`** — ライティングツールの登録簿。`Tool` データクラスがキー・表示名・アイコン・説明・システム指示・デフォルト temperature・`render()` 関数をまとめて持つ。`render()` はそのツールの Streamlit 入力ウィジェットを描画し、組み立て済みのプロンプト文字列を返す。必須入力が足りないときは `None` を返し、生成ボタンが無効になる。**ツールの追加は `render_xxx()` を書いて `TOOLS` に `Tool(...)` を追加するだけ**で、`app.py` の変更は不要。
- **`app.py`** — 汎用的な画面の枠組み。サイドバーのラジオボタンで `Tool` を選択し、設定（API キー、モデル、`temp_{tool.key}` をキーとするツールごとの temperature）もサイドバーに置く。`generate(prompt)` は `st.write_stream` でストリーミング表示した後、結果を `st.session_state.outputs[tool.key]`（ツールごとの最新出力）に保存して `st.session_state.history` の先頭に追加し、`st.rerun()` で結果セクションをセッション状態から描画し直す。「追加の指示で書き直す」の `st.chat_input` は、直前の出力を書き直し用プロンプトで包んで `generate()` を再度呼ぶ。
- **`gemini_client.py`** — クライアントは `_client()` で作り、429/5xx を指数バックオフで自動再試行する（`RETRY_OPTIONS`）。`_client(...).models...` のように一時オブジェクトのまま使うと GC で接続が閉じて失敗するので、必ず変数に保持すること。エラー表示用の日本語メッセージは `friendly_error()`。`stream_generate()` は呼び出しごとにクライアントを生成し、`GenerateContentConfig` に `system_instruction` と `temperature` を渡して `client.models.generate_content_stream` からテキストのチャンクを順に返す。

モデルの選択肢は、API キーがあれば `gemini_client.list_text_models()` で取得した一覧（`available_models()` で 1 時間キャッシュ）、なければ/取得失敗時は `app.py` 冒頭の `FALLBACK_MODELS`。既定は `DEFAULT_MODEL`。古いモデル（例: `gemini-2.5-flash`）は新規ユーザーには 404 になるため、モデル名をハードコードで増やさないこと。

プロンプトと UI の文言はすべて日本語。新しいツールもこれに合わせ、`tools.py` の `BASE_SYSTEM`（前置きなしで成果物だけを出力させる方針）と一貫させること。
