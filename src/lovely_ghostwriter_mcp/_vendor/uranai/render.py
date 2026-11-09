"""HTML テンプレート → PDF / PNG（Microsoft Edge を Playwright 経由で使用）."""
from __future__ import annotations

import base64
import html
import re
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

import segno
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import catalog, config, facts, policy, psych
from .reading import stars

TEMPLATES = Path(__file__).resolve().parent / "templates"
DESIGN = Path(__file__).resolve().parent.parent / "assets" / "design"


@lru_cache(maxsize=1)
def design_assets() -> dict:
    """デジタル版の共通素材（AMENDMENT_10/11）を data URI で返す（ジョブごとの生成はしない）."""
    def uri(name: str, mime: str) -> str:
        return f"data:{mime};base64," + base64.b64encode((DESIGN / name).read_bytes()).decode("ascii")
    return {"page1_bg": uri("page1-bg.jpg", "image/jpeg"), "poem_bg": uri("poem-bg.jpg", "image/jpeg"),
            "ornament": uri("ornament.png", "image/png"), "emblem": uri("beast-emblem.png", "image/png")}


@lru_cache(maxsize=4)
def emblem_line_svg(size_mm: float = 16.0) -> Markup:
    """印刷版の念獣線画エンブレム（beast-line.svg）。ベクターのままインラインで埋め込む（ラスター画像にしない）.
    ルート <svg> の width/height を差し替えて size_mm 角にする（viewBox が無ければ元の width/height から補う）."""
    svg = (DESIGN / "beast-line.svg").read_text(encoding="utf-8")
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg).strip()
    m = re.search(r"<svg\b[^>]*>", svg)
    tag = m.group(0)
    new = tag
    if "viewBox" not in tag:
        w = re.search(r'\swidth="([\d.]+)', tag)
        h = re.search(r'\sheight="([\d.]+)', tag)
        if w and h:
            new = new.replace("<svg", f'<svg viewBox="0 0 {w.group(1)} {h.group(1)}"', 1)
    new = re.sub(r'\s(width|height|class)="[^"]*"', "", new)
    new = new.replace("<svg", f'<svg width="{size_mm}mm" height="{size_mm}mm" class="emblem"', 1)
    return Markup(svg[:m.start()] + new + svg[m.end():])
ENV = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html", "j2"]))
ELEMENTS = ["木", "火", "土", "金", "水"]
# 非公式ファン作品（パロディ）の注意書き（証明書フッター・メール共通）
FAN_NOTICE = "本プロジェクトは HUNTER×HUNTER の非公式ファン作品（パロディ）です。原作・公式とは関係ありません。"
DIGITAL_EL_COLORS = {"木": "#3E8E5E", "火": "#C8473D", "土": "#C89B3C", "金": "#8C8C9E", "水": "#2F5D9A"}


