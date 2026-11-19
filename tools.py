"""各ライティングツールの定義。

ツールごとに「入力フォーム」と「プロンプトの組み立て」を持つ。
新しいツールを追加するときは、render_xxx 関数を書いて TOOLS に登録するだけでよい。
"""

from dataclasses import dataclass
from typing import Callable

import streamlit as st

BASE_SYSTEM = (
    "あなたは日本語のプロのライター兼編集者です。"
    "ユーザーの指示に忠実に、自然で読みやすい日本語で出力してください。"
    "前置きや「承知しました」などの返事は書かず、成果物だけを出力してください。"
)

TONES = ["丁寧", "カジュアル", "ビジネス", "フレンドリー", "専門的", "熱意のある"]


@dataclass
class Tool:
    key: str
    label: str
    icon: str
    description: str
    system: str
    render: Callable[[], str | None]  # 入力フォームを描画し、プロンプトを返す（入力不足なら None）
    temperature: float = 0.7


# ---------------------------------------------------------------- ブログ記事
def render_blog() -> str | None:
    theme = st.text_input("記事のテーマ", placeholder="例: 初心者向け Python の勉強法")
    col1, col2 = st.columns(2)
    target = col1.text_input("想定読者", placeholder="例: プログラミング未経験の社会人")
    tone = col2.selectbox("文体", TONES, index=1)
    col3, col4 = st.columns(2)
    length = col3.select_slider("文字数の目安", [800, 1500, 2500, 4000, 6000], value=2500)
    keywords = col4.text_input("含めたいキーワード（任意）", placeholder="カンマ区切り")
    notes = st.text_area("その他の要望（任意）", placeholder="例: 体験談を交えて、最後にまとめを入れて")
    if not theme:
        return None
    return f"""以下の条件でブログ記事を Markdown で執筆してください。

- テーマ: {theme}
- 想定読者: {target or "一般読者"}
- 文体: {tone}
- 文字数の目安: 約{length}字
- 含めたいキーワード: {keywords or "特になし"}
- その他の要望: {notes or "特になし"}

構成:
1. 魅力的なタイトル（# 見出し）
2. 読者の興味を引く導入
3. ## と ### を使った本文（具体例を含める）
4. まとめ
"""


# ---------------------------------------------------------------- メール返信
def render_email() -> str | None:
    received = st.text_area("受信したメール", height=200, placeholder="返信したいメール本文を貼り付け")
    col1, col2 = st.columns(2)
    relation = col1.selectbox("相手との関係", ["取引先・顧客", "上司", "同僚", "友人・知人", "その他"])
    tone = col2.selectbox("文体", ["ビジネス", "丁寧", "カジュアル", "フレンドリー"])
    intent = st.text_area(
        "返信で伝えたいこと",
        placeholder="例: 日程は了承。ただし資料の提出は来週金曜にしてほしい",
    )
    variations = st.radio("パターン数", [1, 2, 3], horizontal=True)
    if not received or not intent:
        return None
    return f"""以下の受信メールに対する返信メールを作成してください。

# 受信メール
{received}

# 条件
- 相手との関係: {relation}
- 文体: {tone}
- 伝えたいこと: {intent}
- パターン数: {variations}（複数の場合は「## パターン1」のように見出しで区切り、ニュアンスを変える）

件名（Re: 〜）と本文を出力してください。署名部分は [名前] のようなプレースホルダーにしてください。
"""


# ---------------------------------------------------------------- 要約
def render_summary() -> str | None:
    text = st.text_area("要約したい文章", height=250)
    col1, col2 = st.columns(2)
    style = col1.selectbox("要約の形式", ["箇条書き", "段落（文章）", "3行要約", "1行要約", "見出し付きレポート"])
    length = col2.selectbox("詳しさ", ["簡潔", "標準", "詳細"], index=1)
    if text:
        st.caption(f"入力文字数: {len(text):,} 字")
    if not text:
        return None
    return f"""以下の文章を要約してください。

- 形式: {style}
- 詳しさ: {length}
- 重要な数字・固有名詞は残すこと
- 原文にない情報を追加しないこと

# 文章
{text}
"""


# ---------------------------------------------------------------- 校正・推敲
def render_proofread() -> str | None:
    text = st.text_area("校正したい文章", height=250)
    mode = st.radio(
        "モード",
        ["誤字脱字・文法のみ修正", "読みやすく推敲", "大幅にブラッシュアップ"],
        horizontal=True,
    )
    if not text:
        return None
    return f"""以下の文章を「{mode}」のモードで校正してください。

出力形式:
## 修正後の文章
（修正した全文）

## 主な修正点
（何をなぜ直したかを箇条書き）

# 文章
{text}
"""


