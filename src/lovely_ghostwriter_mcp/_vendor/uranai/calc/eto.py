"""干支（えと） — 年・日の干支と十二支の動物.

- 年の干支は2通り出す: (1) 立春の瞬間で切り替える暦学上の干支（四柱推命・九星気学と同じ）、
  (2) 1月1日で切り替える一般的（年賀状的）な干支。1月1日〜立春前の生まれでは両者が異なる。
- 日の干支は (JDN + 49) mod 60（bazi.day_index と同じ。1949-10-01 = 甲子）。
"""
from __future__ import annotations

from datetime import datetime

from . import astro, bazi, solarterms

ANIMALS = ["ねずみ", "うし", "とら", "うさぎ", "たつ", "へび", "うま", "ひつじ", "さる", "とり", "いぬ", "いのしし"]
BRANCH_READING = ["ね", "うし", "とら", "う", "たつ", "み", "うま", "ひつじ", "さる", "とり", "いぬ", "い"]
STEM_READING = ["きのえ", "きのと", "ひのえ", "ひのと", "つちのえ", "つちのと", "かのえ", "かのと", "みずのえ", "みずのと"]

CONVENTIONS = [
    "年の干支（暦学）: 立春の瞬間で年が切り替わる（四柱推命・九星気学と同じ。太陽視黄経315度の時刻をVSOP87短縮式で計算）",
    "年の干支（一般）: 1月1日で切り替える。年賀状などで一般に使われる干支",
    "日の干支: ユリウス通日から算出（1949年10月1日＝甲子日を基準）。日の区切りは0時（JST）",
    "入力時刻は日本標準時（JST）。出生時刻不明時は正午として立春判定",
]


def _gz(idx60: int) -> dict:
    s, b = idx60 % 10, idx60 % 12
    return {
        "ganzhi": bazi.ganzhi_name(idx60),
        "reading": STEM_READING[s] + BRANCH_READING[b],
        "stem": bazi.STEMS[s],
        "branch": bazi.BRANCHES[b],
        "animal": ANIMALS[b],
        "index60": idx60,
    }


def calculate(birth_date: str, birth_time: str | None = None, now: datetime | None = None) -> dict:
    y, m, d = (int(x) for x in birth_date.split("-"))
    has_time = bool(birth_time)
    hh, mi = (int(x) for x in birth_time.split(":")) if has_time else (12, 0)
    local = datetime(y, m, d, hh, mi, tzinfo=astro.JST)
    jd = astro.jd_from_datetime(local)
    warnings: list[str] = []
    status = "ok"

    solar_year, yidx = bazi.year_index_for(jd, y)
    cal_idx = (y - 4) % 60
    rs_jd = solarterms.risshun(y)
    rs_dt = astro.datetime_from_jd(rs_jd)
    differs = yidx != cal_idx
    if differs:
        warnings.append(
            f"1月1日〜立春（{rs_dt:%Y-%m-%d %H:%M}）前の生まれのため、立春基準の干支（{bazi.ganzhi_name(yidx)}）と"
            f"1月1日基準の干支（{bazi.ganzhi_name(cal_idx)}）が異なります")
    if rs_dt.date() == local.date():
        if has_time:
            if abs(rs_jd - jd) * 24 <= 2:
                warnings.append(f"立春（{rs_dt:%H:%M}）の前後2時間以内の出生のため、立春基準の年干支は境界付近です")
        else:
            status = "partial"
            warnings.append(f"出生日が立春当日（{rs_dt:%H:%M}）で出生時刻不明のため、立春基準の年干支は正午出生として仮定しています")

    now = now or datetime.now(astro.JST)
    jd_now = astro.jd_from_datetime(now)
    cur_sy, cur_idx = bazi.year_index_for(jd_now, now.year)

    return {
        "system": "eto",
        "status": status,
        "input": {"birth_date": birth_date, "birth_time": birth_time},
        "year_risshun": {**_gz(yidx), "solar_year": solar_year,
                         "risshun_at": rs_dt.strftime("%Y-%m-%d %H:%M")},
        "year_calendar": {**_gz(cal_idx), "year": y},
        "year_differs": differs,
        "animal": ANIMALS[cal_idx % 12],
        "animal_risshun": ANIMALS[yidx % 12],
        "day": _gz(bazi.day_index(y, m, d)),
        "current": {
            "as_of": now.strftime("%Y-%m-%d"),
            "year_risshun": {**_gz(cur_idx), "solar_year": cur_sy},
            "year_calendar": {**_gz((now.year - 4) % 60), "year": now.year},
            "day": _gz(bazi.day_index(now.year, now.month, now.day)),
        },
        "conventions": CONVENTIONS,
        "warnings": warnings,
        "unavailable": [],
    }
