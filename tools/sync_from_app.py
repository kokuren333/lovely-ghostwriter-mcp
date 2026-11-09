"""アプリ本体（親フォルダの uranai/ ほか）から、MCP サーバーが使う部品を vendoring する.

usage:
    python tools/sync_from_app.py                 # 既定: mcp-server の1つ上のフォルダをアプリとみなす
    python tools/sync_from_app.py --app <path>    # アプリのルートを指定
    python tools/sync_from_app.py --check         # コピーせず、差分と秘密情報チェックだけ行う

コピー先: src/lovely_ghostwriter_mcp/_vendor/
  uranai/          計算（calc/**）・カタログ・プリセット・図表（facts）・心理学レンズ（psych）・
                   鑑定プロンプト（reading）・入力正規化（intake）・描画（render/fit/qa）・テンプレート・data/
  schemas/         reading.schema.json（job_input.schema.json）
  assets/design/   デジタル版・印刷版の共通デザイン素材（page1-bg.jpg, poem-bg.jpg, beast-emblem.png, beast-line.svg, ornament.png）
  config/settings.json   MCP 用に生成（ブランド・描画設定・SNS リンクのみ。連絡先メール・GAS・メール送信・キュー設定は含めない）
  docs/POLICY.md         MCP 用に生成（policy.py が読む要約ブロックだけ）

コピーしないもの（秘密情報・個人情報・運用専用のコード）:
  jobqueue / watcher / workerpool / pipeline / delivery / gas_client / scrub / localform / joblog / codex_bridge /
  __main__ / mail・signboard テンプレート / config/*（gas_endpoint・form_url・settings の連絡先）/ jobs・queue・logs の実データ

config.py は差し替える（_vendor 内の生成設定を読むアダプタ。GAS・フォーム URL は常に空）。
コピー後に、メールアドレス様の文字列・トークン様の文字列・PayPay への言及が残っていないか検査し、見つかれば失敗する。
任意で tools/.sync-denylist.txt（git 管理外）に1行1語で禁止語を書くと、それも検査する。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MCP_ROOT = HERE.parent
VENDOR = MCP_ROOT / "src" / "lovely_ghostwriter_mcp" / "_vendor"

# uranai/ 直下で取り込むモジュール（運用系・送信系・キュー系は含めない）
MODULES = ["__init__.py", "catalog.py", "presets.py", "calc_cli.py", "facts.py", "fit.py", "psych.py",
           "reading.py", "intake.py", "render.py", "qa.py", "policy.py"]
TEMPLATES = ["print.html.j2", "digital.html.j2"]
SCHEMAS = ["reading.schema.json", "job_input.schema.json"]
DESIGN = ["page1-bg.jpg", "poem-bg.jpg", "beast-emblem.png", "beast-line.svg", "ornament.png"]
DATA_EXT = {".json", ".csv", ".txt"}

# vendored コードに当てる最小限の書き換え（絶対 import → 相対 import）
PATCHES = {
    "calc_cli.py": [('importlib.import_module(f"uranai.calc.{s}")',
                     'importlib.import_module(f".calc.{s}", __package__)')],
}

CONFIG_ADAPTER = '''"""MCP 版の設定アダプタ（tools/sync_from_app.py が生成。アプリ版 config.py の代わり）.

アプリ版と同じ関数名を提供するが、読むのは _vendor/config/settings.json（秘密情報なし）だけ。
GAS エンドポイント・フォーム URL は常に空。ブランド名などは環境変数で上書きできる。
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"


@lru_cache(maxsize=1)
def settings() -> dict:
    s = json.loads((CONFIG / "settings.json").read_text(encoding="utf-8"))
    b = s.setdefault("brand", {})
    for key, env in (("shop_name", "LGW_SHOP_NAME"), ("title", "LGW_TITLE"), ("contact_email", "LGW_CONTACT")):
        if os.environ.get(env):
            b[key] = os.environ[env]
    if os.environ.get("LGW_BROWSER_CHANNEL"):
        s.setdefault("render", {})["browser_channel"] = os.environ["LGW_BROWSER_CHANNEL"]
    s.setdefault("claude", {})["model"] = os.environ.get("LGW_MODEL", s.get("claude", {}).get("model", "claude-opus-5-5"))
    return s


def social() -> dict:
    return dict(settings().get("social") or {})


def form_url(kind: str = "main") -> str:
    return ""


def gas_endpoint():
    return None


def brand() -> dict:
    return settings()["brand"]
