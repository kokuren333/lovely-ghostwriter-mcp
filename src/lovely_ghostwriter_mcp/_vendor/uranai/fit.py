"""A4 1枚に収める自動調整（印刷版・デジタル版の両方。2枚になるくらいなら詰める→要約する）.

AMENDMENT_08: デジタル版も「A4・ちょうど1ページ」が絶対条件。縦に伸ばして逃げない。
両版は「同じ鑑定内容の2つのスキン」なので、項目（占術の結果／4テーマの4層／統合解釈／自己申告照合／回答の4層／注意）は
どのレベルでも同じ。レベルが上がると文字サイズと字数だけが詰まる。

印刷版（白黒・感熱。最小 8.5pt）
  P0 本文 9.5pt・短縮テキスト（print_* / *_print）
  P1 本文 9.0pt
  P2 占術別の短文を省略（図表の値は残す。短文はデジタル版に残る）
  P3 本文 8.8pt
  P4 本文 8.5pt（下限）
  P5 一致/ずれは各1件・注意書き省略
  P6 文・読点の単位で字数を詰める・固定文は短い版
  P7 最終段（要約）: さらに詰め、ブレンド欄の担当表記を省略

デジタル版（カラー。画面とA4ラスタ画像で読む。①所見②レンズ③なぜ④一歩を別々の行で出すことを優先）
  D0 本文 8.4pt・全文
  D1 8.0pt  D2 7.6pt
  D3 占術別の短文を短縮版に
  D4 7.3pt・一致/ずれは各1件・注意書き省略
  D5 7.0pt
  D6 4テーマと回答を短縮版に（③は②の短縮版に統合）
  D7 7.0pt  D8 占術別の短文を省略（ケルティッククロスの位置ごとの一言は残す）
  D9 最終段: 位置ごとの一言も省略・字数を詰める

「一歩」（step）はどのレベルでも削らない（行動が途中で切れると意味をなさないため。スキーマで30字前後に抑えている）。
"""
from __future__ import annotations

import re

from . import psych

PRINT_LEVELS = [
    {"font_pt": 9.5},
    {"font_pt": 9.0},
    {"font_pt": 9.0, "no_sys": True},
    {"font_pt": 8.8, "no_sys": True},
    {"font_pt": 8.5, "no_sys": True},
    {"font_pt": 8.5, "no_sys": True, "one_each": True, "no_warnings": True},
    {"font_pt": 8.5, "no_sys": True, "limits": {"tf": 28, "tl": 40, "synth": 60, "af": 34, "al": 42, "self": 36, "headline": 28, "caution": 30},
     "one_each": True, "no_warnings": True, "frame_short": True},
    {"font_pt": 8.5, "no_sys": True, "limits": {"tf": 22, "tl": 30, "synth": 40, "af": 26, "al": 32, "self": 26, "headline": 22, "caution": 24},
     "one_each": True, "no_warnings": True, "frame_short": True, "compact": True},
]
DIGITAL_LEVELS = [  # 1ページ目（プロフィール）用。AMENDMENT_09: ケルティッククロスの位置ごとの一言（cross_notes）は D8 まで残す
    {"font_pt": 8.2, "full": True},
    {"font_pt": 7.8, "full": True},
    {"font_pt": 7.5, "full": True},
    {"font_pt": 7.5, "full": True, "short_sys": True},
    {"font_pt": 7.2, "full": True, "short_sys": True, "one_each": True, "no_warnings": True},
    {"font_pt": 7.0, "full": True, "short_sys": True, "one_each": True, "no_warnings": True},
    {"font_pt": 7.2, "short_sys": True, "one_each": True, "no_warnings": True},
    {"font_pt": 7.0, "short_sys": True, "one_each": True, "no_warnings": True},
    {"font_pt": 7.0, "no_sys": True, "one_each": True, "no_warnings": True},
    {"font_pt": 7.0, "no_sys": True, "one_each": True, "no_warnings": True, "no_cross_notes": True,
     "limits": {"tf": 28, "tl": 40, "synth": 60, "af": 34, "al": 42, "self": 36, "headline": 28}},
]
# 2ページ目（予言詩・BRIEF §4）用。詩は削らず、文字サイズ・行間・連の間隔・本文の開始位置だけで1ページに収める。
# 生成側の上限（600〜900字・3〜8連・合計32行・1行40字以内。psych.POEM_*）と併用し、W0 で典型（4〜6連×4行）、
# W3 で7連×4行、W6 で上限（8連×4行・900字）が収まる設計。行は折り返さない幅（本文幅 162mm）。
POEM_LEVELS = [
    {"font_pt": 10.6, "line_height": 1.9, "para_gap_em": 1.1, "title_pt": 17, "orn_top_mm": 92, "body_top_mm": 99},
    {"font_pt": 10.2, "line_height": 1.85, "para_gap_em": 1.0, "title_pt": 17, "orn_top_mm": 90, "body_top_mm": 97},
    {"font_pt": 9.8, "line_height": 1.8, "para_gap_em": 0.95, "title_pt": 16, "orn_top_mm": 88, "body_top_mm": 95},
    {"font_pt": 9.4, "line_height": 1.75, "para_gap_em": 0.9, "title_pt": 16, "orn_top_mm": 86, "body_top_mm": 93},
    {"font_pt": 9.0, "line_height": 1.7, "para_gap_em": 0.85, "title_pt": 15, "orn_top_mm": 84, "body_top_mm": 90},
    {"font_pt": 8.6, "line_height": 1.65, "para_gap_em": 0.8, "title_pt": 15, "orn_top_mm": 82, "body_top_mm": 88},
    {"font_pt": 8.2, "line_height": 1.6, "para_gap_em": 0.7, "title_pt": 14, "orn_top_mm": 82, "body_top_mm": 88},
]
LEVELS = PRINT_LEVELS  # 後方互換


