"""タロット — SHA-256 による決定論的・再現可能な抽選."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "tarot_cards.json"

# AMENDMENT_09 §C: ケルティッククロス（10枚）を標準スプレッドとする（1枚引きは主占術として使わない）
SPREAD_NAME = "ケルティッククロス（10枚）"
SPREAD = [
    ("present", "1 現状"),
    ("challenge", "2 課題（交差）"),
    ("foundation", "3 土台"),
    ("past", "4 過去"),
    ("potential", "5 目標・可能性"),
    ("near_future", "6 近未来"),
    ("self", "7 自分の立場"),
    ("environment", "8 周囲と環境"),
    ("hopes_fears", "9 願望と恐れ"),
    ("outcome", "10 結論"),
]
CONVENTIONS = [
    "78枚（大アルカナ22・小アルカナ56）",
    "抽選はシード文字列からSHA-256で決定論的にシャッフル（Fisher-Yates、乱数=SHA-256(seed:i)）。同じシードなら同じ結果",
    "正逆は SHA-256(seed:rev:i) の最下位ビットで判定（確率1/2）",
    "スプレッド: ケルティッククロス10枚（1 現状／2 課題（交差）／3 土台／4 過去／5 目標・可能性／6 近未来／7 自分の立場／8 周囲と環境／9 願望と恐れ／10 結論）。シャッフル後の山の上から順に1〜10の位置へ置く",
    "占う対象: 本人の聞きたいこと（question）→ 無ければ気になるテーマ（concern_theme）→ どちらも無ければ全体運",
]


@lru_cache(maxsize=1)
def cards() -> list[dict]:
    return json.loads(DATA.read_text(encoding="utf-8"))["cards"]


def _h(seed: str, label: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest(), "big")


def shuffled_indices(seed: str, n: int = 78) -> list[int]:
    idx = list(range(n))
    for i in range(n - 1, 0, -1):
        j = _h(seed, f"shuffle:{i}") % (i + 1)
        idx[i], idx[j] = idx[j], idx[i]
    return idx


def reading_target(question: str | None, concern_theme: str | None = None) -> dict:
    """占う対象（AMENDMENT_09 §C）: question → concern_theme → 全体運."""
    q = (question or "").strip()
    if q:
        return {"basis": "question", "label": q}
    c = (concern_theme or "").strip()
    if c:
        return {"basis": "concern_theme", "label": f"{c}について"}
    return {"basis": "general", "label": "全体運"}


def draw(seed: str, question: str | None = None, concern_theme: str | None = None) -> dict:
    if not seed:
        raise ValueError("seed is required for reproducibility")
    order = shuffled_indices(seed)
    deck = cards()
    drawn = []
    for pos, ((key, label), ci) in enumerate(zip(SPREAD, order)):
        c = deck[ci]
        reversed_ = bool(_h(seed, f"rev:{pos}") & 1)
        drawn.append({
            "position": key, "position_label": label, "card_id": c["id"], "name_ja": c["name_ja"], "name_en": c["name_en"],
            "arcana": c["arcana"], "orientation": "逆位置" if reversed_ else "正位置",
            "keywords": c["reversed"] if reversed_ else c["upright"],
            **({"suit_theme": c["suit_theme"]} if c.get("suit_theme") else {}),
        })
    majors = sum(1 for d in drawn if d["arcana"] == "major")
    revs = sum(1 for d in drawn if d["orientation"] == "逆位置")
    return {
        "system": "tarot", "status": "ok", "seed": seed, "question": question,
        "spread_name": SPREAD_NAME, "target": reading_target(question, concern_theme),
        "spread": drawn,
        "summary": {"major_count": majors, "reversed_count": revs},
        "conventions": CONVENTIONS, "warnings": [],
    }