def qr_svg(url: str, size_px: int, dark: str = "#000000") -> Markup:
    q = segno.make(url, error="m")
    n = q.symbol_size(border=2)[0]
    scale = max(1, size_px // n)
    svg = q.svg_inline(scale=scale, border=2, dark=dark, light="#ffffff")
    return Markup(svg)


def elements_svg_print(counts: dict, width: int = 150) -> Markup:
    """白黒の五行バー: 長さ＝数、模様で五行を区別（色を使わない）。線はすべて明示的な path."""
    row_h, bar_h, label_w, num_w = 17, 12, 22, 20
    maxc = max(4, max(counts.values()) if counts else 1)
    bw = width - label_w - num_w
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{row_h * 5 + 2}" viewBox="0 0 {width} {row_h * 5 + 2}">']
    for i, el in enumerate(ELEMENTS):
        y = i * row_h + 2
        c = counts.get(el, 0)
        w = round(bw * c / maxc, 1)
        x0 = label_w
        parts.append(f'<text x="0" y="{y + bar_h - 1}" font-size="13" font-weight="700" fill="#000">{el}</text>')
        parts.append(f'<rect x="{x0}" y="{y}" width="{bw}" height="{bar_h}" fill="none" stroke="#000" stroke-width="1.2" stroke-dasharray="2 3"/>')
        if w > 0:
            if el == "木":
                parts.append(f'<rect x="{x0}" y="{y}" width="{w}" height="{bar_h}" fill="#000"/>')
            else:
                parts.append(f'<rect x="{x0}" y="{y}" width="{w}" height="{bar_h}" fill="#fff" stroke="#000" stroke-width="1.6"/>')
                lines = []
                if el == "火":  # vertical stripes
                    xx = x0 + 3
                    while xx < x0 + w - 1:
                        lines.append(f"M{xx:.1f} {y}V{y + bar_h}")
                        xx += 3.5
                elif el == "土":  # horizontal stripes
                    for yy in (y + 3, y + 6, y + 9):
                        lines.append(f"M{x0} {yy}H{x0 + w}")
                elif el == "金":  # diagonal hatch
                    xx = x0 - bar_h
                    while xx < x0 + w:
                        a, b = max(xx, x0), min(xx + bar_h, x0 + w)
                        if b > a:
                            lines.append(f"M{a:.1f} {y + bar_h - (a - xx):.1f}L{b:.1f} {y + bar_h - (b - xx):.1f}")
                        xx += 4.5
                # 水: outline only (白抜き)
                if lines:
                    parts.append(f'<path d="{" ".join(lines)}" stroke="#000" stroke-width="1.2" fill="none"/>')
        parts.append(f'<text x="{width - num_w + 4}" y="{y + bar_h - 1}" font-size="13" font-weight="700" fill="#000">{c}</text>')
    parts.append("</svg>")
    return Markup("".join(parts))


def elements_bars_digital(counts: dict) -> list[dict]:
    maxc = max(4, max(counts.values()) if counts else 1)
    return [{"el": el, "n": counts.get(el, 0), "pct": round(100 * counts.get(el, 0) / maxc), "color": DIGITAL_EL_COLORS[el]}
            for el in ELEMENTS]


def context(job: dict, calc: dict, reading: dict, texts: dict | None = None, pt: dict | None = None,
            show_emblem: bool = True) -> dict:
    """texts: fitted text set for the skin (fit.texts_for_level). Templates read prose only from `t`."""
    if texts is None:
        from . import fit
        texts = fit.texts_for_level(reading, 0, "print")
    soc = config.social()
    fx = facts.build(calc)
    for f in fx:
        if f.get("elements"):
            f["elements_svg"] = elements_svg_print(f["elements"])
            f["elements_bars"] = elements_bars_digital(f["elements"])
    roles = {r["system"]: r["role"] for r in reading["blend_roles"]}
    sysread = {r["system"]: r for r in reading["system_readings"]}
    themes = [{"key": k, "label": lab, **reading["themes"][k], "stars": stars(reading["themes"][k]["score"])}
              for k, lab in catalog.THEMES]
    # ケルティッククロス（AMENDMENT_09 §C）: calc の10枚に、鑑定文の位置ごとの一言を添える
    cross, cross_target = [], ""
    if "tarot" in calc["results"]:
        tr = calc["results"]["tarot"]
        notes = {c["position"]: c["note"] for c in reading.get("tarot_cross") or []}
        cross = [{**c, "note": notes.get(c["position"], "")} for c in tr["spread"]]
        cross_target = (tr.get("target") or {}).get("label") or tr.get("question") or "全体運"
        if len(cross_target) > 60:
            cross_target = cross_target[:59] + "…"
    poem = reading.get("poem") or {"title": "", "body": ""}
    stanzas = psych.poem_stanzas(poem)  # 予言詩（BRIEF §4）: 連（行のリスト）のリスト。旧形式 body も読める
    paras = ["".join(lines) for lines in stanzas]
    if pt is None:
        from . import fit
        pt = fit.poem_texts(0)
    return {
        "brand": config.brand(), "job": job, "calc": calc, "r": reading, "facts": fx, "roles": roles, "sysread": sysread,
        "themes": themes, "policy": policy.texts(), "t": texts, "frame_note": psych.FRAME_NOTE,
        "social": soc, "fan_notice": FAN_NOTICE,
        "birth_label": _birth_label(job),
        "blend_label": " × ".join(catalog.CATALOG[s]["name"] for s in calc["systems"]),
        "cross": cross, "cross_target": cross_target, "cross_note": "シードによる再現可能な抽選・正逆あり",
        "poem": poem, "poem_paras": paras, "poem_stanzas": stanzas,"poem_theme": f"― {(calc.get('poem') or {}).get('theme', '')} ―",
        "pt": pt,
        "design": design_assets(), "emblem_line": emblem_line_svg(16.0), "show_emblem": show_emblem,
    }


def _birth_label(job: dict) -> str:
    if not job.get("birth_date"):
        return "生年月日：未入力（タロット等）"
    y, m, d = job["birth_date"].split("-")
    s = f"{int(y)}年{int(m)}月{int(d)}日生"
    if job.get("birth_time"):
        s += f" {job['birth_time']}"
    return s


def render_html(template: str, ctx: dict) -> str:
    return ENV.get_template(template).render(**ctx)


@contextmanager
def browser():
    from playwright.sync_api import sync_playwright
    cfg = config.settings()["render"]
    # AMENDMENT_13（並行ジョブ）: launch() は起動ごとに新しい一時プロファイル（mkdtemp）を作り終了時に消す。
    # 永続プロファイル（launch_persistent_context / user_data_dir）は使わないこと＝ジョブ間でプロファイルが衝突しない。
    # 各ジョブは別プロセス（workerpool）で走るので Playwright インスタンスも共有しない。
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel=cfg.get("browser_channel", "msedge"))
        except Exception:
            b = p.chromium.launch(channel=cfg.get("fallback_channel", "chrome"))
        try:
            yield b
        finally:
            b.close()


