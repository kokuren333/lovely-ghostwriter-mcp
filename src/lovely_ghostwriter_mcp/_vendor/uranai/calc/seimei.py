"""姓名判断 — 五格（天格・人格・地格・外格・総格）。画数は出典付きデータのみ使用し、推測しない."""
from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OVERRIDES = ROOT.parent / "config" / "stroke_overrides.json"

KICHI = {1, 3, 5, 6, 7, 8, 11, 13, 15, 16, 17, 18, 21, 23, 24, 25, 29, 31, 32, 33, 35, 37, 38, 39, 41, 45, 47, 48,
         52, 57, 58, 61, 63, 65, 67, 68, 81}
HANKICHI = {26, 27, 30, 36, 40, 42, 51, 53, 55, 73, 75, 77, 78}

CONVENTIONS = [
    "漢字の画数: Unicode Unihan Database の kRSAdobe_Japan1_6（日本字形の部首画数＋残り画数＝新字体の総画数）。旧字体で数える流派とは異なる場合あり",
    "かなの画数: 本アプリ収録の一般的な画数表（濁点+2、半濁点+1）",
    "「々」は直前の字と同じ画数として数える",
    "霊数は加えない。1字姓かつ1字名の場合、外格は算出しない",
    "吉凶は一般に流布する81数の吉凶表の一例（82以上は80を引く）。流派により異なる",
    "画数データに無い字は推測せず『判定不可』とし、その字に依存する格も判定不可とする",
]


@lru_cache(maxsize=1)
def _tables():
    uni = json.loads((DATA / "strokes_unihan.json").read_text(encoding="utf-8"))
    kana = json.loads((DATA / "kana_strokes.json").read_text(encoding="utf-8"))
    ov = {}
    if OVERRIDES.exists():
        ov = json.loads(OVERRIDES.read_text(encoding="utf-8")).get("chars", {})
    return uni, kana, ov


def source_meta() -> dict:
    uni, _, _ = _tables()
    m = uni["_meta"]
    return {"kanji": f"{m['source']}（{m['unihan_date'].split(' ')[0]}版, {m['license']}）", "kanji_url": m["url"],
            "kana": "本アプリ収録の画数表"}


def char_strokes(ch: str, prev: int | None = None):
    """Return (strokes or None, source_label)."""
    uni, kana, ov = _tables()
    if ch in ov:
        return int(ov[ch]["strokes"]), "override:" + ov[ch].get("source", "設定ファイル")
    if ch == "々":
        return (prev, "repeat-mark") if prev else (None, "repeat-mark-without-prev")
    if ch in uni["strokes"]:
        return uni["strokes"][ch], "unihan"
    if ch == "ー":
        return kana["long_mark"], "kana"
    base = unicodedata.normalize("NFD", ch)
    core, marks = base[0], base[1:]
    add = sum(kana["dakuten"] if mk == "゙" else kana["handakuten"] if mk == "゚" else 0 for mk in marks)
    small = {"ぁ": "あ", "ぃ": "い", "ぅ": "う", "ぇ": "え", "ぉ": "お", "っ": "つ", "ゃ": "や", "ゅ": "ゆ", "ょ": "よ",
             "ァ": "ア", "ィ": "イ", "ゥ": "ウ", "ェ": "エ", "ォ": "オ", "ッ": "ツ", "ャ": "ヤ", "ュ": "ユ", "ョ": "ヨ"}
    core = small.get(core, core)
    for tbl in ("hiragana", "katakana"):
        if core in kana[tbl]:
            return kana[tbl][core] + add, "kana"
    return None, "not-found"


def fortune_label(n: int) -> str:
    k = n
    while k > 81:
        k -= 80
    return "吉" if k in KICHI else ("半吉" if k in HANKICHI else "凶")


def _sum(vals):
    return None if any(v is None for v in vals) else sum(vals)


def calculate(surname: str | None, given: str | None) -> dict:
    out = {"system": "seimei", "conventions": CONVENTIONS, "sources": source_meta(), "warnings": []}
    if not surname or not given:
        return {**out, "status": "unavailable", "reason": "漢字（またはかな）の姓と名の両方が必要です", "unavailable": ["五格すべて"]}
    surname = unicodedata.normalize("NFKC", surname).replace(" ", "").replace("　", "")
    given = unicodedata.normalize("NFKC", given).replace(" ", "").replace("　", "")
    chars = []
    prev = None
    for part, s in (("姓", surname), ("名", given)):
        for ch in s:
            n, src = char_strokes(ch, prev)
            chars.append({"char": ch, "part": part, "strokes": n, "source": src})
            prev = n
    sur = [c["strokes"] for c in chars if c["part"] == "姓"]
    giv = [c["strokes"] for c in chars if c["part"] == "名"]
    unknown = [c["char"] for c in chars if c["strokes"] is None]
    ten = _sum(sur)
    chi = _sum(giv)
    jin = _sum([sur[-1], giv[0]])
    sou = _sum(sur + giv)
    if len(sur) == 1 and len(giv) == 1:
        gai, gai_note = None, "1字姓・1字名のため外格は算出しない（霊数を用いない流派）"
    else:
        gai = None if sou is None or jin is None else sou - jin
        gai_note = None
    kaku = {}
    for key, label, val, meaning in (
        ("tenkaku", "天格", ten, "家系・先祖から受け継ぐもの"), ("jinkaku", "人格", jin, "性格の中心・主運"),
        ("chikaku", "地格", chi, "若年期・素質"), ("gaikaku", "外格", gai, "対人関係・社会運"),
        ("soukaku", "総格", sou, "人生全体・晩年運"),
    ):
        kaku[key] = {"label": label, "value": val, "fortune": fortune_label(val) if val else None,
                     "meaning": meaning, "status": "ok" if val else "判定不可"}
    if gai_note:
        kaku["gaikaku"]["status"] = "算出なし"
        kaku["gaikaku"]["note"] = gai_note
    if unknown:
        out["warnings"].append("画数データに無い字があるため一部判定不可: " + "".join(unknown))
    status = "ok" if not unknown else ("partial" if any(v["value"] for v in kaku.values()) else "unavailable")
    return {**out, "status": status, "surname": surname, "given": given, "chars": chars, "gokaku": kaku,
            "unknown_chars": unknown}
