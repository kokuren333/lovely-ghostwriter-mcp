"""docs/POLICY.md を唯一の正本として、要約版・超短縮版を取り出す."""
from __future__ import annotations

import re
from functools import lru_cache

from .config import ROOT, settings

FALLBACK_SHORT = ("本鑑定はエンターテインメントで、医療・法律・投資等の助言ではありません。重要な判断は専門家へ。"
                  "入力内容は計算と文章作成のためAI（Anthropic・OpenAI）で処理します。お名前・生年月日・時刻は送信後に削除します。")
FALLBACK_TINY = "占いは娯楽です。医療・法律・投資の助言ではありません。AIで処理し、氏名・生年月日は送信後に削除。"


def _block_after(text: str, heading_prefix: str) -> str | None:
    m = re.search(rf"^##\s*{re.escape(heading_prefix)}.*?```text\s*\n(.*?)\n```", text, re.S | re.M)
    return m.group(1).strip() if m else None


@lru_cache(maxsize=1)
def texts() -> dict:
    p = ROOT / "docs" / "POLICY.md"
    t = p.read_text(encoding="utf-8") if p.exists() else ""
    days = str(settings().get("retention_days", 30))
    short = (_block_after(t, "2.") or FALLBACK_SHORT).replace("30日", f"{days}日")
    tiny = (_block_after(t, "3.") or FALLBACK_TINY).replace("30日", f"{days}日")
    return {"short": short, "tiny": tiny, "contact": settings()["brand"]["contact_email"]}