# ---------------------------------------------------------------- 文体変換
def render_rewrite() -> str | None:
    text = st.text_area("変換したい文章", height=200)
    col1, col2 = st.columns(2)
    tone = col1.selectbox(
        "変換後の文体",
        ["ビジネス敬語", "丁寧（です・ます）", "カジュアル", "である調", "小学生にもわかる", "SNS向けにくだけた感じ"],
    )
    length = col2.selectbox("長さ", ["そのまま", "短く", "長く（肉付け）"])
    if not text:
        return None
    return f"""以下の文章を書き換えてください。意味は変えないでください。

- 文体: {tone}
- 長さ: {length}

# 文章
{text}
"""


# ---------------------------------------------------------------- 翻訳
def render_translate() -> str | None:
    text = st.text_area("翻訳したい文章", height=200)
    col1, col2 = st.columns(2)
    target = col1.selectbox("翻訳先の言語", ["英語", "日本語", "中国語（簡体字）", "韓国語", "スペイン語", "フランス語", "ドイツ語"])
    style = col2.selectbox("スタイル", ["自然な意訳", "直訳寄り", "ビジネス向け", "カジュアル"])
    if not text:
        return None
    return f"""以下の文章を{target}に翻訳してください（スタイル: {style}）。
翻訳文のみを出力し、最後に「## 補足」として訳しにくかった表現があれば短く説明してください（なければ省略）。

# 文章
{text}
"""


# ---------------------------------------------------------------- SNS 投稿
def render_sns() -> str | None:
    topic = st.text_area("投稿の内容・伝えたいこと", placeholder="例: 新しいブログ記事『Python の勉強法』を公開した")
    col1, col2 = st.columns(2)
    platform = col1.selectbox("プラットフォーム", ["X (Twitter)", "Instagram", "Threads", "LinkedIn", "Facebook"])
    count = col2.radio("案の数", [3, 5], horizontal=True)
    hashtags = st.checkbox("ハッシュタグを付ける", value=True)
    emoji = st.checkbox("絵文字を使う", value=True)
    if not topic:
        return None
    return f"""以下の内容で {platform} 向けの投稿文を {count} 案作成してください。

- 内容: {topic}
- ハッシュタグ: {"付ける" if hashtags else "付けない"}
- 絵文字: {"使う" if emoji else "使わない"}
- {platform} の文字数制限や文化に合わせること（X なら 140 字以内）

各案は「## 案1」のように見出しで区切ってください。
"""


# ---------------------------------------------------------------- タイトル・キャッチコピー
def render_title() -> str | None:
    content = st.text_area("内容・商品・記事の概要", height=150)
    col1, col2 = st.columns(2)
    kind = col1.selectbox("種類", ["ブログタイトル", "キャッチコピー", "メール件名", "YouTube タイトル", "商品名"])
    count = col2.slider("案の数", 5, 20, 10)
    if not content:
        return None
    return f"""以下の内容に合う「{kind}」を {count} 案出してください。
切り口（数字・疑問形・ベネフィット訴求・意外性など）を変えて、番号付きリストで出力し、
最後に「## おすすめ」として特に良い 1 案とその理由を書いてください。

# 内容
{content}
"""


# ---------------------------------------------------------------- 自由入力
def render_free() -> str | None:
    prompt = st.text_area("指示を自由に入力", height=200, placeholder="例: 退職の挨拶文を書いて。在籍5年、明るめのトーンで")
    return prompt or None


TOOLS: list[Tool] = [
    Tool("blog", "ブログ記事作成", "📝", "テーマを入れるだけで構成付きのブログ記事を書きます", BASE_SYSTEM, render_blog, 0.8),
    Tool("email", "メール返信", "✉️", "受信メールと伝えたいことから返信文を作ります", BASE_SYSTEM, render_email, 0.6),
    Tool("summary", "文章要約", "📋", "長い文章を好きな形式で要約します", BASE_SYSTEM, render_summary, 0.3),
    Tool("proofread", "校正・推敲", "🔍", "誤字脱字の修正から文章のブラッシュアップまで", BASE_SYSTEM, render_proofread, 0.3),
    Tool("rewrite", "文体変換", "🔄", "敬語・カジュアル・やさしい日本語などに書き換えます", BASE_SYSTEM, render_rewrite, 0.6),
    Tool("translate", "翻訳", "🌐", "自然な訳文で多言語に翻訳します", BASE_SYSTEM, render_translate, 0.3),
    Tool("sns", "SNS投稿作成", "📣", "X や Instagram 向けの投稿文を複数案作ります", BASE_SYSTEM, render_sns, 0.9),
    Tool("title", "タイトル・コピー案", "💡", "タイトルやキャッチコピーを大量に提案します", BASE_SYSTEM, render_title, 1.0),
    Tool("free", "自由入力", "✨", "どんなライティング依頼にも対応します", BASE_SYSTEM, render_free, 0.7),
]
