"""カバラ数秘術（本アプリではカルデア式の文字対応で計算）."""
from __future__ import annotations

from . import kana

MASTER = {11, 22, 33}
CHALDEAN = {
    "a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 8, "g": 3, "h": 5, "i": 1, "j": 1, "k": 2, "l": 3, "m": 4,
    "n": 5, "o": 7, "p": 8, "q": 1, "r": 2, "s": 3, "t": 4, "u": 6, "v": 6, "w": 6, "x": 5, "y": 1, "z": 7,
}

CONVENTIONS = [
    "日本で「カバラ数秘術」と呼ばれる占術は流派が複数あり、本アプリはカルデア式の文字対応（A1 B2 C3 D4 E5 F8 G3 H5 I1 J1 K2 L3 M4 N5 O7 P8 Q1 R2 S3 T4 U6 V6 W6 X5 Y1 Z7。9は割り当てない）を採用",
    "名前はふりがなをヘボン式ローマ字に変換して計算（" + kana.RULES + "）。使用したローマ字を表示",
    "合計を各桁の和で1〜9に縮約し、11・22・33はマスターナンバーとして保持",
    "誕生数は生年月日の全桁（YYYYMMDD）の和を同様に縮約",
]


def reduce(n: int) -> int:
    while n > 9 and n not in MASTER:
        n = sum(int(c) for c in str(n))
    return n


def _steps(n: int) -> str:
    seq = [n]
    while seq[-1] > 9 and seq[-1] not in MASTER:
        seq.append(sum(int(c) for c in str(seq[-1])))
    return "→".join(str(x) for x in seq)


def calculate(name_kana: str | None, birth_date: str | None = None) -> dict:
    out: dict = {"system": "kabbalah", "status": "ok", "conventions": CONVENTIONS, "warnings": [], "unavailable": [],
                 "input": {"name_kana": name_kana, "birth_date": birth_date}}
    if name_kana:
        rom = kana.to_romaji(name_kana)
        letters = [c for c in rom if c in CHALDEAN]
        if not letters:
            out["unavailable"].append("名前数（ふりがなをローマ字に変換できませんでした）")
        else:
            tot = sum(CHALDEAN[c] for c in letters)
            out["name"] = {"kana": name_kana, "romaji": rom,
                           "letters": [{"letter": c, "value": CHALDEAN[c]} for c in letters],
                           "raw_sum": tot, "value": reduce(tot), "steps": _steps(tot),
                           "is_master": reduce(tot) in MASTER}
    else:
        out["unavailable"].append("名前数（ふりがな未入力）")
    if birth_date:
        digits = birth_date.replace("-", "")
        tot = sum(int(c) for c in digits)
        out["birth"] = {"raw_sum": tot, "value": reduce(tot), "steps": _steps(tot), "is_master": reduce(tot) in MASTER}
    if "name" not in out:
        out["status"] = "partial" if "birth" in out else "unavailable"
    return out
