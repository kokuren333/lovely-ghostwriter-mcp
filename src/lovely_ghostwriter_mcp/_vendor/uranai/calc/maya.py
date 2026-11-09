"""マヤ暦 — ドリームスペル（13の月の暦）の KIN と、歴史的マヤ暦のツォルキン（GMT相関）を併記.

Dreamspell:
  2012-12-21 = KIN 207（青い手・音12）、2013-07-26 = KIN 164。2月29日は数えない（2月28日と同じKIN）。
Classic Maya Tzolk'in:
  GMT相関定数 JDN 584283 = 4 Ajaw。番号 = ((JDN-584283+3) mod 13)+1、日の名 = ((JDN-584283+19) mod 20)+1。
"""
from __future__ import annotations

from datetime import date

from . import astro

SEALS = ["赤い竜", "白い風", "青い夜", "黄色い種", "赤い蛇", "白い世界の橋渡し", "青い手", "黄色い星", "赤い月", "白い犬",
         "青い猿", "黄色い人", "赤い空歩く人", "白い魔法使い", "青い鷲", "黄色い戦士", "赤い地球", "白い鏡", "青い嵐", "黄色い太陽"]
TONES = ["磁気", "月", "電気", "自己存在", "倍音", "律動", "共振", "銀河", "太陽", "惑星", "スペクトル", "水晶", "宇宙"]
TZOLKIN_NAMES = ["Imix", "Ik'", "Ak'b'al", "K'an", "Chikchan", "Kimi", "Manik'", "Lamat", "Muluk", "Ok",
                 "Chuwen", "Eb'", "B'en", "Ix", "Men", "Kib'", "Kab'an", "Etz'nab'", "Kawak", "Ajaw"]
GMT = 584283

ANCHOR = (2012, 12, 21)
ANCHOR_KIN = 207

CONVENTIONS = [
    "「マヤ暦」として日本で広く使われているのは、ホゼ・アグエイアス（José Argüelles）が1987年に発表した現代の体系「ドリームスペル（13の月の暦）」であり、古代マヤ人が用いた歴史的なマヤ暦とは別物（KINの数え方が一致しない）",
    "本アプリはドリームスペルのKIN・太陽の紋章・銀河の音・ウェイブスペルと、歴史的マヤ暦のツォルキン（GMT相関 584283）の両方を併記する",
    "ドリームスペル: 2012年12月21日＝KIN207、2013年7月26日＝KIN164 を基準とし、2月29日は数えない（2月28日と同じKINとして扱う）",
    "太陽の紋章＝(KIN−1) mod 20 番目、銀河の音＝(KIN−1) mod 13 ＋1、ウェイブスペル＝そのKINを含む13日周期の初日（音1）のKINの紋章",
    "歴史的ツォルキン: GMT相関（JDN 584283＝4 Ajaw）。相関定数には584285等の異説があり、その場合は値が2日ずれる",
    "日付はグレゴリオ暦の出生日（時刻は使わない）",
]


def _leap_days_through(d: date) -> int:
    """Number of Feb-29 dates from 0001-01-01 up to and including d."""
    y = d.year
    prev = y - 1
    n = prev // 4 - prev // 100 + prev // 400
    if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0:
        if (d.month, d.day) >= (2, 29):
            n += 1
    return n


def dreamspell_daynum(y: int, m: int, d: int) -> int:
    """Day counter that does not advance on Feb 29."""
    return astro.jdn(y, m, d) - _leap_days_through(date(y, m, d))


def kin_of(y: int, m: int, d: int) -> int:
    off = dreamspell_daynum(y, m, d) - dreamspell_daynum(*ANCHOR)
    return (ANCHOR_KIN - 1 + off) % 260 + 1


def kin_info(kin: int) -> dict:
    seal_no = (kin - 1) % 20 + 1
    tone_no = (kin - 1) % 13 + 1
    wave_kin = (kin - tone_no) % 260 + 1
    wave_seal = (wave_kin - 1) % 20 + 1
    return {
        "kin": kin,
        "seal": {"no": seal_no, "name": SEALS[seal_no - 1]},
        "tone": {"no": tone_no, "name": TONES[tone_no - 1]},
        "wavespell": {"kin": wave_kin, "seal_no": wave_seal, "name": SEALS[wave_seal - 1]},
        "label": f"KIN{kin} {SEALS[seal_no - 1]}・{TONES[tone_no - 1]}の音（音{tone_no}）",
    }


def tzolkin(y: int, m: int, d: int) -> dict:
    j = astro.jdn(y, m, d)
    num = (j - GMT + 3) % 13 + 1
    sign = (j - GMT + 19) % 20 + 1
    return {"number": num, "sign_no": sign, "sign": TZOLKIN_NAMES[sign - 1],
            "label": f"{num} {TZOLKIN_NAMES[sign - 1]}", "correlation": GMT, "jdn": j}


def calculate(birth_date: str) -> dict:
    y, m, d = (int(x) for x in birth_date.split("-"))
    warnings = []
    if (m, d) == (2, 29):
        warnings.append("2月29日生まれ: ドリームスペルでは2月29日を数えない（「0.0 フナブ・ク」の日）ため、2月28日と同じKINを表示しています")
    info = kin_info(kin_of(y, m, d))
    return {
        "system": "maya",
        "status": "ok",
        "input": {"birth_date": birth_date},
        "dreamspell": {**info, "note": "ドリームスペル（1987年、José Argüelles）による現代の体系"},
        "classic_tzolkin": {**tzolkin(y, m, d), "note": "歴史的マヤ暦のツォルキン（GMT相関）"},
        "conventions": CONVENTIONS,
        "warnings": warnings,
        "unavailable": [],
    }
