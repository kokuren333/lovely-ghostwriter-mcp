"""西洋占星術（MVP範囲）: 太陽星座・月星座・ASC。出生時刻と出生地が揃った場合のみ."""
from __future__ import annotations

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from . import astro

SIGNS = ["牡羊座", "牡牛座", "双子座", "蟹座", "獅子座", "乙女座", "天秤座", "蠍座", "射手座", "山羊座", "水瓶座", "魚座"]
SIGN_EL = ["火", "地", "風", "水"] * 3
SIGN_MODE = ["活動", "不動", "柔軟"] * 4
DATA = Path(__file__).resolve().parent.parent / "data" / "prefectures.json"
CONVENTIONS = [
    "トロピカル方式。太陽はVSOP87短縮式、月はMeeus第47章の主要項で視黄経を計算",
    "ASCは地方恒星時・黄道傾斜角・出生地緯度から計算（出生地は都道府県庁所在地の座標、または緯度経度の直接入力）",
    "入力時刻は日本標準時（JST）",
    "惑星（水星〜冥王星）とハウスはMVP範囲外のため未算出",
]


@lru_cache(maxsize=1)
def prefectures() -> list[dict]:
    return json.loads(DATA.read_text(encoding="utf-8"))["prefectures"]


def resolve_place(place: str | None):
    if not place:
        return None
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)\s*$", place)
    if m:
        return {"label": f"緯度{m.group(1)} 経度{m.group(2)}", "lat": float(m.group(1)), "lon": float(m.group(2)), "precision": "座標入力"}
    for p in prefectures():
        short = p["name"].rstrip("都道府県") if p["name"] != "北海道" else "北海道"
        if p["name"] in place or (short and place.startswith(short)):
            return {"label": f"{p['name']}（{p['capital']}の座標で代用）", "lat": p["lat"], "lon": p["lon"], "precision": "都道府県"}
    return None


def sign_of(lon: float) -> dict:
    i = int(lon // 30) % 12
    deg = lon - i * 30
    return {"sign": SIGNS[i], "degree": round(deg, 2), "longitude": round(lon, 3), "element": SIGN_EL[i], "mode": SIGN_MODE[i]}


def calculate(birth_date: str | None, birth_time: str | None, birth_place: str | None,
              time_precision: str = "exact") -> dict:
    out = {"system": "westastro", "conventions": CONVENTIONS, "warnings": []}
    place = resolve_place(birth_place)
    missing = []
    if not birth_date:
        missing.append("生年月日")
    if not birth_time or time_precision == "unknown":
        missing.append("出生時刻")
    if not place:
        missing.append("出生地（都道府県名または『緯度,経度』）")
    if missing:
        return {**out, "status": "unavailable", "reason": "不足: " + "・".join(missing), "unavailable": ["太陽・月・ASC"]}
    y, m, d = (int(x) for x in birth_date.split("-"))
    hh, mi = (int(x) for x in birth_time.split(":"))
    jd = astro.jd_from_datetime(datetime(y, m, d, hh, mi, tzinfo=astro.JST))
    sun = sign_of(astro.sun_apparent_longitude(jd))
    moon = sign_of(astro.moon_apparent_longitude(jd))
    asc = sign_of(astro.ascendant(jd, place["lat"], place["lon"]))
    for label, body, tol in (("太陽", sun, 0.05), ("月", moon, 0.5), ("ASC", asc, 1.5)):
        if body["degree"] < tol or body["degree"] > 30 - tol:
            out["warnings"].append(f"{label}が星座の境界付近（{body['sign']}{body['degree']}度）のため、隣の星座の可能性があります")
    if time_precision == "approximate":
        out["warnings"].append("出生時刻がおおよそのため、ASC（約4分で1度動く）と月星座の精度は低めです")
    return {**out, "status": "ok", "place": place, "sun": sun, "moon": moon, "ascendant": asc,
            "unavailable": ["惑星（水星〜冥王星）", "ハウス"]}