def html_to_pdf(b, html_text: str, out: Path | None) -> list[float]:
    """HTML → PDF。戻り値は各 .sheet（固定高さのページ）のはみ出し量 px（デジタル版の fit 判定用。印刷版は空リスト）.
    out=None なら計測だけ行う。"""
    page = b.new_page()
    page.emulate_media(media="print")
    page.set_content(html_text, wait_until="load")
    page.evaluate("document.fonts.ready")
    over = page.evaluate("""() => Array.from(document.querySelectorAll('.sheet')).map(s => {
        const b = s.querySelector('.pbody');
        const a = Math.max(0, s.scrollHeight - s.clientHeight);
        return b ? Math.max(a, b.scrollHeight - b.clientHeight) : a; })""")
    if out is not None:
        page.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True,
                 margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    page.close()
    return over


DIGITAL_PNGS = ("digital_p1.png", "digital_p2.png")  # AMENDMENT_17: 1ページ目＝プロフィール面／2ページ目＝詩ページ


def pdf_to_pngs(pdf: Path, outs: list[Path], width_px: int | None = None) -> list[tuple[int, int]]:
    """デジタル版PNG = デジタル版PDFの各ページを1ページ1ファイルでラスタライズ（AMENDMENT_17: 連結版は廃止）.
    outs[i] に i+1 ページ目を書く（digital_p1.png＝プロフィール面／digital_p2.png＝詩ページ）。
    幅は settings.render.png_width_px（3307px ≒ 400dpi）、高さは A4 単ページの縦横比。"""
    import pymupdf
    width_px = width_px or int(config.settings()["render"].get("png_width_px", 2480))
    doc = pymupdf.open(str(pdf))
    try:
        # ページ数が outs と合わない場合も落とさず、書ける分だけ書く（判定は qa.check_digital がページ数・PNG欠落で行う）
        sizes = []
        for page, out in zip(doc, outs):
            r = page.rect
            height_px = round(width_px * r.height / r.width)
            # 目標ピクセル数に合わせた倍率（端数の丸めで1px増えないよう、わずかに内側へ）
            m = pymupdf.Matrix((width_px - 0.01) / r.width, (height_px - 0.01) / r.height)
            pix = page.get_pixmap(matrix=m, alpha=False, colorspace=pymupdf.csRGB)
            dpi = round(72 * width_px / r.width)
            pix.set_dpi(dpi, dpi)
            pix.save(str(out))
            sizes.append((pix.width, pix.height))
        return sizes
    finally:
        doc.close()


def esc(s: str) -> str:
    return html.escape(s)
