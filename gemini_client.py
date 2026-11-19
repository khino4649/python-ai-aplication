"""Gemini API の呼び出しをまとめたモジュール。"""

from collections.abc import Iterator

from google import genai
from google.genai import errors, types

# 混雑（503）やレート制限（429）などの一時的なエラーは、待ち時間を伸ばしながら自動で再試行する
RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=4,  # 初回を含めた試行回数
    initial_delay=2.0,  # 秒
    max_delay=20.0,
    exp_base=2.0,
    http_status_codes=[429, 500, 502, 503, 504],
)


def _client(api_key: str) -> genai.Client:
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(retry_options=RETRY_OPTIONS),
    )


def list_text_models(api_key: str) -> list[str]:
    """この API キーで文章生成（generateContent）に使える Gemini モデル名の一覧を返す。"""
    # client は変数で保持すること（一時オブジェクトだと GC で接続が閉じられ、リクエストが失敗する）
    client = _client(api_key)
    names = []
    for m in client.models.list():
        actions = m.supported_actions or []
        name = (m.name or "").removeprefix("models/")
        if "generateContent" in actions and name.startswith("gemini"):
            names.append(name)
    return sorted(names, reverse=True)  # 新しいバージョンが上に来やすいよう降順


def stream_generate(
    api_key: str,
    model: str,
    system_instruction: str,
    prompt: str,
    temperature: float = 0.7,
) -> Iterator[str]:
    """Gemini にプロンプトを送り、生成テキストを少しずつ返す。"""
    client = _client(api_key)  # ストリームを読み終えるまで保持する
    stream = client.models.generate_content_stream(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        ),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def friendly_error(e: Exception, model: str) -> str:
    """API エラーを、次に何をすればよいかがわかる日本語メッセージにする。"""
    code = getattr(e, "code", None) if isinstance(e, errors.APIError) else None
    if code == 503:
        return f"モデル `{model}` が混み合っています（自動で再試行しましたが混雑が続いています）。少し時間をおいて再実行するか、サイドバーの「設定」で別のモデルを選んでください。"
    if code == 429:
        return "API の利用上限（レート制限）に達しました。少し時間をおいて再実行してください。"
    if code == 404:
        return f"モデル `{model}` は利用できません。サイドバーの「設定」で別のモデルを選んでください。"
    if code in (400, 401, 403) and "API key" in str(e):
        return "API キーが正しくないか、権限がありません。サイドバーの「設定」でキーを確認してください。"
    return f"生成に失敗しました: {e}"
