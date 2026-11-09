"""九星気学 — 本命星・月命星、年盤/月盤での位置と方位の吉凶（決定論的部分のみ）."""
from __future__ import annotations

from datetime import datetime

from . import astro, solarterms
from .bazi import BRANCHES, year_index_for

STARS = ["", "一白水星", "二黒土星", "三碧木星", "四緑木星", "五黄土星", "六白金星", "七赤金星", "八白土星", "九紫火星"]
STAR_EL = ["", "水", "土", "木", "木", "土", "金", "金", "土", "火"]
# 洛書 (center 5): palace -> star
LOSHU = {"中央": 5, "北": 1, "南西": 2, "東": 3, "南東": 4, "北西": 6, "西": 7, "北東": 8, "南": 9}
OPPOSITE = {"北": "南", "南": "北", "東": "西", "西": "東", "北東": "南西", "南西": "北東", "南東": "北西", "北西": "南東", "中央": None}
BRANCH_DIR = {"子": "北", "丑": "北東", "寅": "北東", "卯": "東", "辰": "南東", "巳": "南東",
              "午": "南", "未": "南西", "申": "南西", "酉": "西", "戌": "北西", "亥": "北西"}
GEN = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}

CONVENTIONS = [
    "年の区切りは立春、月の区切りは節入り（四柱推命と同じ太陽黄経計算）",
    "月命星は本命星グループ（一四七／三六九／二五八）ごとに寅月を八白／五黄／二黒として逆行",
    "盤は中宮星から洛書の飛泊順に配置。凶方は五黄殺・暗剣殺・本命殺・本命的殺・歳破（年盤のみ）・月破（月盤のみ）",
    "吉方位は凶方を除いた宮のうち、本命星と相生・比和の星が入る方位（月命星との併用は流派により異なるため本命星のみで判定）",
]


def year_star(solar_year: int) -> int:
    s = (11 - solar_year % 9) % 9
    return 9 if s == 0 else s


def month_star(year_star_no: int, month_branch: int) -> int:
    start = {1: 8, 4: 8, 7: 8, 3: 5, 6: 5, 9: 5, 2: 2, 5: 2, 8: 2}[year_star_no]
    k = (month_branch - 2) % 12  # 寅月=0
    s = (start - k - 1) % 9 + 1
    return s


def board(center: int) -> dict:
    return {pal: (base - 5 + center - 1) % 9 + 1 for pal, base in LOSHU.items()}


def relation(a: int, b: int) -> str:
    ea, eb = STAR_EL[a], STAR_EL[b]
    if ea == eb:
        return "比和"
    if GEN[ea] == eb or GEN[eb] == ea:
        return "相生"
    return "相剋"


def evaluate_board(center: int, honmei: int, branch: str | None, kind: str) -> dict:
    b = board(center)
    star_pal = {v: k for k, v in b.items()}
    bad: dict[str, list[str]] = {}

    def add(p, name):
        if p and p != "中央":
            bad.setdefault(p, []).append(name)

    p5 = star_pal[5]
    add(p5, "五黄殺")
    add(OPPOSITE[p5], "暗剣殺")
    ph = star_pal[honmei]
    add(ph, "本命殺")
    add(OPPOSITE[ph], "本命的殺")
    if branch:
        add(OPPOSITE[BRANCH_DIR[branch]], "歳破" if kind == "year" else "月破")
    good = []
    for pal, st in b.items():
        if pal == "中央" or pal in bad or st == honmei or st == 5:
            continue
        if relation(honmei, st) in ("相生", "比和"):
            good.append({"direction": pal, "star": STARS[st], "relation": relation(honmei, st)})
    return {
        "center_star": STARS[center],
        "board": {pal: STARS[st] for pal, st in b.items()},
        "honmei_palace": ph,
        "bad_directions": [{"direction": p, "reasons": r} for p, r in bad.items()],
        "good_directions": good,
    }


def calculate(birth_date: str, birth_time: str | None, now: datetime | None = None) -> dict:
    y, m, d = (int(x) for x in birth_date.split("-"))
    hh, mi = (int(x) for x in birth_time.split(":")) if birth_time else (12, 0)
    local = datetime(y, m, d, hh, mi, tzinfo=astro.JST)
    jd = astro.jd_from_datetime(local)
    sy, _ = year_index_for(jd, y)
    hs = year_star(sy)
    prev, nxt = solarterms.surrounding_jie(jd, y)
    gs = month_star(hs, prev[2])
    warnings = []
    for j in (prev, nxt):
        dt_j = astro.datetime_from_jd(j[0])
        if birth_time and abs(j[0] - jd) * 24 <= 2:
            warnings.append(f"節入り（{j[1]}）前後2時間以内の出生のため、本命星/月命星が境界付近です")
        if not birth_time and dt_j.date() == local.date():
            warnings.append(f"出生日に節入り（{j[1]} {dt_j:%H:%M}）があり、出生時刻不明のため正午出生として仮定")

    now = now or datetime.now(astro.JST)
    jdn_ = astro.jd_from_datetime(now)
    cur_sy, cur_yidx = year_index_for(jdn_, now.year)
    cprev, _ = solarterms.surrounding_jie(jdn_, now.year)
    cy_star = year_star(cur_sy)
    cm_star = month_star(cy_star, cprev[2])
    year_eval = evaluate_board(cy_star, hs, BRANCHES[cur_yidx % 12], "year")
    month_eval = evaluate_board(cm_star, hs, BRANCHES[cprev[2]], "month")
    return {
        "system": "kyusei",
        "status": "ok",
        "input": {"birth_date": birth_date, "birth_time": birth_time},
        "honmei": {"no": hs, "name": STARS[hs], "element": STAR_EL[hs], "solar_year": sy},
        "getsumei": {"no": gs, "name": STARS[gs], "element": STAR_EL[gs]},
        "current_year": {"solar_year": cur_sy, **year_eval},
        "current_month": {"jie": cprev[1], **month_eval},
        "as_of": now.strftime("%Y-%m-%d"),
        "warnings": warnings,
        "conventions": CONVENTIONS,
    }
