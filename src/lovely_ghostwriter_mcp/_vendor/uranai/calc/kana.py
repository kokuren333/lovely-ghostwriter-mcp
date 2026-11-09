"""Hiragana/Katakana -> Hepburn romaji (deterministic, documented rules)."""
from __future__ import annotations

import unicodedata

_BASE = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "ゐ": "i", "ゑ": "e", "を": "o", "ん": "n",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ゔ": "vu", "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o",
}
_YOON = {"ゃ": "ya", "ゅ": "yu", "ょ": "yo"}
_SPECIAL = {"しゃ": "sha", "しゅ": "shu", "しょ": "sho", "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
            "じゃ": "ja", "じゅ": "ju", "じょ": "jo", "ぢゃ": "ja", "ぢゅ": "ju", "ぢょ": "jo"}

RULES = "ヘボン式（長音符号なし：おう→ou、ー→直前母音の重ね）。撥音「ん」は n、促音は次の子音を重ねる（ch は tch）"


def to_hiragana(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def to_romaji(kana: str) -> str:
    s = to_hiragana(kana).replace(" ", "").replace("　", "")
    out: list[str] = []
    i = 0
    sokuon = False
    while i < len(s):
        c = s[i]
        if c == "っ":
            sokuon = True
            i += 1
            continue
        if c == "ー":
            if out and out[-1]:
                out.append(out[-1][-1] if out[-1][-1] in "aeiou" else "")
            i += 1
            continue
        pair = s[i:i + 2]
        if pair in _SPECIAL:
            syl = _SPECIAL[pair]
            i += 2
        elif i + 1 < len(s) and s[i + 1] in _YOON and c in _BASE and _BASE[c].endswith("i"):
            syl = _BASE[c][:-1] + _YOON[s[i + 1]]
            i += 2
        elif c in _BASE:
            syl = _BASE[c]
            i += 1
        elif c.isascii() and c.isalpha():
            syl = c.lower()
            i += 1
        else:
            i += 1
            continue
        if sokuon:
            syl = ("t" + syl) if syl.startswith("ch") else (syl[0] + syl)
            sokuon = False
        out.append(syl)
    return "".join(out)
