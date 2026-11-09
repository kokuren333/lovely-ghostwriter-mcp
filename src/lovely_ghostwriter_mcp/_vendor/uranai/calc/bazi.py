"""四柱推命 (BaZi) — deterministic chart calculation.

Conventions (recorded in output):
- Civil time JST (UTC+9) as entered; no true-solar-time / longitude correction.
- Year boundary = exact 立春 instant; month boundaries = exact 12 jie instants.
- Day boundary = 00:00. 23:00-23:59 births use the NEXT day's stem for the hour pillar (夜子時).
- Five-element count = 8 visible characters (stems + branch main element); weighted variant adds hidden stems.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import astro, solarterms

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = "木火土金水"
STEM_EL = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
BRANCH_EL = [4, 2, 0, 0, 2, 1, 1, 2, 3, 3, 2, 4]
HIDDEN = {  # 本気, 中気, 余気
    "子": "癸", "丑": "己癸辛", "寅": "甲丙戊", "卯": "乙", "辰": "戊乙癸", "巳": "丙庚戊",
    "午": "丁己", "未": "己丁乙", "申": "庚壬戊", "酉": "辛", "戌": "戊辛丁", "亥": "壬甲",
}
TEN_GODS = {  # (relation, same_polarity) -> name
    ("same", True): "比肩", ("same", False): "劫財",
    ("output", True): "食神", ("output", False): "傷官",
    ("wealth", True): "偏財", ("wealth", False): "正財",
    ("officer", True): "偏官", ("officer", False): "正官",
    ("resource", True): "偏印", ("resource", False): "印綬",
}
TWELVE = ["長生", "沐浴", "冠帯", "建禄", "帝旺", "衰", "病", "死", "墓", "絶", "胎", "養"]
CHANGSHENG = {0: 11, 2: 2, 4: 2, 6: 5, 8: 8, 1: 6, 3: 9, 5: 9, 7: 0, 9: 3}  # stem idx -> branch idx of 長生

CONVENTIONS = [
    "入力時刻は日本標準時（JST）。真太陽時・経度補正は行わない",
    "年の区切りは立春の瞬間、月の区切りは12節（節入り）の瞬間（太陽視黄経をVSOP87短縮式で計算）",
    "日の区切りは0時。23時台の出生は時柱のみ翌日の日干で算出（夜子時）",
    "蔵干は本気・中気・余気の三分法（本気を地支の通変星に使用）",
    "五行バランスは天干4＋地支4（本気の五行）の8字で数える。出生時刻不明時は6字",
    "大運は性別と年干の陰陽による標準規則で順逆を決める（陽男陰女＝順行、陰男陽女＝逆行。AMENDMENT_15）。"
    "性別が「その他」・未回答のときだけ、旧フォームの計算区分（任意回答）を使い、それも無ければ省略。立運は節入りまでの日数÷3年",
]

GENDER_LABEL = {"male": "男性", "female": "女性"}


def resolve_daiun_basis(gender: str | None, daiun_basis: str | None) -> tuple[str | None, str | None, str | None]:
    """大運の順逆に使う区分を決める（AMENDMENT_15）。戻り値 (basis, source, note).

    - gender が male/female → その性別を正とする（source="gender"）。daiun_basis と食い違っても gender を優先し note に記録。
    - gender が other/空 → daiun_basis（female/male）があればそれを使う（source="daiun_basis"）。
    - どちらも無い → (None, None, None) で大運は省略。
    """
    if gender in ("male", "female"):
        note = None
        if daiun_basis in ("male", "female") and daiun_basis != gender:
            note = "大運の計算区分（旧質問）と性別が食い違ったため、性別を優先"
        return gender, "gender", note
    if daiun_basis in ("male", "female"):
        return daiun_basis, "daiun_basis", None
    return None, None, None


def ganzhi_name(idx60: int) -> str:
    return STEMS[idx60 % 10] + BRANCHES[idx60 % 12]


def ganzhi_index(stem: int, branch: int) -> int:
    for i in range(60):
        if i % 10 == stem and i % 12 == branch:
            return i
    raise ValueError("invalid stem/branch parity")


def day_index(y: int, m: int, d: int) -> int:
    """Sexagenary day index (0=甲子). Anchor: 1949-10-01 甲子, 2000-01-01 戊午."""
    return (astro.jdn(y, m, d) + 49) % 60


def ten_god(day_stem: int, other_stem: int) -> str:
    de, oe = STEM_EL[day_stem], STEM_EL[other_stem]
    same_pol = (day_stem % 2) == (other_stem % 2)
    if de == oe:
        rel = "same"
    elif (de + 1) % 5 == oe:
        rel = "output"
    elif (de + 2) % 5 == oe:
        rel = "wealth"
    elif (oe + 2) % 5 == de:
        rel = "officer"
    else:
        rel = "resource"
    return TEN_GODS[(rel, same_pol)]


def twelve_stage(day_stem: int, branch: int) -> str:
    start = CHANGSHENG[day_stem]
    off = (branch - start) % 12 if day_stem % 2 == 0 else (start - branch) % 12
    return TWELVE[off]


def year_index_for(jd_ut: float, civil_year: int) -> tuple[int, int]:
    """Return (solar_year, idx60) using the 立春 boundary."""
    y = civil_year if jd_ut >= solarterms.risshun(civil_year) else civil_year - 1
    return y, (y - 4) % 60


def month_index_for(jd_ut: float, civil_year: int, year_stem: int):
    prev, nxt = solarterms.surrounding_jie(jd_ut, civil_year)
    branch = prev[2]
    k = (branch - 2) % 12  # months counted from 寅
    stem = (year_stem * 2 + 2 + k) % 10
    return ganzhi_index(stem, branch), prev, nxt


def hour_branch(hour: int, minute: int) -> int:
    return ((hour * 60 + minute + 60) // 120) % 12


def _pillar(idx60: int, day_stem: int | None, is_day: bool = False) -> dict:
    s, b = idx60 % 10, idx60 % 12
    p = {
        "ganzhi": ganzhi_name(idx60), "stem": STEMS[s], "branch": BRANCHES[b],
        "stem_element": ELEMENTS[STEM_EL[s]], "branch_element": ELEMENTS[BRANCH_EL[b]],
        "stem_yinyang": "陽" if s % 2 == 0 else "陰",
        "hidden_stems": list(HIDDEN[BRANCHES[b]]),
    }
    if day_stem is not None:
        p["tsuhen_stem"] = "日主" if is_day else ten_god(day_stem, s)
        p["tsuhen_branch"] = ten_god(day_stem, STEMS.index(HIDDEN[BRANCHES[b]][0]))
        p["twelve_stage"] = twelve_stage(day_stem, b)
    return p


def calculate(birth_date: str, birth_time: str | None, daiun_basis: str | None = None,
              now: datetime | None = None, gender: str | None = None) -> dict:
    """birth_date 'YYYY-MM-DD'; birth_time 'HH:MM' or None; daiun_basis 'female'|'male'|None;
    gender 'male'|'female'|'other'|''|None（male/female なら daiun_basis より優先。resolve_daiun_basis 参照）."""
    y, m, d = (int(x) for x in birth_date.split("-"))
    has_time = bool(birth_time)
    hh, mi = (int(x) for x in birth_time.split(":")) if has_time else (12, 0)
    local = datetime(y, m, d, hh, mi, tzinfo=astro.JST)
    jd = astro.jd_from_datetime(local)
    warnings: list[str] = []

    solar_year, yidx = year_index_for(jd, y)
    midx, prev_jie, next_jie = month_index_for(jd, y, yidx % 10)
    didx = day_index(y, m, d)
    day_stem = didx % 10

    hidx = None
    if has_time:
        hb = hour_branch(hh, mi)
        stem_day = didx
        if hh >= 23:
            nd = local + timedelta(days=1)
            stem_day = day_index(nd.year, nd.month, nd.day)
        hidx = ganzhi_index((stem_day % 10 * 2 + hb) % 10, hb)

    # boundary checks (birth time unknown -> whole day is uncertain if a jie falls on that date)
    for j in (prev_jie, next_jie):
        dt_j = astro.datetime_from_jd(j[0])
        if has_time:
            if abs(j[0] - jd) * 24 <= 2:
                warnings.append(f"節入り（{j[1]} {dt_j:%Y-%m-%d %H:%M}）の前後2時間以内の出生のため、年柱/月柱が境界付近です")
        elif dt_j.date() == local.date():
            warnings.append(f"出生日に節入り（{j[1]} {dt_j:%H:%M}）があり、出生時刻不明のため年柱/月柱は正午出生として仮定しています")
    if has_time and hh >= 23:
        warnings.append("23時台の出生のため、時柱は翌日の日干で算出（夜子時。流派により異なる）")

    pillars = {
        "year": _pillar(yidx, day_stem), "month": _pillar(midx, day_stem),
        "day": _pillar(didx, day_stem, is_day=True), "hour": _pillar(hidx, day_stem) if hidx is not None else None,
    }

    counts = {e: 0 for e in ELEMENTS}
    weighted = {e: 0.0 for e in ELEMENTS}
    for p in pillars.values():
        if p is None:
            continue
        counts[p["stem_element"]] += 1
        counts[p["branch_element"]] += 1
        weighted[p["stem_element"]] += 1.0
        hs = p["hidden_stems"]
        w = [0.6, 0.3, 0.1] if len(hs) == 3 else ([0.7, 0.3] if len(hs) == 2 else [1.0])
        for st, ww in zip(hs, w):
            weighted[ELEMENTS[STEM_EL[STEMS.index(st)]]] += ww
    weighted = {k: round(v, 2) for k, v in weighted.items()}

    de = STEM_EL[day_stem]
    support_els = {ELEMENTS[de], ELEMENTS[(de + 4) % 5]}  # same + resource
    score = 0.0
    total = 0.0
    for key, p in pillars.items():
        if p is None:
            continue
        for el, wt in ((p["stem_element"], 1.0), (p["branch_element"], 2.0 if key == "month" else 1.0)):
            if key == "day" and el == p["stem_element"] and wt == 1.0:
                continue  # skip the day master itself
            total += wt
            if el in support_els:
                score += wt
    ratio = score / total if total else 0
    label = "身強寄り" if ratio >= 0.55 else ("身弱寄り" if ratio <= 0.35 else "中庸")

    xun_start = didx - didx % 10
    kuubou = [BRANCHES[(xun_start + 10) % 12], BRANCHES[(xun_start + 11) % 12]]

    daiun: dict
    basis, basis_source, basis_note = resolve_daiun_basis(gender, daiun_basis)
    if basis in ("female", "male"):
        yang_year = (yidx % 10) % 2 == 0
        forward = (yang_year and basis == "male") or ((not yang_year) and basis == "female")
        target = next_jie[0] if forward else prev_jie[0]
        days = abs(target - jd)
        years_f = days / 3.0
        sy = int(years_f)
        sm = int(round((years_f - sy) * 12))
        if sm == 12:
            sy, sm = sy + 1, 0
        periods = []
        for k in range(1, 9):
            idx = (midx + (k if forward else -k)) % 60
            periods.append({"age_from": sy + 10 * (k - 1), "ganzhi": ganzhi_name(idx),
                            "tsuhen": ten_god(day_stem, idx % 10)})
        daiun = {"omitted": False, "direction": "順行" if forward else "逆行",
                 "start_age": {"years": sy, "months": sm}, "periods": periods,
                 "basis": (f"性別（{GENDER_LABEL[basis]}）と年干の陰陽（{'陽' if yang_year else '陰'}）による標準規則"
                           if basis_source == "gender" else
                           ("女性として計算" if basis == "female" else "男性として計算") + "（旧フォームの計算区分）"),
                 "basis_source": basis_source}
        if basis_note:
            daiun["basis_note"] = basis_note
        if not has_time:
            warnings.append("出生時刻不明のため立運年齢は正午出生として概算")
    else:
        daiun = {"omitted": True, "reason": "性別が「その他」または未回答で、大運の計算区分も未選択のため省略"}

    now = now or datetime.now(astro.JST)
    jd_now = astro.jd_from_datetime(now)
    cur_sy, cur_yidx = year_index_for(jd_now, now.year)
    cur_midx, _, _ = month_index_for(jd_now, now.year, cur_yidx % 10)

    return {
        "system": "bazi",
        "status": "ok" if has_time else "partial",
        "input": {"birth_date": birth_date, "birth_time": birth_time, "daiun_basis": daiun_basis, "gender": gender or ""},
        "solar_year": solar_year,
        "pillars": pillars,
        "day_master": {"stem": STEMS[day_stem], "element": ELEMENTS[de], "yinyang": "陽" if day_stem % 2 == 0 else "陰"},
        "five_elements": {"counts": counts, "weighted_with_hidden": weighted,
                          "basis_chars": 8 if has_time else 6},
        "strength": {"support_ratio": round(ratio, 3), "label": label,
                     "method": "日干と同五行・生じる五行の比率（月支2倍）による簡易目安"},
        "kuubou": kuubou,
        "daiun": daiun,
        "current": {"year_ganzhi": ganzhi_name(cur_yidx), "month_ganzhi": ganzhi_name(cur_midx),
                    "year_tsuhen": ten_god(day_stem, cur_yidx % 10), "as_of": now.strftime("%Y-%m-%d")},
        "jie": {"prev": {"name": prev_jie[1], "at": astro.datetime_from_jd(prev_jie[0]).strftime("%Y-%m-%d %H:%M")},
                "next": {"name": next_jie[1], "at": astro.datetime_from_jd(next_jie[0]).strftime("%Y-%m-%d %H:%M")}},
        "unavailable": [] if has_time else ["時柱（出生時刻不明）"],
        "warnings": warnings,
        "conventions": CONVENTIONS,
    }
