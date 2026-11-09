"""数秘術（ピタゴラス式）."""
from __future__ import annotations

from datetime import datetime

from . import kana

MASTER = {11, 22, 33}
PYTHAGOREAN = {c: (i % 9) + 1 for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}
VOWELS = set("aeiou")

CONVENTIONS = [
    "ピタゴラス式（A=1…I=9, J=1…）",
    "ライフパスは年・月・日を個別に還元してから合計し、11/22/33はマスターナンバーとして保持",
    "名前の数はふりがなをヘボン式ローマ字に変換して計算（" + kana.RULES + "）。母音は a,i,u,e,o（y は子音扱い）",
    "パーソナルイヤーは誕生月日＋今年（西暦）で計算",
]


def reduce(n: int, keep_master: bool = True) -> int:
    while n > 9 and not (keep_master and n in MASTER):
        n = sum(int(c) for c in str(n))
    return n


def _steps(n: int) -> str:
    seq = [n]
    while seq[-1] > 9 and seq[-1] not in MASTER:
        seq.append(sum(int(c) for c in str(seq[-1])))
    return "→".join(str(x) for x in seq)


def name_numbers(romaji: str) -> dict:
    letters = [c for c in romaji.lower() if c in PYTHAGOREAN]
    tot = sum(PYTHAGOREAN[c] for c in letters)
    vow = sum(PYTHAGOREAN[c] for c in letters if c in VOWELS)
    con = sum(PYTHAGOREAN[c] for c in letters if c not in VOWELS)
    return {
        "destiny": {"value": reduce(tot), "raw_sum": tot, "steps": _steps(tot)},
        "soul": {"value": reduce(vow), "raw_sum": vow, "steps": _steps(vow)},
        "personality": {"value": reduce(con), "raw_sum": con, "steps": _steps(con)},
    }


def calculate(birth_date: str | None, name_kana: str | None, now: datetime | None = None) -> dict:
    out: dict = {"system": "numerology", "status": "ok", "conventions": CONVENTIONS, "warnings": [], "unavailable": []}
    now = now or datetime.now()
    if birth_date:
        y, m, d = (int(x) for x in birth_date.split("-"))
        parts = [reduce(sum(int(c) for c in str(y))), reduce(m), reduce(d)]
        total = sum(parts)
        out["life_path"] = {"value": reduce(total), "parts": {"year": parts[0], "month": parts[1], "day": parts[2]},
                            "raw_sum": total, "steps": _steps(total)}
        out["birthday"] = {"value": reduce(d), "raw": d}
        py_raw = reduce(m) + reduce(d) + reduce(sum(int(c) for c in str(now.year)), keep_master=False)
        out["personal_year"] = {"year": now.year, "value": reduce(py_raw, keep_master=False), "raw_sum": py_raw}
    else:
        out["unavailable"].append("ライフパス・パーソナルイヤー（生年月日未入力）")
    if name_kana:
        rom = kana.to_romaji(name_kana)
        out["name"] = {"kana": name_kana, "romaji": rom, **name_numbers(rom)}
    else:
        out["unavailable"].append("名前の数（ふりがな未入力）")
    if out["unavailable"]:
        out["status"] = "partial"
    return out
