"""Streamlit + LLM アプリのセキュリティ上の「確認候補」を洗い出す補助スクリプト。

使い方: python scan.py <プロジェクトのディレクトリ>

標準ライブラリのみ。出力は手がかりであり、指摘として確定させる前に必ずコードを読んで判断すること。
秘密情報らしき値は伏せ字で表示する。
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {
    ".venv", "venv", "env", ".env", "node_modules", "__pycache__", ".git",
    "site-packages", ".mypy_cache", ".pytest_cache", ".claude", ".agents", "dist", "build",
}
TEXT_SUFFIXES = {".py", ".toml", ".json", ".yaml", ".yml", ".md", ".txt", ".ipynb", ".cfg", ".ini", ".sh", ".ps1"}
TEXT_NAMES = {"Dockerfile", "Procfile", ".env.example", ".env.sample", ".env.template"}

SECRET_PATTERNS = [
    ("Google API キー", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Anthropic API キー", re.compile(r"sk-ant-[0-9A-Za-z_\-]{20,}")),
    ("OpenAI API キー", re.compile(r"sk-(?:proj-)?[0-9A-Za-z_\-]{20,}")),
    ("GitHub トークン", re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}")),
    ("AWS アクセスキー", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("キー代入のリテラル", re.compile(r"""(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["'][^"'\s]{16,}["']""")),
]

# (カテゴリ, 正規表現, 確認ポイント)
CODE_RULES = [
    ("LLM 出力の描画", r"unsafe_allow_html\s*=\s*True", "描画している値に LLM 出力やユーザー入力が含まれると XSS"),
    ("LLM 出力の描画", r"\bst\.html\(|components(\.v1)?\.html\(|\bcomponents\.iframe\(", "生の HTML として描画している。LLM 出力やユーザー入力が流れていないか"),
    ("コード実行", r"(?<![\w.])(eval|exec)\s*\(", "LLM 出力やユーザー入力が渡ると任意コード実行"),
    ("コード実行", r"\bsubprocess\.|\bos\.system\(|\bos\.popen\(", "コマンドに外部入力が混ざらないか"),
    ("危険な読み込み", r"pickle\.loads?\(|read_pickle\(|torch\.load\(|joblib\.load\(", "信頼できないデータを読むと任意コード実行"),
    ("危険な読み込み", r"yaml\.load\((?![^)]*SafeLoader)", "SafeLoader なしの yaml.load"),
    ("秘密情報", r"value\s*=\s*(os\.getenv|os\.environ|st\.secrets)", "サーバーの秘密情報をウィジェットの初期値にするとブラウザに送られる（type=password でも同じ）"),
    ("秘密情報", r"(print|logging\.\w+|logger\.\w+)\(.*(api_key|apikey|secret|token|password)", "秘密情報をログに出していないか"),
    ("エラー表示", r"st\.(code|error|write|text)\(\s*(str\()?\s*(e|err|exc|error)\b|st\.exception\(", "例外の詳細を画面に出している。公開時に内部情報や URL が漏れないか"),
    ("共有キャッシュ", r"@st\.cache_(data|resource)", "全ユーザーで共有される。ユーザー固有のデータをキャッシュしていないか"),
    ("ファイルアップロード", r"st\.file_uploader\(", "type= の制限、サイズ、保存先のパス、解析方法を確認"),
    ("外部アクセス", r"requests\.(get|post|request)\(|httpx\.|urllib\.request\.urlopen\(|aiohttp\.", "ユーザー入力の URL を取得していないか（SSRF）"),
    ("過剰な権限", r"\btools\s*=|function_declarations|tool_choice|bind_tools\(|create_\w*agent\(|code_execution", "LLM が使えるツールと、その権限を確認"),
    ("入力・出力の上限", r"max_output_tokens|max_tokens|max_chars", "上限の設定あり（値が妥当か確認）"),
    ("認証", r"st\.login\(|st\.user\b|st\.experimental_user|streamlit_authenticator|check_password", "認証の仕組みあり（全ページで効いているか確認）"),
]
LLM_SDKS = {
    "google.genai": "google-genai", "google.generativeai": "google-generativeai（非推奨）",
    "openai": "openai", "anthropic": "anthropic", "langchain": "langchain", "litellm": "litellm",
    "ollama": "ollama", "mistralai": "mistralai", "cohere": "cohere", "groq": "groq",
}
CONFIG_RULES = [
    (r"enableXsrfProtection\s*=\s*false", "XSRF 対策が無効"),
    (r"enableCORS\s*=\s*false", "CORS 制限が無効"),
    (r"showErrorDetails\s*=\s*(true|\"full\"|\"stacktrace\")", "例外の詳細をユーザーに表示する"),
    (r"address\s*=\s*\"0\.0\.0\.0\"", "全インターフェースで待ち受け"),
    (r"maxUploadSize\s*=\s*\d{4,}", "アップロード上限が非常に大きい"),
]


def mask(s: str) -> str:
    return f"{s[:4]}****（末尾4文字: {s[-4:]}）" if len(s) > 8 else "****"


def iter_files(root: Path):
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts[:-1]):
            continue
        if p.is_file() and (p.suffix in TEXT_SUFFIXES or p.name in TEXT_NAMES):
            yield p


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def module_level_mutables(tree: ast.Module) -> list[tuple[int, str]]:
    found = []
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        is_mutable = isinstance(value, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp)) or (
            isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            and value.func.id in {"list", "dict", "set", "defaultdict", "deque", "OrderedDict"}
        )
        if is_mutable:
            for t in targets:
                if isinstance(t, ast.Name):
                    found.append((node.lineno, t.id))
    return found


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    rel = lambda p: p.relative_to(root).as_posix()  # noqa: E731
    print(f"# スキャン結果: {root}\n")
    print("※ 確認候補の一覧です。指摘とする前に必ずコードを読んで判断してください。\n")

    files = list(iter_files(root))
    py_files = [p for p in files if p.suffix == ".py"]

    # LLM SDK と Streamlit の利用状況
    sdks, entry_points = set(), []
    for p in py_files:
        text = read(p)
        for mod, label in LLM_SDKS.items():
            if re.search(rf"^\s*(from|import)\s+{re.escape(mod)}\b", text, re.M):
                sdks.add(label)
        if re.search(r"^\s*import streamlit|^\s*from streamlit", text, re.M) and "set_page_config" in text:
            entry_points.append(rel(p))
    print("## 概要\n")
    print(f"- Python ファイル数: {len(py_files)}")
    print(f"- LLM SDK: {', '.join(sorted(sdks)) or '検出なし'}")
    print(f"- エントリーポイント候補（set_page_config あり）: {', '.join(entry_points) or '検出なし'}\n")

    # 秘密情報
    print("## 秘密情報らしき文字列\n")
    hits = 0
    for p in files:
        for i, line in enumerate(read(p).splitlines(), 1):
            for label, pat in SECRET_PATTERNS:
                m = pat.search(line)
                if m:
                    hits += 1
                    print(f"- `{rel(p)}:{i}` {label}: {mask(m.group(0))}")
                    break
    print("- なし\n" if not hits else "")

    # コードのパターン
    print("## コード上の確認候補\n")
    by_cat: dict[str, list[str]] = {}
    for p in py_files:
        lines = read(p).splitlines()
        for i, line in enumerate(lines, 1):
            if line.lstrip().startswith("#"):
                continue
            for cat, pat, note in CODE_RULES:
                if re.search(pat, line):
                    by_cat.setdefault(cat, []).append(f"- `{rel(p)}:{i}` `{line.strip()[:100]}` — {note}")
    found_cats = set(by_cat)
    for cat, items in by_cat.items():
        print(f"### {cat}\n")
        print("\n".join(items[:30]))
        if len(items) > 30:
            print(f"- …ほか {len(items) - 30} 件")
        print()
    if "入力・出力の上限" not in found_cats:
        print("- ⚠ max_output_tokens / max_tokens / max_chars が見つからない（入力・出力の長さに上限がない可能性）")
    if "認証" not in found_cats:
        print("- ⚠ 認証の仕組みが見つからない（公開する場合は要確認）")
    print()

    # モジュールレベルの可変オブジェクト（エントリーポイント以外は全セッションで共有）
    print("## モジュールレベルの可変オブジェクト\n")
    print("インポートされるモジュールのものは全ユーザーで共有される。実行中にユーザーのデータを追加していないか確認する。\n")
    any_mut = False
    for p in py_files:
        try:
            tree = ast.parse(read(p))
        except SyntaxError:
            continue
        for lineno, name in module_level_mutables(tree):
            any_mut = True
            where = "エントリーポイント（実行ごとに再評価）" if rel(p) in entry_points else "インポートされるモジュール（共有）"
            print(f"- `{rel(p)}:{lineno}` `{name}` — {where}")
    print("- なし\n" if not any_mut else "")

    # 設定ファイル
    print("## Streamlit の設定\n")
    cfg = root / ".streamlit" / "config.toml"
    if cfg.exists():
        text = read(cfg)
        issues = [msg for pat, msg in CONFIG_RULES if re.search(pat, text)]
        print("\n".join(f"- ⚠ {m}" for m in issues) or "- 危険な設定は検出なし")
        if "showErrorDetails" not in text:
            print("- showErrorDetails が未設定（既定では例外の詳細が表示される）")
    else:
        print("- `.streamlit/config.toml` なし（すべて既定値。showErrorDetails も既定のまま）")
    print()

    # .gitignore と Git 管理状況
    print("## 秘密情報ファイルの管理\n")
    gi = read(root / ".gitignore")
    for name in [".env", ".streamlit/secrets.toml"]:
        covered = any(
            line.strip().rstrip("/") in {name, name.split("/")[-1], "*" + Path(name).suffix, ".streamlit"}
            or (name == ".env" and line.strip() in {".env*", "*.env"})
            for line in gi.splitlines()
        )
        exists = (root / name).exists()
        print(f"- `{name}`: {'存在する' if exists else '存在しない'} / .gitignore {'で除外' if covered else 'に記載なし ⚠'}")
    if (root / ".git").exists():
        try:
            tracked = subprocess.run(
                ["git", "ls-files", ".env", ".streamlit/secrets.toml", "*.env"],
                cwd=root, capture_output=True, text=True, timeout=30,
            ).stdout.split()
            print(f"- Git 管理下の秘密情報ファイル: {', '.join(tracked) if tracked else 'なし'}{' ⚠' if tracked else ''}")
        except (OSError, subprocess.SubprocessError):
            print("- git コマンドを実行できず未確認")
    else:
        print("- Git リポジトリではない（履歴の確認は不要）")
    print()

    # 依存関係
    print("## 依存関係\n")
    req = root / "requirements.txt"
    if req.exists():
        unpinned = [
            l.strip() for l in read(req).splitlines()
            if l.strip() and not l.strip().startswith(("#", "-")) and not re.search(r"==|~=|<=|<|>=", l)
        ]
        print(f"- バージョン指定なし: {', '.join(unpinned) if unpinned else 'なし'}")
    elif (root / "pyproject.toml").exists():
        print("- pyproject.toml で管理（手動で確認）")
    else:
        print("- 依存定義ファイルが見つからない")


if __name__ == "__main__":
    main()
