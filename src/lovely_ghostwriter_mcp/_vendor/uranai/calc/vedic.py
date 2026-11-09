"""インド占星術（ジョーティシュ）— サイデリアル方式の月のラーシ・ナクシャトラ・パーダと太陽のラーシ.

アヤナムシャ（ラーヒリ）:
  ayanamsa(T) = 23.85306° + (5029.0966″·T + 1.11113″·T²) / 3600
  T = (JD_TT − 2451545.0) / 36525（J2000.0 からのユリウス世紀）
  23.85306° は J2000.0 における平均ラーヒリ値、括弧内は IAU 2006 の一般歳差（黄経方向。約50.29″/年）。
  章動は含めない平均アヤナムシャ（真アヤナムシャとの差は最大約0.005°）。
"""
from __future__ import annotations

from datetime import datetime

from . import astro

RASHI = ["メーシャ（牡羊）", "ヴリシャバ（牡牛）", "ミトゥナ（双子）", "カルカ（蟹）", "シンハ（獅子）", "カニヤー（乙女）",
         "トゥラー（天秤）", "ヴリシュチカ（蠍）", "ダヌ（射手）", "マカラ（山羊）", "クンバ（水瓶）", "ミーナ（魚）"]
NAKSHATRA = ["アシュヴィニー", "バラニー", "クリッティカー", "ローヒニー", "ムリガシラー", "アールドラー", "プナルヴァス",
             "プシュヤ", "アーシュレーシャー", "マガー", "プールヴァ・パルグニー", "ウッタラ・パルグニー", "ハスタ", "チトラー",
             "スヴァーティー", "ヴィシャーカー", "アヌラーダー", "ジェーシュター", "ムーラ", "プールヴァ・アーシャーダー",
             "ウッタラ・アーシャーダー", "シュラヴァナ", "ダニシュター", "シャタビシャー", "プールヴァ・バードラパダー",
             "ウッタラ・バードラパダー", "レーヴァティー"]
NAK_SPAN = 40.0 / 3.0   # 13°20'
PADA_SPAN = 10.0 / 3.0  # 3°20'
AYANAMSA_J2000 = 23.85306

CONVENTIONS = [
    "サイデリアル方式（恒星基準）。アヤナムシャはラーヒリ（チトラパクシャ）: J2000.0で23.85306°＋一般歳差（5029.0966″T＋1.11113″T²、約50.29″/年）の平均値",
    "月・太陽の視黄経（トロピカル）は太陽VSOP87短縮式・月Meeus第47章主要項で計算し、アヤナムシャを差し引いてサイデリアル黄経とする",
    "ナクシャトラは27等分（各13°20′）、パーダは各ナクシャトラを4等分（各3°20′）",
    "入力時刻は日本標準時（JST）。出生時刻不明時は12:00 JSTで計算し、その日00:00〜23:59にとりうる範囲を併記",
    "ラグナ（上昇宮）・ハウス・ダシャー（運期）は出生地と正確な時刻が必要で、本アプリでは算出しない",
]
UNAVAILABLE = ["ラグナ（上昇宮）", "ハウス（バーヴァ）", "ダシャー（ヴィムショッタリ等の運期）", "月・太陽以外の惑星"]


def ayanamsa(jd_ut: float) -> float:
    t = (astro._jde(jd_ut) - 2451545.0) / 36525.0
    return AYANAMSA_J2000 + (5029.0966 * t + 1.11113 * t * t) / 3600.0


def sidereal(tropical: float, jd_ut: float) -> float:
    return astro.norm360(tropical - ayanamsa(jd_ut))


def moon_sidereal(jd_ut: float) -> float:
    return sidereal(astro.moon_apparent_longitude(jd_ut), jd_ut)


def sun_sidereal(jd_ut: float) -> float:
    return sidereal(astro.sun_apparent_longitude(jd_ut), jd_ut)


