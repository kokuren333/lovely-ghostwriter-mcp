"""MCP 版の設定アダプタ（tools/sync_from_app.py が生成。アプリ版 config.py の代わり）.

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
