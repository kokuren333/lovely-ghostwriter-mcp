"""calc.json → 鑑定書に載せる図表データ（印刷版・デジタル版共通）。選ばれた占術の分だけ作る."""
from __future__ import annotations

from . import catalog


def _w(r: dict) -> list[str]:
    return list(r.get("warnings") or [])


def bazi(r):
    cols = [("年柱", "year"), ("月柱", "month"), ("日柱", "day"), ("時柱", "hour")]
    head = [c for c, _ in cols]
    rows = []
    for label, key in (("天干", "stem"), ("地支", "branch"), ("通変星", "tsuhen_stem"), ("十二運", "twelve_stage")):
        rows.append([label] + [(r["pillars"][k] or {}).get(key, "—") if r["pillars"][k] else "不明" for _, k in cols])
    d = r["daiun"]
    lines = [["日主", f"{r['day_master']['stem']}（{r['day_master']['element']}・{r['day_master']['yinyang']}）"],
             ["身の強さ", r["strength"]["label"]], ["空亡", "".join(r["kuubou"])],
             ["今年", f"{r['current']['year_ganzhi']}（{r['current']['year_tsuhen']}）"]]
    if d.get("omitted"):
        lines.append(["大運", "省略（性別の指定なし）"])
    else:
        cur = d["periods"][:3]
        lines.append(["大運", f"{d['direction']}・立運{d['start_age']['years']}歳 " + " ".join(f"{p['age_from']}歳{p['ganzhi']}" for p in cur)])
    return {"table": {"head": [""] + head, "rows": rows}, "rows": lines, "elements": r["five_elements"]["counts"],
            "elements_basis": r["five_elements"]["basis_chars"], "warnings": _w(r) + [f"{u}は判定不可" for u in r.get("unavailable", [])]}


def tarot(r):
    """ケルティッククロス（AMENDMENT_09 §C）。rows は印刷版用の要約（占う対象＋要所の3枚）、cross は10枚すべて（デジタル版）."""
    by = {c["position"]: c for c in r["spread"]}
    tgt = (r.get("target") or {}).get("label") or (r.get("question") or "全体運")
    rows = [["占う対象", tgt if len(tgt) <= 22 else tgt[:21] + "…"]]
    for key in ("present", "challenge", "outcome"):
        c = by.get(key)
        if c:
            rows.append([c["position_label"].split(" ", 1)[-1].replace("（交差）", ""), f"{c['name_ja']}・{c['orientation'][0]}"])
    return {"rows": rows, "cross": r["spread"], "target": tgt, "spread_name": r.get("spread_name", "ケルティッククロス（10枚）"),
            "note": f"ケルティッククロス10枚の要所／正＝正位置・逆＝逆位置／シード {r['seed']}（再現可能な抽選）", "warnings": _w(r)}


def kyusei(r):
    cy = r["current_year"]
    good = "・".join(g["direction"] for g in cy["good_directions"]) or "なし"
    bad = "・".join(f"{b['direction']}" for b in cy["bad_directions"])
    return {"rows": [["本命星", r["honmei"]["name"]], ["月命星", r["getsumei"]["name"]],
                     [f"{cy['solar_year']}年の位置", f"{cy['honmei_palace']}（中宮 {cy['center_star']}）"],
                     ["今年の吉方位", good], ["今年の凶方位", bad]], "warnings": _w(r)}


def numerology(r):
    rows = []
    if "life_path" in r:
        rows += [["ライフパス", str(r["life_path"]["value"])], ["バースデー", str(r["birthday"]["value"])],
                 [f"{r['personal_year']['year']}年のパーソナルイヤー", str(r["personal_year"]["value"])]]
    if "name" in r:
        n = r["name"]
        rows += [["ディスティニー", str(n["destiny"]["value"])], ["ソウル／パーソナリティ", f"{n['soul']['value']}／{n['personality']['value']}"]]
    return {"rows": rows, "note": f"読み: {r['name']['romaji']}" if "name" in r else None,
            "warnings": _w(r) + [f"{u}" for u in r.get("unavailable", [])]}


def seimei(r):
    if r["status"] == "unavailable" and "gokaku" not in r:
        return {"rows": [["判定", "判定不可"]], "note": r.get("reason"), "warnings": _w(r)}
    strokes = " ".join(f"{c['char']}{c['strokes'] if c['strokes'] is not None else '?'}" for c in r["chars"])
    rows = [[v["label"], f"{v['value']}画 {v['fortune']}" if v["value"] else v["status"]] for v in r["gokaku"].values()]
    return {"rows": [["画数", strokes]] + rows, "note": "画数: Unicode Unihan（日本字形）／新字体", "warnings": _w(r)}