def nakshatra_index(lon: float) -> int:
    return int(lon // NAK_SPAN) % 27


def rashi_info(lon: float) -> dict:
    i = int(lon // 30) % 12
    return {"no": i + 1, "name": RASHI[i], "degree": round(lon - i * 30, 2), "longitude": round(lon, 3)}


def nakshatra_info(lon: float) -> dict:
    i = nakshatra_index(lon)
    within = lon - i * NAK_SPAN
    pada = min(int(within // PADA_SPAN) + 1, 4)
    return {"no": i + 1, "name": NAKSHATRA[i], "pada": pada, "degree_in_nakshatra": round(within, 2)}


def _boundary_distance(lon: float) -> float:
    """Distance (deg) to the nearest nakshatra-pada or rashi boundary (pada boundaries include both)."""
    r = lon % PADA_SPAN
    return min(r, PADA_SPAN - r)


def calculate(birth_date: str, birth_time: str | None = None) -> dict:
    y, m, d = (int(x) for x in birth_date.split("-"))
    has_time = bool(birth_time)
    hh, mi = (int(x) for x in birth_time.split(":")) if has_time else (12, 0)
    jd = astro.jd_from_datetime(datetime(y, m, d, hh, mi, tzinfo=astro.JST))
    warnings: list[str] = []
    moon = moon_sidereal(jd)
    sun = sun_sidereal(jd)
    out = {
        "system": "vedic",
        "status": "ok" if has_time else "partial",
        "input": {"birth_date": birth_date, "birth_time": birth_time},
        "assumed_time": None if has_time else "12:00",
        "ayanamsa": {"name": "ラーヒリ（平均）", "value": round(ayanamsa(jd), 5)},
        "moon": {"rashi": rashi_info(moon), "nakshatra": nakshatra_info(moon)},
        "sun": {"rashi": rashi_info(sun)},
        "range_if_time_unknown": None,
        "conventions": CONVENTIONS,
        "warnings": warnings,
        "unavailable": list(UNAVAILABLE),
    }
    if has_time:
        if _boundary_distance(moon) < 0.5:
            r = moon % NAK_SPAN
            kind = "ナクシャトラ" if min(r, NAK_SPAN - r) < 0.5 else "パーダ"
            r30 = moon % 30
            if min(r30, 30 - r30) < 0.5:
                kind = "ラーシ・ナクシャトラ"
            warnings.append(f"月が{kind}の境界から0.5°以内のため、隣の区分の可能性があります（月は約2時間で1°動く）")
        if (sun % 30) < 0.05 or (sun % 30) > 29.95:
            warnings.append("太陽がラーシの境界付近のため、隣のラーシの可能性があります")
    else:
        jd0 = astro.jd_from_datetime(datetime(y, m, d, 0, 0, tzinfo=astro.JST))
        jd1 = astro.jd_from_datetime(datetime(y, m, d, 23, 59, tzinfo=astro.JST))
        m0, m1 = moon_sidereal(jd0), moon_sidereal(jd1)
        s0, s1 = sun_sidereal(jd0), sun_sidereal(jd1)
        span = (m1 - m0) % 360.0  # moon moves forward ~12-15 deg/day
        n0 = nakshatra_index(m0)
        n_steps = int((m0 % NAK_SPAN + span) // NAK_SPAN)
        naks = [NAKSHATRA[(n0 + k) % 27] for k in range(n_steps + 1)]
        r0 = int(m0 // 30)
        r_steps = int((m0 % 30 + span) // 30)
        rashis = [RASHI[(r0 + k) % 12] for k in range(r_steps + 1)]
        sr0, sr1 = int(s0 // 30) % 12, int(s1 // 30) % 12
        sun_rashis = [RASHI[sr0]] + ([RASHI[sr1]] if sr1 != sr0 else [])
        out["range_if_time_unknown"] = {
            "moon_longitude_from": round(m0, 2), "moon_longitude_to": round(m1, 2),
            "moon_nakshatras": naks, "moon_rashis": rashis, "sun_rashis": sun_rashis,
        }
        warnings.append("出生時刻不明のため12:00 JSTで計算しています。月は1日に約13°動くため、ナクシャトラ・パーダが確定しない場合があります")
        if len(naks) > 1:
            warnings.append("この日のうちに月のナクシャトラが変わります（候補: " + "／".join(naks) + "）")
        if len(rashis) > 1:
            warnings.append("この日のうちに月のラーシが変わります（候補: " + "／".join(rashis) + "）")
        if len(sun_rashis) > 1:
            warnings.append("この日のうちに太陽のラーシが変わります（候補: " + "／".join(sun_rashis) + "）")
        fixed = "月のナクシャトラ・パーダの確定" if len(naks) > 1 else "月のパーダの確定"
        out["unavailable"].insert(0, fixed + "（出生時刻不明）")
    return out