def shorten(text: str, limit: int) -> str:
    text = text.strip()
    if limit <= 0 or len(text) <= limit:
        return text
    sentences = re.findall(r"[^。！？!?]+[。！？!?]?", text)
    out = ""
    for s in sentences:
        if len(out) + len(s) > limit:
            break
        out += s
    if not out:
        # 1文が長すぎる場合は、読点（、）の位置で切る。読点が無ければ字数で切る
        head = text[: limit - 1]
        cut = head.rfind("、")
        out = (head[:cut] if cut >= limit // 2 else head) + "…"
    return out


def _lensed(o: dict, full: bool, lim: dict | None, kind: str) -> dict:
    f, l = ("tf", "tl") if kind == "theme" else ("af", "al")
    if full:
        d = {"finding": o["finding"], "lens": o["lens"], "why": o["why"], "step": o["step"]}
    else:
        d = {"finding": o["print_finding"], "lens": o["print_lens"], "why": "", "step": o["step"]}
    if lim:
        d = {"finding": shorten(d["finding"], lim[f]), "lens": shorten(d["lens"], lim[l]), "why": "", "step": d["step"]}
    d["concept"] = o["concept"]
    return d


def texts_for_level(reading: dict, level: int, skin: str = "print") -> dict:
    """Complete text set for one skin at one fit level (templates read only from this)."""
    levels = PRINT_LEVELS if skin == "print" else DIGITAL_LEVELS
    cfg = levels[level]
    lim = cfg.get("limits")
    full = bool(cfg.get("full"))
    ig = reading["integration"]
    t: dict = {"font_pt": cfg["font_pt"], "level": level, "skin": skin, "full": full}
    t["headline"] = shorten(reading["headline"], lim["headline"]) if lim else reading["headline"]
    t["themes"] = {k: _lensed(v, full, lim, "theme") for k, v in reading["themes"].items()}
    t["answer"] = _lensed(reading["answer"], full, lim, "answer")
    t["synthesis"] = ig["synthesis"] if full else ig["synthesis_print"]
    t["self_report"] = ig["self_report_link"] if full else ig["self_report_print"]
    if lim:
        t["synthesis"] = shorten(t["synthesis"], lim["synth"])
        t["self_report"] = shorten(t["self_report"], lim["self"])
    if cfg.get("no_sys"):
        t["sys"] = {}
    elif skin == "digital" and not cfg.get("short_sys"):
        t["sys"] = {r["system"]: r["reading"] for r in reading["system_readings"]}
    else:
        t["sys"] = {r["system"]: r["reading_print"] for r in reading["system_readings"]}
    t["agreements"] = ig["agreements"][:1] if cfg.get("one_each") else ig["agreements"]
    t["differences"] = ig["differences"][:1] if cfg.get("one_each") else ig["differences"]
    t["show_warnings"] = not cfg.get("no_warnings")
    t["compact"] = bool(cfg.get("compact"))
    t["cross_notes"] = not cfg.get("no_cross_notes")
    t["caution"] = shorten(reading["advice"]["caution"], lim["caution"]) if lim and "caution" in lim else reading["advice"]["caution"]
    # 二層構造の明示（固定文）はどのレベルでも必ず1回だけ出す。最終段では短い版
    t["frame"] = psych.FRAME_NOTE_SHORT if cfg.get("frame_short") else psych.FRAME_NOTE
    return t


def poem_texts(level: int) -> dict:
    """2ページ目（予言詩）の組版パラメータ（POEM_LEVELS）."""
    return {**POEM_LEVELS[level], "level": level}
