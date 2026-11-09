"""MCP ツールの本体（トランスポート非依存）.

アプリ本体から同期した部品（_vendor/uranai）をそのまま呼び、足りないところだけ薄いアダプタを書く:
- 入力（person）→ 正規化済みジョブ: intake.normalize を流用（メール・同意は MCP では不要なので内部の仮値で埋める）
- 計算: calc_cli.compute（決定論。外部 API なし）
- 鑑定文・予言詩のプロンプト: reading.SYSTEM_PROMPT / reading.build_prompt と schemas/reading.schema.json
- 検査: reading._check_consistency / psych.check_style / psych.check_poem_* / psych.check_grounding
- 描画: render.context / render_html / html_to_pdf / pdf_to_pngs と fit の段階調整、qa の検査
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jsonschema

from ._vendor.uranai import calc_cli, catalog, facts, intake, presets, psych, reading

VENDOR = Path(__file__).resolve().parent / "_vendor"
SCHEMA_PATH = VENDOR / "schemas" / "reading.schema.json"
JST = timezone(timedelta(hours=9))
DEFAULT_QUESTION = "これからの過ごし方"
_PLACEHOLDER_EMAIL = "mcp-local@example.invalid"  # intake の必須チェックを通すための内部値（出力には含めない）
PROFILE_FIELDS = ("worries", "self_desc", "about_me", "concern_theme", "occupation", "period", "partner_status")
PERSONALITY_KEYS = ("decision", "money", "stress", "love", "holiday", "new_env")
PRIVATE_JOB_KEYS = ("email", "consent", "response_id", "test_mode", "source", "received_at")


class InputError(ValueError):
    """入力不備（ツールの呼び出し側で直せるもの）."""


# ---------------------------------------------------------------- catalog

def list_systems() -> dict:
    systems = []
    for e in catalog.public_catalog():
        systems.append({k: e[k] for k in ("id", "name", "tier", "tier_label", "region", "era", "role", "description",
                                          "required_inputs", "optional_inputs", "needs_time", "needs_place", "note")})
    return {
        "systems": systems,
        "selectable": list(catalog.SELECTABLE),
        "presets": [{"id": k, **v} for k, v in presets.PRESETS.items()],
        "max_systems": catalog.MAX_SYSTEMS,
        "themes": [{"key": k, "label": v} for k, v in catalog.THEMES] + [{"key": "answer", "label": "占ってほしいこと（1件）"}],
        "input_labels": dict(catalog.INPUT_LABELS),
        "notes": ["tier 1/2 だけが選択可能。tier 3 は準備中、tier 0 は対象外（参考掲載）。",
                  "ブレンドは 1〜3 種（カクテル式・土台固定なし）。preset か systems のどちらかで指定する。",
                  "計算はすべて決定論（同じ入力・同じ as_of なら同じ結果）。値の捏造はしない。"],
    }


# ---------------------------------------------------------------- person -> job

def _clean(v) -> str:
    return "" if v is None else str(v).strip()


def build_job(person: dict) -> dict:
    """MCP の入力（person）→ アプリと同じ正規化済みジョブ。決定論（同じ入力なら同じ job_id・タロットのシード）."""
    p = {k: v for k, v in (person or {}).items() if v not in (None, "", [], {}) and not str(k).startswith("_")}
    as_of = _clean(p.get("as_of")) or datetime.now(JST).strftime("%Y-%m-%d")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", as_of):
        raise InputError(f"as_of は YYYY-MM-DD で指定してください: {as_of}")
    systems = p.get("systems") or None
    preset = _clean(p.get("preset")) or None
    if isinstance(systems, str):
        systems = [s.strip() for s in re.split(r"[,、×x\s]+", systems) if s.strip()]
    try:
        chosen, _ = presets.resolve(preset, systems)
    except KeyError as e:
        raise InputError(f"未知のハウスブレンド: {e}（list_systems の presets を参照）") from e
    except ValueError as e:
        raise InputError(str(e)) from e
    unknown = [s for s in chosen if s not in catalog.CATALOG]
    if unknown:
        raise InputError(f"未知の占術ID: {', '.join(unknown)}（list_systems を参照）")

    needs_kana = any("name_kana" in catalog.CATALOG[s]["required_inputs"] for s in chosen)
    name_kana = _clean(p.get("name_kana"))
    if not name_kana and not needs_kana:
        name_kana = "-"  # 名前系の占術を選んでいないときは不要（アプリのフォームでは全員必須だが MCP では省略可）
    display_name = _clean(p.get("display_name")) or "ゲスト"
    name_kanji = _clean(p.get("name_kanji"))
    sur, giv = (intake.split_kanji_name(name_kanji) if name_kanji else ("", ""))
    profile = {k: _clean(p[k]) for k in PROFILE_FIELDS if _clean(p.get(k))}
    for k, v in (p.get("personality") or {}).items():
        if _clean(v):
            profile[k] = _clean(v)
    question = _clean(p.get("question"))
    canon = json.dumps({k: p[k] for k in sorted(p) if k != "as_of"}, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256(f"{canon}|{as_of}".encode("utf-8")).hexdigest()[:8]
    job_id = f"{as_of.replace('-', '')}-120000-{h}"
    raw = {
        "job_id": job_id, "received_at": f"{as_of}T12:00:00+09:00", "as_of": as_of, "source": "cli",
        "display_name": display_name, "name_kana": name_kana, "surname_kanji": sur, "given_kanji": giv,
        "email": _PLACEHOLDER_EMAIL, "consent": True,
        "question": question or DEFAULT_QUESTION,
        "birth_date": p.get("birth_date"), "birth_time": p.get("birth_time"), "birth_place": _clean(p.get("birth_place")),
        "birth_time_precision": p.get("birth_time_precision"), "gender": p.get("gender"),
        "daiun_basis": p.get("daiun_basis"), "profile": profile, "tarot_seed": _clean(p.get("tarot_seed")) or None,
        "systems": chosen, "preset": None,
    }
    try:
        job = intake.normalize(raw, strict=True)
    except intake.IntakeError as e:
        raise InputError("入力不備: " + " / ".join(e.errors)) from e
    if not question:
        job["intake_notes"] = list(job.get("intake_notes") or []) + [f"占ってほしいことが未入力のため「{DEFAULT_QUESTION}」として鑑定"]
    if name_kana == "-":
        job["name_kana"] = ""
    return job


def public_job(job: dict) -> dict:
    return {k: v for k, v in job.items() if k not in PRIVATE_JOB_KEYS}


# ---------------------------------------------------------------- calculate

def compute(job: dict) -> dict:
    return json.loads(calc_cli.dumps(calc_cli.compute(job, job["as_of"])))


def calculate(person: dict) -> dict:
    job = build_job(person)
    calc = compute(job)
    return {"job": public_job(job), "calc": calc, "facts": facts.build(calc),
            "calc_sha256": calc_cli.sha256_text(calc_cli.dumps(calc)),
            "note": "決定論計算（外部 API なし）。鑑定文ではこの calc に書かれた値だけを使うこと。"}


# ---------------------------------------------------------------- schemas / prompts

def reading_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def poem_schema() -> dict:
    s = reading_schema()
    out = copy.deepcopy(s["properties"]["poem"])
    out["$schema"] = s.get("$schema", "http://json-schema.org/draft-07/schema#")
    if s.get("definitions"):
        out["definitions"] = s["definitions"]
    return out


def _payload_json(job: dict, calc: dict) -> str:
    """reading.build_prompt の JSON 部分（入力ペイロード）だけを取り出す."""
    text = reading.build_prompt(job, calc, None)
    m = re.search(r"```json\n(.*)\n```", text, re.S)
    return m.group(1) if m else text


def reading_prompt(job: dict, calc: dict) -> dict:
    return {"system": reading.SYSTEM_PROMPT, "user": reading.build_prompt(job, calc, None), "schema": reading_schema()}


def _poem_section(system_prompt: str) -> str:
    """アプリの鑑定プロンプトから、詩（p2）の節だけを抜き出す（アプリ側の改訂に自動で追従するため）."""
    parts = re.split(r"(?m)^(?=# )", system_prompt)
    sec = [s for s in parts if s.startswith("# ") and "詩" in s.splitlines()[0]]
    return "\n".join(s.strip() for s in sec)


POEM_HEADER = """あなたは「天使の自動筆記（ラブリーゴーストライター）」の自動筆記者です。鑑定書の2ページ目に載る予言詩だけを書きます。
入力として、検証済みの計算結果（calc）と本人の入力（person・profile）、詩のテーマ（poem_theme）が渡されます。
- 計算値は calc に書かれたものだけを象徴として使う。自分で計算・推測・補完しない。
- 本人の言葉は逐語で引用せず、モチーフ・象徴に置き換えて織り込む。名前・個人情報は書かない。
- 助言・命令・教訓・励ましは書かない（それは1ページ目の役割）。断定的な災厄の宣告はせず、不吉さは象徴に留める。
- 出力は指定の JSON スキーマどおりの JSON だけ。
"""


def poem_prompt(job: dict, calc: dict) -> dict:
    """予言詩だけを書かせるプロンプト。アプリの reading.build_poem_prompt があればそれを使う（無い旧版は節を抜き出す）."""
    builder = getattr(reading, "build_poem_prompt", None)
    system = user = None
    if callable(builder):
        out = builder(job, calc)
        if isinstance(out, tuple):
            system, user = out
        else:
            user = out
    if not system:
        system = getattr(reading, "POEM_SYSTEM_PROMPT", None) or (POEM_HEADER + "\n" + _poem_section(reading.SYSTEM_PROMPT_BASE))
    if not user:
        user = ("以下の入力から、2ページ目の予言詩（poem）だけを、スキーマどおりの JSON で作成してください。\n\n```json\n"
                + _payload_json(job, calc) + "\n```")
    return {"system": system, "user": user, "schema": poem_schema()}


# ---------------------------------------------------------------- validation

def _issues(res) -> list[str]:
    if not res:
        return []
    if isinstance(res, str):
        return [res]
    if isinstance(res, dict):
        if res.get("ok") is False or res.get("passed") is False:
            return [str(x) for x in (res.get("errors") or res.get("violations") or ["検査不合格"])]
        return [str(x) for x in (res.get("errors") or [])]
    return [str(x) for x in res]


def check_poem(poem: dict, job: dict, calc: dict | None = None) -> dict:
    """予言詩の機械検査（アプリの psych の検査器をそのまま使う）.
    errors = hard（助言・教訓・励まし調、断定的な災厄の宣告など。残れば描画しない）
    warnings = soft（モチーフの数・逐語引用・字数・連の形。理由を記録して採用してよい）"""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        jsonschema.validate(poem, poem_schema())
    except jsonschema.ValidationError as e:
        errors.append(f"スキーマ不一致: {e.message}（{'/'.join(map(str, e.absolute_path))}）")
    agg = getattr(psych, "check_poem", None)
    if callable(agg):  # アプリ側の「検査一式」入口
        try:
            res = agg(poem, job, calc)
            errors += [str(x) for x in res.get("hard", [])]
            warnings += [str(x) for x in res.get("soft", [])]
        except Exception as e:
            errors.append(f"check_poem: 検査できませんでした（{type(e).__name__}: {str(e)[:120]}）")
    else:  # 旧版のアプリ: 個別の検査関数を全部かける
        for name in sorted(dir(psych)):
            fn = getattr(psych, name)
            if not (callable(fn) and name.startswith("check_poem")):
                continue
            try:
                errors += _issues(fn(poem, job))
            except Exception as e:
                errors.append(f"{name}: 検査できませんでした（{type(e).__name__}）")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_reading(rd: dict, job: dict, calc: dict | None = None) -> dict:
    """鑑定データ（reading JSON）の検査: スキーマ・占術の整合・スタイル（心理学レンズ）・詩の検査.
    errors は描画を止めるもの、warnings（接地・詩のモチーフ等の soft 検査）は理由を記録して採用してよいもの."""
    r = copy.deepcopy({k: v for k, v in rd.items() if not k.startswith("_")})
    errors: list[str] = []
    warnings: list[str] = []
    try:
        jsonschema.validate(r, reading_schema())
    except jsonschema.ValidationError as e:
        errors.append(f"スキーマ不一致: {e.message}（{'/'.join(map(str, e.absolute_path))}）")
        return {"ok": False, "errors": errors, "warnings": warnings, "reading": r}
    try:
        reading._check_consistency(r, job)
    except (ValueError, KeyError) as e:
        errors.append(str(e))
    try:
        errors += psych.check_style(r)
    except Exception as e:
        errors.append(f"check_style: {type(e).__name__}: {str(e)[:200]}")
    pc = check_poem(r.get("poem") or {}, job, calc)
    errors += pc["errors"]
    warnings += pc["warnings"]
    try:
        g = psych.check_grounding(r, job)
        warnings += [str(x) for x in g.get("errors", []) if str(x) not in warnings]
    except Exception:
        pass
    return {"ok": not errors, "errors": errors, "warnings": warnings, "reading": r}


# ---------------------------------------------------------------- generation (two modes)

def api_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def compose_reading(person: dict, mode: str = "auto") -> dict:
    job = build_job(person)
    calc = compute(job)
    pr = reading_prompt(job, calc)
    use_api = mode == "api" or (mode == "auto" and api_available())
    if mode == "api" and not api_available():
        raise InputError("mode=api には ANTHROPIC_API_KEY と anthropic パッケージ（pip install -e .[anthropic]）が必要です")
    if not use_api:
        return {
            "mode": "prompt",
            "instructions": ("ANTHROPIC_API_KEY が無いため、ホスト LLM 用のプロンプトを返します。system と user に従い、schema どおりの "
                             "JSON（鑑定データ）を作成してください。値は calc にあるものだけを使い、捏造しないこと。作成した JSON は "
                             "validate_reading で検査し、render_certificate に person と一緒に渡すと証明書（PDF/PNG）になります。"),
            "system_prompt": pr["system"], "user_prompt": pr["user"], "output_schema": pr["schema"],
            "job": public_job(job), "calc": calc,
        }
    from . import llm
    prompt, last = pr["user"], None
    for attempt in (1, 2):
        out, meta = llm.generate_json(pr["system"], prompt, pr["schema"])
        v = validate_reading(out, job, calc)
        last = (v, meta)
        if v["ok"]:
            v["reading"]["_meta"] = {**meta, "attempts": attempt, "soft_warnings": v["warnings"]}
            return {"mode": "api", "ok": True, "reading": v["reading"], "warnings": v["warnings"],
                    "job": public_job(job), "calc": calc}
        prompt = (pr["user"] + "\n\n# 前回の出力は検証で不合格でした。次の点を直して、全体を出し直してください\n"
                  + "\n".join(f"- {x}" for x in v["errors"]))
    v, meta = last
    return {"mode": "api", "ok": False, "errors": v["errors"], "warnings": v["warnings"], "reading": v["reading"],
            "meta": meta, "job": public_job(job), "calc": calc}


def prophecy_poem(person: dict, mode: str = "auto") -> dict:
    job = build_job(person)
    calc = compute(job)
    pp = poem_prompt(job, calc)
    use_api = mode == "api" or (mode == "auto" and api_available())
    if mode == "api" and not api_available():
        raise InputError("mode=api には ANTHROPIC_API_KEY と anthropic パッケージが必要です")
    theme = (calc.get("poem") or {}).get("theme")
    if not use_api:
        return {"mode": "prompt",
                "instructions": ("ANTHROPIC_API_KEY が無いため、ホスト LLM 用のプロンプトを返します。system と user に従い、"
                                 "schema どおりの JSON（予言詩）を作成してください。助言・命令・教訓・励ましは書かないこと。"
                                 "鑑定データ（compose_reading）の poem 欄にそのまま入れられます。"),
                "poem_theme": theme, "system_prompt": pp["system"], "user_prompt": pp["user"],
                "output_schema": pp["schema"], "job": public_job(job), "calc": calc}
    from . import llm
    prompt, res = pp["user"], None
    for attempt in (1, 2):
        poem, meta = llm.generate_json(pp["system"], prompt, pp["schema"], max_tokens=16000)
        chk = check_poem(poem, job, calc)
        res = {"mode": "api", "ok": chk["ok"], "poem": poem, "errors": chk["errors"], "warnings": chk["warnings"],
               "poem_theme": theme, "meta": {**meta, "attempts": attempt}}
        # hard（errors）だけ1回出し直し、残れば ok=False。soft（warnings）は理由つきで採用（アプリと同じ方針）
        if chk["ok"]:
            return res
        prompt = (pp["user"] + "\n\n# 前回の詩は検査で不合格でした。次の点を直して書き直してください\n"
                  + "\n".join(f"- {x}" for x in chk["errors"] + chk["warnings"]))
    return res


# ---------------------------------------------------------------- render

class RenderUnavailable(RuntimeError):
    pass


@contextmanager
def browser():
    """Chromium 系ブラウザ（既定は Microsoft Edge → Google Chrome → Playwright 同梱 Chromium の順に試す）."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RenderUnavailable("playwright が入っていません（pip install playwright）") from e
    from ._vendor.uranai import config
    cfg = config.settings().get("render", {})
    channels = [c for c in (os.environ.get("LGW_BROWSER_CHANNEL"), cfg.get("browser_channel", "msedge"),
                            cfg.get("fallback_channel", "chrome")) if c]
    channels = list(dict.fromkeys(channels)) + [None]
    with sync_playwright() as p:
        b, errs = None, []
        for ch in channels:
            try:
                b = p.chromium.launch(channel=ch) if ch else p.chromium.launch()
                break
            except Exception as e:
                errs.append(f"{ch or 'chromium'}: {str(e).splitlines()[0][:160]}")
        if b is None:
            raise RenderUnavailable("Chromium 系ブラウザを起動できません。Microsoft Edge か Google Chrome を入れるか、"
                                    "`python -m playwright install chromium` を実行してください。詳細: " + " | ".join(errs))
        try:
            yield b
        finally:
            b.close()


