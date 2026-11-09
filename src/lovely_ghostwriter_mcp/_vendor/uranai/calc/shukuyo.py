"""宿曜占星術（二十七宿）— 旧暦の月日から本命宿を求める.

宿 = 旧暦の月ごとの起点宿 + (旧暦の日 − 1)、27宿（牛宿を除く）を順に巡る。
"""
from __future__ import annotations

from . import lunisolar

MANSIONS = ["昴", "畢", "觜", "参", "井", "鬼", "柳", "星", "張", "翼", "軫", "角", "亢", "氐",
            "房", "心", "尾", "箕", "斗", "女", "虚", "危", "室", "壁", "奎", "婁", "胃"]
READINGS = ["ぼう", "ひつ", "し", "しん", "せい", "き", "りゅう", "せい", "ちょう", "よく", "しん", "かく", "こう", "てい",
            "ぼう", "しん", "び", "き", "と", "じょ", "きょ", "き", "しつ", "へき", "けい", "ろう", "い"]
MONTH_START = {1: "室", 2: "奎", 3: "胃", 4: "畢", 5: "参", 6: "鬼", 7: "張", 8: "角", 9: "氐", 10: "心", 11: "斗", 12: "女"}

CONVENTIONS = [
    "二十七宿（牛宿を除く）: 昴・畢・觜・参・井・鬼・柳・星・張・翼・軫・角・亢・氐・房・心・尾・箕・斗・女・虚・危・室・壁・奎・婁・胃",
    "本命宿＝旧暦の月の起点宿（1月室・2月奎・3月胃・4月畢・5月参・6月鬼・7月張・8月角・9月氐・10月心・11月斗・12月女）から旧暦の日数−1だけ進めた宿",
    "閏月は元の月（例: 閏4月→4月）の起点宿を使う",
    *lunisolar.CONVENTIONS,
    "旧暦の日付は出生日（JSTの暦日）で決まるため、出生時刻は使わない",
]


def shuku_of(month: int, day: int) -> str:
    start = MANSIONS.index(MONTH_START[month])
    return MANSIONS[(start + day - 1) % 27]


def calculate(birth_date: str, birth_time: str | None = None) -> dict:
    y, m, d = (int(x) for x in birth_date.split("-"))
    ld = lunisolar.lunar_date(y, m, d)
    name = shuku_of(ld["month"], ld["day"])
    warnings = []
    status = "ok"
    if ld["boundary_notes"]:
        status = "partial"
        warnings.append("旧暦の境界が不確実です: " + "／".join(ld["boundary_notes"])
                        + "。天文計算の誤差や暦の作り方の違いで旧暦の日付（＝宿）が1日ずれる可能性があります")
    if ld["leap"]:
        warnings.append(f"閏{ld['month']}月の生まれのため、{ld['month']}月の起点宿（{MONTH_START[ld['month']]}宿）で計算しています")
    i = MANSIONS.index(name)
    return {
        "system": "shukuyo",
        "status": status,
        "input": {"birth_date": birth_date, "birth_time": birth_time},
        "lunar_date": {"year": ld["year"], "month": ld["month"], "day": ld["day"], "leap": ld["leap"],
                       "label": ld["label"], "new_moon_at": ld["new_moon_at"]},
        "shuku": {"name": name + "宿", "kanji": name, "reading": READINGS[i] + "しゅく", "index27": i},
        "month_start_shuku": MONTH_START[ld["month"]] + "宿",
        "conventions": CONVENTIONS,
        "warnings": warnings,
        "unavailable": [],
    }
