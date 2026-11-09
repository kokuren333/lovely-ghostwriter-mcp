"""旧暦（太陰太陽暦）— 現行の旧暦（天保暦の定気法による月名付け）を JST で計算する.

方法:
- 朔（新月）: 月と太陽の視黄経の差（離角）= 0 となる瞬間をニュートン法で解く（astro の太陽・月の式を使用）。
- 日の区切り: JST の0時。朔の瞬間を含む JST の日がその月の1日。
- 中気（太陽視黄経が30°の倍数）を含む月に、その中気に対応する月名を与える
  （雨水330°→1月、春分0°→2月、…、冬至270°→11月、大寒300°→12月）。冬至を含む月は必ず11月。
- 閏月: 11月から次の11月までの間（1歳）に月が13個ある場合、その中で最初の「中気を含まない月」を閏月とし、
  直前の月と同じ月名に「閏」を付ける（現代の中国暦と同じ規則。いわゆる2033年問題でもこの規則で一意に決まる）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache

from . import astro

SYNODIC = 29.530588853
_REL_RATE = 12.190749  # mean daily motion of moon minus sun, deg/day

CONVENTIONS = [
    "旧暦は朔（新月）を月の始まり、日本標準時（JST）の0時を日の区切りとする現行旧暦の方式で計算（天文計算: 太陽VSOP87短縮式・月Meeus第47章主要項）",
    "月名は含まれる中気（定気法）で決め、冬至を含む月を11月とする",
    "11月から次の11月までに13か月ある年は、最初の中気を含まない月を閏月とする（現代中国暦と同じ規則。2033年問題もこの規則で処理）",
]


def _jst_date(jd: float) -> date:
    return astro.datetime_from_jd(jd).date()


def elongation(jd_ut: float) -> float:
    return astro.norm360(astro.moon_apparent_longitude(jd_ut) - astro.sun_apparent_longitude(jd_ut))


def new_moon_near(jd_guess: float) -> float:
    """JD_UT of the new moon nearest to jd_guess (within ~half a lunation)."""
    jd = jd_guess
    for _ in range(40):
        e = (elongation(jd) + 180.0) % 360.0 - 180.0
        if abs(e) < 1e-6:
            break
        jd -= e / _REL_RATE
    return jd


def _month_start_containing(jd_event: float) -> float:
    nm = new_moon_near(jd_event)
    if _jst_date(nm) > _jst_date(jd_event):
        nm = new_moon_near(nm - SYNODIC)
    return nm


def _winter_solstice(year: int) -> float:
    guess = astro.jd_from_datetime(datetime(year, 12, 21, 12, tzinfo=astro.JST))
    return astro.find_sun_longitude(270.0, guess)


def _zhongqi_month(lon: float) -> int:
    return (int(round(lon)) // 30 + 1) % 12 + 1


@lru_cache(maxsize=256)
def sui(year: int) -> tuple:
    """Months from the 11th month containing the winter solstice of `year` up to (excluding) the next one.

    Returns tuple of dicts: start_jd, start (date), end (date, exclusive), year, month, leap, zhongqi (list)."""
    ws0, ws1 = _winter_solstice(year), _winter_solstice(year + 1)
    start0, start1 = _month_start_containing(ws0), _month_start_containing(ws1)
    nms = [start0]
    while True:
        nxt = new_moon_near(nms[-1] + SYNODIC)
        if abs(nxt - start1) < 1.0 or nxt > start1:
            break
        nms.append(nxt)
    zqs = []
    for k in range(13):
        lon = (270.0 + 30.0 * k) % 360.0
        jd = ws0 if k == 0 else (ws1 if k == 12 else astro.find_sun_longitude(lon, ws0 + 30.437 * k))
        zqs.append((jd, lon))
    starts = [_jst_date(j) for j in nms] + [_jst_date(start1)]
    months = []
    for i, nm in enumerate(nms):
        inside = [(j, lon) for j, lon in zqs if starts[i] <= _jst_date(j) < starts[i + 1]]
        months.append({"start_jd": nm, "start": starts[i], "end": starts[i + 1], "zhongqi": inside})
    leap_idx = None
    if len(months) == 13:
        leap_idx = next(i for i, mo in enumerate(months) if not mo["zhongqi"])
    num, yr = 11, year
    for i, mo in enumerate(months):
        if i == 0:
            num, leap = 11, False
        elif i == leap_idx:
            leap = True
        else:
            num, leap = num % 12 + 1, False
            if num == 1:
                yr = year + 1
        mo.update({"month": num, "leap": leap, "year": yr})
    return tuple(months)


def _midnight_distance_hours(jd: float) -> float:
    dt = astro.datetime_from_jd(jd)
    secs = dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6
    return min(secs, 86400 - secs) / 3600.0


def lunar_date(y: int, m: int, d: int) -> dict:
    """旧暦 of a Gregorian (JST civil) date."""
    t = date(y, m, d)
    s_year = y if t >= sui(y)[0]["start"] else y - 1
    months = sui(s_year)
    idx = next(i for i, mo in enumerate(months) if mo["start"] <= t < mo["end"])
    mo = months[idx]
    day = (t - mo["start"]).days + 1
    next_nm = months[idx + 1]["start_jd"] if idx + 1 < len(months) else sui(s_year + 1)[0]["start_jd"]
    near = []
    for label, jd in (("この月の朔", mo["start_jd"]), ("次の月の朔", next_nm)):
        if _midnight_distance_hours(jd) < 1.0:
            near.append(f"{label}（{astro.datetime_from_jd(jd):%Y-%m-%d %H:%M} JST）が0時の前後1時間以内")
    is_leap_sui = len(months) == 13
    starts = {x["start"] for x in months} | {months[-1]["end"]}
    for x in months:
        for jd, lon in x["zhongqi"]:
            if not (is_leap_sui or int(round(lon)) == 270):
                continue  # in a 12-month 歳 a shifted 中気 cannot create/move a leap month (冬至 excepted)
            dt = astro.datetime_from_jd(jd)
            secs = dt.hour * 3600 + dt.minute * 60 + dt.second
            after_midnight = secs < 3600 and dt.date() in starts
            before_midnight = secs > 86400 - 3600 and (dt.date() + timedelta(days=1)) in starts
            if after_midnight or before_midnight:
                near.append(f"中気（太陽黄経{int(round(lon))}°, {dt:%Y-%m-%d %H:%M} JST）が月の境目の0時前後1時間以内にあり、閏月・月名の判定に影響しうる")
    return {
        "year": mo["year"], "month": mo["month"], "day": day, "leap": mo["leap"],
        "label": f"{mo['year']}年{'閏' if mo['leap'] else ''}{mo['month']}月{day}日",
        "month_start": mo["start"].isoformat(),
        "new_moon_at": astro.datetime_from_jd(mo["start_jd"]).strftime("%Y-%m-%d %H:%M"),
        "boundary_notes": near,
    }
