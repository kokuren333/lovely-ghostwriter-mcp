"""PDF/PNG の自動QA（PyMuPDF）.

デジタル版の合格条件（AMENDMENT_09 §D で更新）: PDF がちょうど2ページ・各ページA4判、2ページ目が詩ページ（詩のタイトルを含む）、
  PNG は1ページ1ファイル（AMENDMENT_17: digital_p1.png＝プロフィール面／digital_p2.png＝詩ページ。縦連結版は廃止）で、
  各 PNG が A4 単ページの縦横比（誤差 < 1%）かつ幅 ≥ settings.render.png_width_px。
  背景アート（AMENDMENT_10）やエンブレム（AMENDMENT_11）が入っても、両ページから実テキストが抽出できること。

印刷版の合格条件:
  pages == 1 / テキスト色はすべて #000000 / ベクター描画の塗り・線は黒か白のみ /
  線幅 >= min_line_pt / 細い黒塗り（罫線相当）の太さ >= min_line_pt / 文字 >= min_font_pt /
  埋め込みラスター画像なし（AMENDMENT_12: 念獣（beast-line.svg）の白黒ベクター線画エンブレムは許可。エンブレムにも黒/白のみ・線幅・グレー塗りの検査が
  そのままかかる）/ 150dpi ラスタで彩度のある画素 0 / 1.7mm角(10px@150dpi)全面中間グレーのブロック 0（グレー塗りの検出）
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pymupdf

from . import psych
from .config import settings


def _is_bw(c) -> bool:
    if c is None:
        return True
    return all(v <= 0.02 for v in c) or all(v >= 0.98 for v in c)


def check_print_pdf(path: Path) -> dict:
    cfg = settings()["print"]
    min_font, min_line = cfg["min_font_pt"], cfg["min_line_pt"]
    doc = pymupdf.open(str(path))
    res = {"file": path.name, "pages": doc.page_count, "checks": {}, "violations": []}
    v = res["violations"]
    if doc.page_count != 1:
        v.append(f"ページ数が {doc.page_count}（1ページ必須）")
    text_colors, small_fonts, min_size = set(), [], 99.0
    bad_draw, thin, images = 0, [], 0
    emblem = {"paths": 0, "thin": 0, "non_bw": 0, "min_width_pt": None}
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if not span["text"].strip():
                        continue
                    text_colors.add(span["color"])
                    min_size = min(min_size, span["size"])
                    if span["size"] < min_font - 0.05:
                        small_fonts.append((span["text"][:12], round(span["size"], 2)))
        er = _emblem_rect(page)
        for d in page.get_drawings():
            in_emb = er is not None and er.contains(d["rect"])
            if in_emb:
                emblem["paths"] += 1
                if d.get("color") is not None and "s" in d.get("type", ""):
                    w = d.get("width") or 0
                    emblem["min_width_pt"] = round(w if emblem["min_width_pt"] is None else min(emblem["min_width_pt"], w), 2)
                    if w < 1.0 - 0.01:  # AMENDMENT_12: エンブレムの線は最終サイズで 1pt 以上
                        emblem["thin"] += 1
                if not (_is_bw(d.get("color")) and _is_bw(d.get("fill"))):
                    emblem["non_bw"] += 1
            if not (_is_bw(d.get("color")) and _is_bw(d.get("fill"))):
                bad_draw += 1
            if d.get("color") is not None and "s" in d.get("type", "") and (d.get("width") or 0) < min_line - 0.01:
                thin.append(("stroke", round(d.get("width") or 0, 2)))
            if d.get("fill") is not None and all(x <= 0.02 for x in d["fill"]) and d.get("type") == "f":
                r = d["rect"]
                m = min(r.width, r.height)
                if 0 < m < min_line - 0.01:
                    thin.append(("fill", round(m, 2)))
        images += len(page.get_images(full=True))
    if any(c != 0 for c in text_colors):
        v.append(f"黒以外の文字色: {sorted(hex(c) for c in text_colors if c != 0)}")
    if small_fonts:
        v.append(f"最小文字サイズ違反 {len(small_fonts)}件: {small_fonts[:3]}")
    if bad_draw:
        v.append(f"黒/白以外の色の描画 {bad_draw}件")
    if thin:
        v.append(f"細すぎる線 {len(thin)}件: {thin[:3]}")
    if images:
        v.append(f"埋め込みラスター画像 {images}件（ベクターのみ。線画エンブレムはベクターなので対象外）")
    if emblem["thin"]:
        v.append(f"エンブレムの線が 1pt 未満: {emblem['thin']}件（最小 {emblem['min_width_pt']}pt）")
    # raster checks
    pix = doc[0].get_pixmap(dpi=150, colorspace=pymupdf.csRGB)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).astype(np.int16)
    chroma = (a.max(axis=2) - a.min(axis=2))
    color_px = int((chroma > 24).sum())
    gray = a.mean(axis=2)
    mid = (gray > 60) & (gray < 200)
    B = 10  # 10x10px @150dpi = 1.7mm square entirely mid-tone -> a gray fill (dense kanji never fills this)
    h6, w6 = (pix.height // B) * B, (pix.width // B) * B
    blocks = mid[:h6, :w6].reshape(h6 // B, B, w6 // B, B).all(axis=(1, 3))
    gray_blocks = int(blocks.sum())
    ink_ratio = float((gray < 128).mean())
    if color_px:
        v.append(f"カラー画素 {color_px}個")
    if gray_blocks:
        v.append(f"グレー塗りの疑い（1.7mm角が全面中間調）{gray_blocks}個")
    res["checks"] = {
        "one_page": doc.page_count == 1, "text_black_only": all(c == 0 for c in text_colors),
        "vector_bw_only": bad_draw == 0, "min_font_pt": round(min_size, 2), "min_font_ok": not small_fonts,
        "line_width_ok": not thin, "no_raster_images": images == 0, "raster_images": images, "color_pixels": color_px,
        "gray_fill_blocks": gray_blocks, "ink_coverage": round(ink_ratio, 4),
        "emblem_vector_paths": emblem["paths"], "emblem_min_line_pt": emblem["min_width_pt"],
        "emblem_ok": emblem["paths"] > 0 and emblem["thin"] == 0 and emblem["non_bw"] == 0,
    }
    res["passed"] = not v
    doc.close()
    return res


def _emblem_rect(page):
    """印刷版ヘッダーの線画エンブレム（svg.emblem）の領域: 左上の余白内側から 20mm 角を目安に探す."""
    mm = 72 / 25.4
    r = page.rect
    return pymupdf.Rect(r.x0 + 10 * mm, r.y0 + 10 * mm, r.x0 + 34 * mm, r.y0 + 34 * mm)


A4_PT = (595.276, 841.89)  # 210mm x 297mm
DIGITAL_PAGES = 2          # AMENDMENT_09 §D: 1ページ目＝プロフィール、2ページ目＝散文詩
A4_TOL_PT = 1.5            # +-0.5mm
ASPECT_TOL = 0.01          # PNG のアスペクト比誤差 < 1%


def p2_pii_hits(text: str, job: dict | None) -> list[str]:
    """AMENDMENT_P2PII: 2ページ目（SNS シェア前提）のテキストに含まれる個人情報の種別（値は返さない＝qa.json に残さない）.
    氏名・ふりがな（psych.name_terms と同じ規則）、メールアドレス、生年月日（各表記）、出生時刻、出生地。照合は空白を除いて行う."""
    if not job:
        return []
    t = psych._norm(text)
    hits = set(psych.name_hits(text, job))
    email = str(job.get("email") or "").strip().lower()
    if email and email in t.lower():
        hits.add("メールアドレス")

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", str(job.get("birth_date") or "").strip())
    if m:
        y, mo, d = m.groups()
        mi, di = int(mo), int(d)
        forms = {f"{y}-{mo}-{d}", f"{y}/{mo}/{d}", f"{y}/{mi}/{di}", f"{y}.{mo}.{d}", f"{y}年{mo}月{d}日", f"{y}年{mi}月{di}日", f"{y}{mo}{d}"}
        if any(f in t for f in forms) or re.search(rf"(?<!\d)0?{mi}月0?{di}日(?:生|に生|のお?誕生)", t):
            hits.add("生年月日")
    mt = re.match(r"^(\d{1,2}):(\d{2})$", str(job.get("birth_time") or "").strip())
    if mt and re.search(rf"(?<!\d)0?{int(mt.group(1))}(?::{mt.group(2)}|時0?{int(mt.group(2))}分)(?!\d)", t):
        hits.add("出生時刻")
    place = psych._norm(job.get("birth_place") or "")
    if place and place in t:
        hits.add("出生地")
    return sorted(hits)


def check_digital_pdf(pdf: Path, poem_title: str | None = None, expect_pages: int = DIGITAL_PAGES, job: dict | None = None) -> dict:
    """デジタル版PDF: 各ページA4判・ちょうど2ページ（AMENDMENT_09）。2ページ目に詩のタイトル。文字サイズの最小値も記録する.
    job を渡すと、2ページ目（SNS シェア前提）に本人の個人情報が出ていないことも検査する（AMENDMENT_P2PII）。"""
    res = {"file": pdf.name, "violations": []}
    if not pdf.exists():
        res["violations"].append("デジタル版PDFがありません")
        res["pages"] = 0
        res["passed"] = False
        return res
    doc = pymupdf.open(str(pdf))
    try:
        res["pages"] = doc.page_count
        sizes = [(round(pg.rect.width, 2), round(pg.rect.height, 2)) for pg in doc]
        res["page_size_pt"] = list(sizes[0]) if sizes else None
        res["page_size_mm"] = [round(sizes[0][0] / 72 * 25.4, 1), round(sizes[0][1] / 72 * 25.4, 1)] if sizes else None
        a4 = bool(sizes) and all(abs(w - A4_PT[0]) <= A4_TOL_PT and abs(h - A4_PT[1]) <= A4_TOL_PT for w, h in sizes)
        min_size = 99.0
        for pg in doc:
            for block in pg.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip():
                            min_size = min(min_size, span["size"])
        res["min_font_pt"] = round(min_size, 2)
        # 背景アートの上でもテキスト抽出が壊れていないこと（各ページの抽出文字数）
        texts = [pg.get_text("text") for pg in doc]
        res["text_chars_per_page"] = [len("".join(t.split())) for t in texts]
        if poem_title is not None:
            norm = lambda x: "".join((x or "").split())
            res["poem_on_page2"] = len(texts) >= 2 and bool(norm(poem_title)) and norm(poem_title) in norm(texts[1])
        if job is not None and len(texts) >= 2:
            # digital_p2.png はこの PDF の2ページ目をそのままラスタライズしたもの（pdf_to_pngs）なので、PDF の2ページ目のテキストで両方を担保する
            res["p2_pii_hits"] = p2_pii_hits(texts[1], job)
            res["p2_name_checked"] = bool(psych.name_terms(job))
    finally:
        doc.close()
    res["page_count_ok"] = res["pages"] == expect_pages
    res["one_page"] = res["page_count_ok"]  # 後方互換のキー（意味は「規定ページ数」）
    res["a4"] = a4
    if not res["page_count_ok"]:
        res["violations"].append(f"デジタル版PDFのページ数が {res['pages']}（A4 {expect_pages}ページ必須）")
    if any(n < 40 for n in res["text_chars_per_page"]):
        res["violations"].append(f"テキスト抽出できる文字が少ないページがある: {res['text_chars_per_page']}")
    if poem_title is not None and not res.get("poem_on_page2"):
        res["violations"].append("2ページ目に詩のタイトルが見つからない（2ページ目＝詩ページ）")
    if res.get("p2_pii_hits"):
        res["violations"].append(f"2ページ目（SNS シェア用）に個人情報が含まれている: {'・'.join(res['p2_pii_hits'])}")
    if not a4:
        res["violations"].append(f"デジタル版PDFのページサイズが A4 ではない: {res['page_size_mm']}mm")
    min_font = settings()["render"].get("digital_min_font_pt", 6.0)
    if res["min_font_pt"] < min_font - 0.05:
        res["violations"].append(f"デジタル版の最小文字 {res['min_font_pt']}pt（下限 {min_font}pt）")
    res["passed"] = not res["violations"]
    return res


def check_digital(pdf: Path, pngs: list[Path], poem_title: str | None = None, job: dict | None = None) -> dict:
    """デジタル版: PDF＝A4・2ページ（2ページ目＝詩）、PNG＝ページごとの2ファイル（AMENDMENT_17）。
    各 PNG は A4 単ページの縦横比（理論値 A4高さ/A4幅 に対する誤差 < 1%）かつ幅 ≥ settings.render.png_width_px。"""
    res = check_digital_pdf(pdf, poem_title, job=job)
    res.pop("file", None)
    res["pdf_pages"] = res.get("pages")
    target = A4_PT[1] / A4_PT[0]  # A4 単ページの理論値
    min_w = int(settings()["render"].get("png_width_px", 2480))
    res["png_aspect_target"] = round(target, 4)
    res["png_min_width_px"] = min_w
    pngs = list(pngs)
    if len(pngs) != DIGITAL_PAGES:
        res["violations"].append(f"デジタル版PNGの数が {len(pngs)}（ページごとに {DIGITAL_PAGES} ファイル必須）")
    per, sizes, errs, ok = [], [], [], len(pngs) == DIGITAL_PAGES
    for i, png in enumerate(pngs, 1):
        if not png.exists():
            res["violations"].append(f"デジタル版PNG（{i}ページ目: {png.name}）がありません")
            per.append({"file": png.name, "exists": False})
            ok = False
            continue
        pm = pymupdf.Pixmap(str(png))
        actual = pm.height / pm.width
        err = abs(actual - target) / target
        a_ok = err < ASPECT_TOL
        w_ok = pm.width >= min_w
        per.append({"file": png.name, "size": [pm.width, pm.height], "dpi": pm.xres, "aspect": round(actual, 4),
                    "aspect_error_pct": round(100 * err, 3), "aspect_ok": a_ok, "width_ok": w_ok})
        sizes.append([pm.width, pm.height])
        errs.append(round(100 * err, 3))
        res.setdefault("png_dpi", pm.xres)
        if not a_ok:
            res["violations"].append(f"PNG（{i}ページ目: {png.name}）のアスペクト比 {actual:.3f}（A4単ページ {target:.3f} に対して誤差 {100 * err:.2f}% ≥ 1%）")
        if not w_ok:
            res["violations"].append(f"PNG（{i}ページ目: {png.name}）の幅 {pm.width}px（設定値 {min_w}px 未満）")
        ok = ok and a_ok and w_ok
    res["pngs"] = per
    res["png_size"] = sizes                                   # ページごとの [幅, 高さ]
    res["png_aspect_error_pct"] = max(errs) if errs else None  # 最大誤差
    res["png_aspect_ok"] = bool(per) and all(x.get("aspect_ok") for x in per)
    res["png_ok"] = ok
    res["passed"] = not res["violations"]
    return res