'''

POLICY_MD = """# POLICY（MCP 版・要約のみ。tools/sync_from_app.py が生成）

## 2. 要約版（デジタル版フッター）

```text
本鑑定はエンターテインメントで、医療・法律・投資等の助言ではありません。重要な判断は専門家へ。
```

## 3. 超短縮版（印刷版フッター）

```text
占いは娯楽です。医療・法律・投資の助言ではありません。
```
"""

SECRET_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.)[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "メールアドレス"),
    (re.compile(r"script\.google\.com/macros/s/[A-Za-z0-9_-]{20,}"), "GAS WebApp URL"),
    (re.compile(r"docs\.google\.com/forms/d/(?:e/)?[A-Za-z0-9_-]{20,}"), "Google フォーム ID"),
    (re.compile(r"forms\.gle/[A-Za-z0-9]{6,}"), "フォーム短縮 URL"),
    (re.compile(r"(?i)\b(?:token|secret|api[_-]?key)\b\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"), "トークン様の文字列"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"), "Anthropic API キー"),
    (re.compile(r"(?i)paypay"), "PayPay への言及（BRIEF §5 で撤去済みのはず）"),
]
TEXT_EXT = {".py", ".j2", ".json", ".md", ".svg", ".txt", ".html"}


def build_settings(app: Path) -> dict:
    src = json.loads((app / "config" / "settings.json").read_text(encoding="utf-8"))
    b = src.get("brand", {})
    social = {}
    st = app / "config" / "social.txt"
    if st.exists():
        for line in st.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() in ("youtube_url", "x_url"):
                    social[k.strip()] = v.strip()
    r = src.get("render", {})
    return {
        "_note": "MCP 版の設定（tools/sync_from_app.py が生成）。秘密情報・連絡先は含めない。",
        "brand": {"shop_name": b.get("shop_name", "天使の自動筆記（ラブリーゴーストライター）"),
                  "title": b.get("title", "占術ブレンド鑑定書"), "tagline": b.get("tagline", ""),
                  "contact_email": "ローカル出力のみ（サーバー保存なし）"},
        "claude": {"model": "claude-opus-5-5", "effort": "medium"},
        "render": {"browser_channel": r.get("browser_channel", "msedge"), "fallback_channel": r.get("fallback_channel", "chrome"),
                   "png_width_px": r.get("png_width_px", 3307), "png_min_width_px": r.get("png_min_width_px", 1240),
                   "digital_min_font_pt": r.get("digital_min_font_pt", 6.0)},
        "print": {k: v for k, v in src.get("print", {}).items() if k in ("margin_mm", "min_font_pt", "min_line_pt")},
        "retention_days": 0,
        "social": social,
    }


def scan(root: Path, deny: list[str]) -> list[str]:
    hits = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in TEXT_EXT or "__pycache__" in p.parts:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for rx, why in SECRET_PATTERNS:
            for m in rx.finditer(text):
                hits.append(f"{p.relative_to(root)}: {why}: {m.group(0)[:60]}")
        for w in deny:
            if w and w in text:
                hits.append(f"{p.relative_to(root)}: 禁止語（denylist）")
    return hits


def sync(app: Path, check_only: bool = False) -> int:
    ur = app / "uranai"
    if not (ur / "catalog.py").exists():
        print(f"アプリが見つかりません: {app}", file=sys.stderr)
        return 2
    staging = VENDOR.parent / "_vendor.staging"
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "uranai" / "templates").mkdir(parents=True)
    warnings = []
    # --- uranai modules
    for m in MODULES:
        src = ur / m
        if not src.exists():
            warnings.append(f"uranai/{m} がありません（スキップ）")
            continue
        text = src.read_text(encoding="utf-8")
        for old, new in PATCHES.get(m, []):
            if old not in text:
                warnings.append(f"uranai/{m}: パッチ対象「{old}」が見つかりません（アプリ側で変更された可能性）")
            text = text.replace(old, new)
        (staging / "uranai" / m).write_text(text, encoding="utf-8", newline="\n")
    (staging / "uranai" / "config.py").write_text(CONFIG_ADAPTER, encoding="utf-8", newline="\n")
    # --- calc/** and data/
    shutil.copytree(ur / "calc", staging / "uranai" / "calc", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (staging / "uranai" / "data").mkdir()
    for p in sorted((ur / "data").iterdir()):
        if p.is_file() and p.suffix in DATA_EXT:
            shutil.copy2(p, staging / "uranai" / "data" / p.name)
    for t in TEMPLATES:
        shutil.copy2(ur / "templates" / t, staging / "uranai" / "templates" / t)
    # --- schemas
    (staging / "schemas").mkdir()
    for s in SCHEMAS:
        if (app / "schemas" / s).exists():
            shutil.copy2(app / "schemas" / s, staging / "schemas" / s)
    # --- design assets
    (staging / "assets" / "design").mkdir(parents=True)
    for a in DESIGN:
        src = app / "assets" / "design" / a
        if src.exists():
            shutil.copy2(src, staging / "assets" / "design" / a)
        else:
            warnings.append(f"assets/design/{a} がありません（render_certificate は素材が揃うまで失敗します）")
    fonts = app / "assets" / "fonts"
    if fonts.is_dir():
        shutil.copytree(fonts, staging / "assets" / "fonts")
    # --- generated config / policy
    (staging / "config").mkdir()
    (staging / "config" / "settings.json").write_text(json.dumps(build_settings(app), ensure_ascii=False, indent=1) + "\n",
                                                      encoding="utf-8", newline="\n")
    (staging / "docs").mkdir()
    (staging / "docs" / "POLICY.md").write_text(POLICY_MD, encoding="utf-8", newline="\n")
    rs = app / "docs" / "READING_STYLE.md"
    if rs.exists():
        shutil.copy2(rs, staging / "docs" / "READING_STYLE.md")
    (staging / "__init__.py").write_text('"""アプリ本体から同期した部品（tools/sync_from_app.py が生成。直接編集しない）."""\n',
                                         encoding="utf-8", newline="\n")
    (staging / "SYNCED_FROM.txt").write_text("synced by tools/sync_from_app.py from the app's uranai/, schemas/, assets/design/\n",
                                             encoding="utf-8", newline="\n")

    # テスト・サンプル用の架空の鑑定データ生成器（アプリのテスト fixture。スキーマ改訂に追従させるため同期する）
    fx = app / "tests" / "fixtures" / "fake_reading.py"
    if fx.exists():
        t = fx.read_text(encoding="utf-8")
        t = re.sub(r"(?m)^from uranai\b", "from .uranai", t).replace("import uranai.", "import lovely_ghostwriter_mcp._vendor.uranai.")
        (staging / "fake_reading.py").write_text(t, encoding="utf-8", newline="\n")
    else:
        warnings.append("tests/fixtures/fake_reading.py がありません（テストの描画サンプルが作れません）")

    deny_file = HERE / ".sync-denylist.txt"
    deny = [w.strip() for w in deny_file.read_text(encoding="utf-8").splitlines()] if deny_file.exists() else []
    hits = scan(staging, deny)
    for w in warnings:
        print("WARN:", w)
    if hits:
        print("NG: 秘密情報・撤去対象の疑いがあるため同期を中止しました:", file=sys.stderr)
        for h in hits:
            print("  -", h, file=sys.stderr)
        shutil.rmtree(staging)
        return 1
    if check_only:
        shutil.rmtree(staging)
        print("OK: check only（コピーはしていません）")
        return 0
    if VENDOR.exists():
        shutil.rmtree(VENDOR)
    staging.rename(VENDOR)
    n = sum(1 for p in VENDOR.rglob("*") if p.is_file())
    print(f"OK: {n} files -> {VENDOR}")
    make_example_reading()
    return 0


def make_example_reading() -> None:
    """examples/sample_reading.json（架空の人物 sample_person.json 用の、文面がダミーの鑑定データ）を再生成する."""
    import subprocess
    code = ("import json,sys; sys.path.insert(0, r'%s');"
            "from lovely_ghostwriter_mcp import core; from lovely_ghostwriter_mcp._vendor import fake_reading;"
            "P=json.load(open(r'%s',encoding='utf-8')); rd=fake_reading.make(core.build_job(P));"
            "open(r'%s','w',encoding='utf-8',newline='\\n').write(json.dumps(rd,ensure_ascii=False,indent=1)+'\\n')"
            % (MCP_ROOT / "src", MCP_ROOT / "examples" / "sample_person.json", MCP_ROOT / "examples" / "sample_reading.json"))
    if not (MCP_ROOT / "examples" / "sample_person.json").exists() or not (VENDOR / "fake_reading.py").exists():
        return
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("OK: examples/sample_reading.json" if r.returncode == 0 else "WARN: sample_reading.json を作れません: " + r.stderr[-300:])


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--app", default=str(MCP_ROOT.parent), help="アプリ本体のルート（既定: mcp-server の親）")
    ap.add_argument("--check", action="store_true", help="コピーせず検査だけ行う")
    a = ap.parse_args(argv)
    return sync(Path(a.app).resolve(), a.check)


if __name__ == "__main__":
    raise SystemExit(main())
