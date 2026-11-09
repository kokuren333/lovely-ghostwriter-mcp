"""タロット出生カード（バースカード） — Mary K. Greer 方式.

n = 月 + 日 + 西暦年（例: 1990-07-15 → 7 + 15 + 1990 = 2012）
s = n の各桁の和。s > 21 の間、さらに各桁の和を取る。
s が主カード。s >= 10 なら各桁の和を1桁になるまで続け、2枚組（または 19→10→1 の3枚組）とする。
"""
from __future__ import annotations

from . import tarot

CONVENTIONS = [
    "Mary K. Greer（『Who Are You in the Tarot?』）の方式: 月＋日＋西暦年を足し、各桁の和が21以下になるまで縮約",
    "21以下になった数を主カード、それが10以上なら各桁の和を1桁になるまで取り、組（ペア/トリオ）を作る",
    "大きい数のカード＝パーソナリティカード、1桁のカード＝ソウルカード（1桁のみの場合は1枚が両方を兼ねる）",
    "19→10→1 の3枚組では中間の10（運命の輪）も組の一員として示す",
    "大アルカナの番号はライダー・ウェイト・スミス系（8＝力、11＝正義）",
    "0（愚者）はこの計算方式では出現しない",
]


def _digit_sum(n: int) -> int:
    return sum(int(c) for c in str(n))


def _card(num: int) -> dict:
    c = next(c for c in tarot.cards() if c["id"] == f"major-{num:02d}")
    return {"number": num, "card_id": c["id"], "name_ja": c["name_ja"], "name_en": c["name_en"],
            "keywords": c["upright"]}


def calculate(birth_date: str) -> dict:
    y, m, d = (int(x) for x in birth_date.split("-"))
    n = m + d + y
    steps = [n]
    s = _digit_sum(n)
    steps.append(s)
    while s > 21:
        s = _digit_sum(s)
        steps.append(s)
    chain = [s]
    while chain[-1] > 9:
        chain.append(_digit_sum(chain[-1]))
    cards = []
    if len(chain) == 1:
        cards.append({**_card(s), "role": "パーソナリティカード／ソウルカード（兼）"})
    else:
        for i, num in enumerate(chain):
            if i == 0:
                role = "パーソナリティカード"
            elif i == len(chain) - 1:
                role = "ソウルカード"
            else:
                role = "中間カード（3枚組の中継）"
            cards.append({**_card(num), "role": role})
    return {
        "system": "birthcard",
        "status": "ok",
        "input": {"birth_date": birth_date},
        "sum": n,
        "steps": "→".join(str(x) for x in steps),
        "chain": chain,
        "cards": cards,
        "personality": cards[0]["number"],
        "soul": cards[-1]["number"],
        "conventions": CONVENTIONS,
        "warnings": [],
        "unavailable": [],
    }
