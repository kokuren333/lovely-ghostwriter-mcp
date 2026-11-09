"""算命学 — 天中殺のみ（陽占・陰占・人体星図などは未実装）.

天中殺 = 日柱が属する旬（10日の組）で欠ける2つの地支（四柱推命の空亡と同じ二支）。
"""
from __future__ import annotations

from datetime import datetime

from . import astro, bazi, solarterms

GROUPS = {  # 旬の始まり（甲X）の日柱index -> 天中殺の二支
    0: "戌亥", 10: "申酉", 20: "午未", 30: "辰巳", 40: "寅卯", 50: "子丑",
}
XUN_NAME = {0: "甲子旬", 10: "甲戌旬", 20: "甲申旬", 30: "甲午旬", 40: "甲辰旬", 50: "甲寅旬"}

CONVENTIONS = [
    "天中殺は日柱の旬（甲から始まる10日の組）で欠ける2つの地支。四柱推命で日柱から求める空亡と同じ二支",
    "日柱はユリウス通日から算出（1949年10月1日＝甲子日）。日の区切りは0時（JST）",
    "天中殺の年＝年支が天中殺の二支にあたる年（立春で年が切り替わる）。天中殺の月＝月支が二支にあたる節月（節入りの瞬間で切り替わる）",
    "本アプリの算命学は天中殺のみを算出（陽占・陰占・人体星図などは未実装）",
]
UNAVAILABLE = ["陰占（命式の干支・蔵干・位相法など）", "陽占（人体星図・十大主星・十二大従星）", "大運・年運の詳細", "宿命天中殺などの判定"]


def _jst(jd: float) -> str:
    return astro.datetime_from_jd(jd).strftime("%Y-%m-%d %H:%M")


def _year_entry(solar_year: int) -> dict:
    idx = (solar_year - 4) % 60
    return {"solar_year": solar_year, "ganzhi": bazi.ganzhi_name(idx),
            "from": _jst(solarterms.risshun(solar_year)), "to": _jst(solarterms.risshun(solar_year + 1))}


def _month_period(solar_year: int, branch: int) -> dict:
    """節月 of the given branch within the solar year starting at 立春 of solar_year."""
    gy = solar_year + 1 if branch == 1 else solar_year  # 丑月(小寒) falls in January of the next year
    jies = solarterms.jie_instants(gy)
    k = next(i for i, j in enumerate(jies) if j[2] == branch)
    start = jies[k]
    end = jies[k + 1] if k + 1 < len(jies) else solarterms.jie_instants(gy + 1)[0]
    ystem = (solar_year - 4) % 10
    kk = (branch - 2) % 12
    stem = (ystem * 2 + 2 + kk) % 10
    return {"branch": bazi.BRANCHES[branch], "ganzhi": bazi.ganzhi_name(bazi.ganzhi_index(stem, branch)),
            "jie": start[1], "from": _jst(start[0]), "to": _jst(end[0])}


def calculate(birth_date: str, now: datetime | None = None) -> dict:
    y, m, d = (int(x) for x in birth_date.split("-"))
    didx = bazi.day_index(y, m, d)
    xun = didx - didx % 10
    pair = GROUPS[xun]
    pair_idx = [bazi.BRANCHES.index(c) for c in pair]

    now = now or datetime.now(astro.JST)
    jd_now = astro.jd_from_datetime(now)
    cur_sy, cur_yidx = bazi.year_index_for(jd_now, now.year)
    in_now = cur_yidx % 12 in pair_idx

    current_period = None
    if in_now:
        years = [cur_sy] + ([cur_sy + 1] if cur_yidx % 12 == pair_idx[0] else [cur_sy - 1])
        years.sort()
        current_period = {"years": [_year_entry(v) for v in years]}
    nxt = cur_sy + 1
    while (nxt - 4) % 12 not in pair_idx or (in_now and nxt - 1 == cur_sy):
        nxt += 1
    next_years = [nxt, nxt + 1]
    months = [_month_period(cur_sy, b) for b in pair_idx]
    months.sort(key=lambda x: x["from"])

    return {
        "system": "sanmei",
        "status": "partial",
        "input": {"birth_date": birth_date},
        "day_pillar": bazi.ganzhi_name(didx),
        "xun": XUN_NAME[xun],
        "tenchusatsu": {"name": f"{pair}天中殺", "branches": list(pair)},
        "current": {
            "as_of": now.strftime("%Y-%m-%d"),
            "solar_year": cur_sy, "year_ganzhi": bazi.ganzhi_name(cur_yidx),
            "is_tenchusatsu_year": in_now,
            "period": current_period,
        },
        "next_tenchusatsu_years": [_year_entry(v) for v in next_years],
        "tenchusatsu_months_this_year": months,
        "conventions": CONVENTIONS,
        "warnings": [],
        "unavailable": list(UNAVAILABLE),
    }
