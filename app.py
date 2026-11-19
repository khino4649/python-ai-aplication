"""AI ライティングツール（個人用）

起動: streamlit run app.py
"""

import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from gemini_client import friendly_error, list_text_models, stream_generate
from tools import TOOLS

load_dotenv()

DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = [DEFAULT_MODEL]  # API からモデル一覧を取得できないときに使う
CUSTOM_MODEL = "その他（手入力）"


@st.cache_data(ttl=3600, show_spinner=False)
def available_models(api_key: str) -> list[str]:
    """API キーで使えるモデル一覧（1 時間キャッシュ）。取得失敗時は固定リスト。"""
    try:
        return list_text_models(api_key) or FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS

st.set_page_config(page_title="AI ライティングツール", page_icon="✍️", layout="wide")

# セッション内で保持するデータ（DB は使わない）
st.session_state.setdefault("outputs", {})  # tool.key -> 最新の生成結果
st.session_state.setdefault("history", [])  # 生成履歴（新しい順）


# ---------------------------------------------------------------- サイドバー
with st.sidebar:
    st.title("✍️ AI ライティング")

    tool = st.radio(
        "ツール",
        TOOLS,
        format_func=lambda t: f"{t.icon} {t.label}",
        label_visibility="collapsed",
    )

    st.divider()
    server_key = os.getenv("GEMINI_API_KEY", "")
    with st.expander("⚙️ 設定", expanded=not server_key):
        # .env のキーはウィジェットの値にしない（type="password" でも値はブラウザに送られるため）
        if server_key:
            api_key = server_key
            st.caption("🔑 API キーは .env から読み込み済みです")
        else:
            api_key = st.text_input(
                "Gemini API キー",
                type="password",
                help=".env に GEMINI_API_KEY を書いておくと自動で読み込みます",
            )
        models = (available_models(api_key) if api_key else FALLBACK_MODELS) + [CUSTOM_MODEL]
        model = st.selectbox(
            "モデル",
            models,
            index=models.index(DEFAULT_MODEL) if DEFAULT_MODEL in models else 0,
            help="API キーを入力すると、そのキーで使えるモデルの一覧を取得します",
        )
        if model == CUSTOM_MODEL:
            model = st.text_input("モデル名", placeholder=f"例: {DEFAULT_MODEL}")
        temperature = st.slider(
            "創造性（temperature）",
            0.0,
            2.0,
            tool.temperature,
            0.1,
            key=f"temp_{tool.key}",
            help="低いほど正確・安定、高いほど多様で独創的",
        )

    if st.session_state.history:
        st.divider()
        st.subheader("🕘 履歴")
        for h in st.session_state.history[:10]:
            with st.expander(f"{h['time']} {h['tool']}"):
                st.markdown(h["text"])
        if st.button("履歴をクリア", use_container_width=True):
            st.session_state.history = []
            st.rerun()


# ---------------------------------------------------------------- メイン
def generate(prompt: str) -> None:
    """生成してストリーミング表示し、結果を保存する。"""
    if not api_key:
        st.error("サイドバーの「設定」で Gemini API キーを入力してください。")
        return
    if not model:
        st.error("モデル名を入力してください。")
        return
    try:
        with st.spinner("生成中…（混雑時は自動で再試行します）"), st.container(border=True):
            text = st.write_stream(
                stream_generate(api_key, model, tool.system, prompt, temperature)
            )
    except Exception as e:
        st.error(friendly_error(e, model))
        with st.expander("エラーの詳細"):
            st.code(str(e))
        return
    st.session_state.outputs[tool.key] = text
    st.session_state.history.insert(
        0, {"time": datetime.now().strftime("%H:%M"), "tool": f"{tool.icon} {tool.label}", "text": text}
    )
    st.rerun()


st.header(f"{tool.icon} {tool.label}")
st.caption(tool.description)

prompt = tool.render()

if st.button("生成する", type="primary", disabled=prompt is None):
    generate(prompt)

output = st.session_state.outputs.get(tool.key)
if output:
    st.subheader("生成結果")
    with st.container(border=True):
        st.markdown(output)

    col1, col2, _ = st.columns([1, 1, 3])
    col1.download_button(
        "💾 ダウンロード",
        output,
        file_name=f"{tool.key}_{datetime.now():%Y%m%d_%H%M}.md",
        mime="text/markdown",
        use_container_width=True,
    )
    if col2.button("🗑️ クリア", use_container_width=True):
        del st.session_state.outputs[tool.key]
        st.rerun()

    with st.expander("📋 コピー用（右上のアイコンでコピー）"):
        st.code(output, language="markdown")

    # 生成結果への追加指示で書き直す
    refine = st.chat_input("追加の指示で書き直す（例: もっと短く / 具体例を増やして）")
    if refine:
        generate(
            f"以下の文章を、指示に従って修正してください。修正後の全文のみを出力してください。\n\n"
            f"# 指示\n{refine}\n\n# 文章\n{output}"
        )