def westastro(r):
    if r["status"] != "ok":
        return {"rows": [["判定", "判定不可"]], "note": r.get("reason"), "warnings": _w(r)}
    return {"rows": [["太陽", f"{r['sun']['sign']} {r['sun']['degree']:.0f}°"], ["月", f"{r['moon']['sign']} {r['moon']['degree']:.0f}°"],
                     ["ASC", f"{r['ascendant']['sign']} {r['ascendant']['degree']:.0f}°"]],
            "note": r["place"]["label"], "warnings": _w(r)}


def vedic(r):
    m = r["moon"]
    rows = [["月のラシ", m["rashi"]["name"]], ["ナクシャトラ", f"{m['nakshatra']['name']}（第{m['nakshatra']['pada']}パーダ）"],
            ["太陽のラシ", r["sun"]["rashi"]["name"]]]
    if r.get("range_if_time_unknown"):
        rng = r["range_if_time_unknown"]
        cand = rng.get("nakshatras") or rng.get("moon_nakshatras") or []
        if cand:
            rows.append(["時刻不明の候補", "・".join(c if isinstance(c, str) else c.get("name", "") for c in cand)])
    return {"rows": rows, "note": f"アヤナムシャ {r['ayanamsa']['name']} {r['ayanamsa']['value']:.2f}°", "warnings": _w(r)}


def shukuyo(r):
    return {"rows": [["生まれ宿", r["shuku"]["name"]], ["旧暦", r["lunar_date"]["label"]]], "warnings": _w(r)}


def maya(r):
    d = r["dreamspell"]
    return {"rows": [["KIN", str(d["kin"])], ["太陽の紋章", d["seal"]["name"]], ["銀河の音", f"{d['tone']['no']}（{d['tone']['name']}）"],
                     ["ウェイブスペル", d["wavespell"]["name"]], ["歴史的ツォルキン", r["classic_tzolkin"]["label"]]],
            "note": "KINはドリームスペル（現代の体系）。歴史的マヤ暦とは別", "warnings": _w(r)}


def birthcard(r):
    return {"rows": [[c["role"].split("／")[0] if "（兼）" not in c["role"] else "出生カード", f"{c['number']} {c['name_ja']}"] for c in r["cards"]],
            "note": f"計算: {r['steps']}", "warnings": _w(r)}


def kabbalah(r):
    rows = [["名前の数（カルデア式）", str(r["name"]["value"])]]
    if r.get("birth"):
        rows.append(["誕生数", str(r["birth"]["value"])])
    return {"rows": rows, "note": f"読み: {r['name']['romaji']}", "warnings": _w(r)}


def eto(r):
    rows = [["生まれ年", f"{r['year_risshun']['ganzhi']}（{r['animal_risshun']}）"], ["生まれ日", r["day"]["ganzhi"]]]
    if r.get("year_differs"):
        rows.append(["1月1日区切り", f"{r['year_calendar']['ganzhi']}（{r['year_calendar']['animal']}）"])
    return {"rows": rows, "warnings": _w(r)}


def sanmei(r):
    nxt = r["next_tenchusatsu_years"][:2]
    cur = "今年が天中殺" if r["current"]["is_tenchusatsu_year"] else "今年は該当なし"
    return {"rows": [["天中殺", r["tenchusatsu"]["name"]], ["今年", cur],
                     ["次の天中殺年", "・".join(f"{y['solar_year']}" for y in nxt)]],
            "note": "算命学は天中殺のみ算出（陽占・陰占は未実装）", "warnings": _w(r)}


def birthstone(r):
    return {"rows": [["誕生石", r["label"]]], "note": f"{r['source']}（表の参照）", "warnings": _w(r)}


BUILDERS = {k: v for k, v in globals().items() if k in catalog.CATALOG}


def build(calc: dict) -> list[dict]:
    out = []
    for s in calc["systems"]:
        spec = BUILDERS[s](calc["results"][s])
        spec.update(system=s, name=catalog.CATALOG[s]["name"], tier=catalog.CATALOG[s]["tier"],
                    status=calc["results"][s].get("status", "ok"))
        out.append(spec)
    return out