def _missing_assets() -> list[str]:
    need = ["page1-bg.jpg", "poem-bg.jpg", "beast-emblem.png", "beast-line.svg", "ornament.png"]
    return [n for n in need if not (VENDOR / "assets" / "design" / n).exists()]


def _ctx(render, job, calc, rd, texts, pt=None, **kw) -> dict:
    ctx = render.context(job, calc, rd, texts, pt, **kw) if pt is not None else render.context(job, calc, rd, texts, **kw)
    return ctx


def render_certificate(person: dict, rd: dict, out_dir: str | None = None, strict: bool = True) -> dict:
    job = build_job(person)
    calc = compute(job)
    v = validate_reading(rd, job, calc)
    if not v["ok"] and strict:
        return {"ok": False, "stage": "validate", "errors": v["errors"], "warnings": v["warnings"],
                "hint": "鑑定データを直すか、strict=false で検査エラーを無視して描画できます（スキーマ不一致は描画できません）"}
    if any(e.startswith("スキーマ不一致") for e in v["errors"]):
        return {"ok": False, "stage": "validate", "errors": v["errors"]}
    r = v["reading"]
    missing = _missing_assets()
    if missing:
        return {"ok": False, "stage": "assets", "errors": [f"デザイン素材がありません: {', '.join(missing)}（tools/sync_from_app.py を実行）"]}
    from ._vendor.uranai import fit, qa, render
    out = Path(out_dir or os.environ.get("LGW_OUTPUT_DIR") or (Path.cwd() / "lgw-output")).expanduser().resolve() / job["job_id"]
    out.mkdir(parents=True, exist_ok=True)
    print_pdf, digital_pdf = out / "print.pdf", out / "digital.pdf"
    pngs = [out / n for n in getattr(render, "DIGITAL_PNGS", ("digital_p1.png", "digital_p2.png"))]
    pq, attempts = None, []
    try:
        with browser() as b:
            for lvl in range(len(fit.PRINT_LEVELS)):
                texts = fit.texts_for_level(r, lvl, "print")
                render.html_to_pdf(b, render.render_html("print.html.j2", _ctx(render, job, calc, r, texts)), print_pdf)
                pq = qa.check_print_pdf(print_pdf)
                attempts.append({"level": lvl, "pages": pq["pages"]})
                if pq["pages"] == 1:
                    break
            lv1 = lv2 = 0
            over = [1.0, 1.0]
            for _ in range(len(fit.DIGITAL_LEVELS) + len(fit.POEM_LEVELS)):
                html_d = render.render_html("digital.html.j2", _ctx(render, job, calc, r, fit.texts_for_level(r, lv1, "digital"),
                                                                    fit.poem_texts(lv2)))
                over = render.html_to_pdf(b, html_d, None)
                o1, o2 = (list(over) + [0, 0])[:2]
                moved = False
                if o1 > 1 and lv1 < len(fit.DIGITAL_LEVELS) - 1:
                    lv1, moved = lv1 + 1, True
                if o2 > 1 and lv2 < len(fit.POEM_LEVELS) - 1:
                    lv2, moved = lv2 + 1, True
                if not moved:
                    break
            render.html_to_pdf(b, html_d, digital_pdf)
    except RenderUnavailable as e:
        return {"ok": False, "stage": "browser", "errors": [str(e)]}
    render.pdf_to_pngs(digital_pdf, pngs)
    poem_title = (r.get("poem") or {}).get("title")
    dq = qa.check_digital(digital_pdf, pngs, poem_title=poem_title)
    if any(x > 1 for x in over):
        dq["violations"].append(f"最終段でもページからはみ出しています（{[round(x) for x in over]}px）")
        dq["passed"] = False
    (out / "reading.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    passed = bool(pq and pq["passed"] and dq["passed"])
    return {
        "ok": True, "qa_passed": passed, "out_dir": str(out),
        "files": {"print_pdf": str(print_pdf), "digital_pdf": str(digital_pdf), "digital_pngs": [str(p) for p in pngs],
                  "reading_json": str(out / "reading.json")},
        "qa": {"print": {"pages": pq["pages"] if pq else None, "passed": bool(pq and pq["passed"]),
                         "violations": (pq or {}).get("violations", []), "fit_attempts": attempts},
               "digital": {"pages": dq.get("pdf_pages"), "passed": dq["passed"], "violations": dq["violations"],
                           "levels": {"profile": lv1, "poem": lv2}, "png_size": dq.get("png_size")}},
        "validation": {"errors": v["errors"], "warnings": v["warnings"]},
    }
