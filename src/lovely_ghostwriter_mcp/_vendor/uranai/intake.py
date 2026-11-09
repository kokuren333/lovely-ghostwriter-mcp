"""入力（問診）の正規化と検証。必須項目は選択された占術のカタログから決まる.

strict=True（CLI・現場ローカルフォーム）: 不足があればエラーで差し戻す（その場で直せるため）。
strict=False（Googleフォーム経由）: 必要な入力が無い占術はブレンドから外して notes に記録する。
  全部外れた場合はタロット単体に切り替える（占ってほしいこと＝必須項目があるため必ず鑑定できる）。
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime

from . import catalog, presets
from .calc.westastro import resolve_place

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PROFILE_KEYS = ["decision", "money", "stress", "love", "holiday", "new_env", "about_me", "occupation",
                "worry", "period", "partner_status",
                # AMENDMENT_09 §A: 路上版フォームに追加した自由記入（任意。無くても従来どおり動く）
                "worries", "self_desc", "concern_theme"]
CONCERN_THEMES = ["仕事", "恋愛", "お金", "人間関係", "進路・転機", "健康", "その他"]
# AMENDMENT_15: 性別（フォームのラベル「男／女／その他」→ id）。無回答・旧フォーム・不明な値は ""
GENDERS = {"male": "男", "female": "女", "other": "その他"}
_GENDER_ALIASES = {"男": "male", "男性": "male", "male": "male", "m": "male",
                   "女": "female", "女性": "female", "female": "female", "f": "female",
                   "その他": "other", "other": "other"}


class IntakeError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _s(v) -> str:
    return unicodedata.normalize("NFKC", str(v)).strip() if v not in (None, "") else ""


def _date(v) -> str | None:
    v = _s(v).replace("/", "-").replace(".", "-")
    if not v:
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", v) or re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$", v)
    if not m:
        raise ValueError(f"日付の形式が読めません: {v}")
    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if not (1900 <= d.year <= date.today().year):
        raise ValueError(f"生年月日が対応範囲外です（1900年〜今年）: {v}")
    return d.isoformat()


def _time(v) -> str | None:
    v = _s(v)
    if not v or v in ("不明", "わからない"):
        return None
    m = re.match(r"^(\d{1,2})[:時](\d{1,2})?", v)
    if not m:
        raise ValueError(f"時刻の形式が読めません: {v}")
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise ValueError(f"時刻が不正です: {v}")
    return f"{h:02d}:{mi:02d}"


def normalize_gender(v) -> str:
    """"男"/"女"/"その他"（または male/female/other）→ "male"/"female"/"other"。それ以外は ""."""
    return _GENDER_ALIASES.get(_s(v).lower(), "")


def split_kanji_name(display_name: str) -> tuple[str, str]:
    parts = re.split(r"[\s　]+", display_name.strip())
    if len(parts) == 2 and all(parts):
        return parts[0], parts[1]
    return "", ""


def make_job_id(raw: dict, received_at: str) -> str:
    h = hashlib.sha256((received_at + "|" + _s(raw.get("email")) + "|" + _s(raw.get("display_name"))
                        + "|" + _s(raw.get("response_id"))).encode()).hexdigest()[:8]
    return datetime.fromisoformat(received_at).strftime("%Y%m%d-%H%M%S") + "-" + h


def normalize(raw: dict, strict: bool = True) -> dict:
    errors: list[str] = []
    notes: list[str] = []
    received_at = raw.get("received_at") or datetime.now().astimezone().isoformat(timespec="seconds")
    display_name = _s(raw.get("display_name"))
    sur, giv = _s(raw.get("surname_kanji")), _s(raw.get("given_kanji"))
    if not (sur and giv):
        sur, giv = split_kanji_name(display_name)
    profile = {k: _s(v) for k, v in (raw.get("profile") or {}).items() if _s(v)}
    for k in PROFILE_KEYS:
        if _s(raw.get(k)) and k not in profile:
            profile[k] = _s(raw.get(k))
    job = {
        "job_id": raw.get("job_id") or make_job_id(raw, received_at),
        "received_at": received_at,
        "as_of": raw.get("as_of") or datetime.fromisoformat(received_at).strftime("%Y-%m-%d"),
        "source": raw.get("source", "cli"),
        "response_id": raw.get("response_id"),
        "display_name": display_name,
        "name_kana": _s(raw.get("name_kana")),
        "surname_kanji": sur,
        "given_kanji": giv,
        "email": _s(raw.get("email")).lower(),
        "question": _s(raw.get("question")),
        "birth_place": _s(raw.get("birth_place")),
        "daiun_basis": raw.get("daiun_basis") if raw.get("daiun_basis") in ("female", "male") else None,
        "gender": normalize_gender(raw.get("gender")),  # AMENDMENT_15。大運は gender（male/female）を daiun_basis より優先
        "birth_time_precision": raw.get("birth_time_precision") or "exact",
        "profile": profile,
        "tarot_seed": _s(raw.get("tarot_seed")) or None,
        "consent": bool(raw.get("consent")),
        "test_mode": bool(raw.get("test_mode")),
    }
    for key, fn in (("birth_date", _date), ("birth_time", _time)):
        try:
            job[key] = fn(raw.get(key))
        except ValueError as e:
            (errors if strict else notes).append(str(e))
            job[key] = None
    if not job["birth_time"]:
        job["birth_time_precision"] = "unknown"

    try:
        systems, preset = presets.resolve(raw.get("preset") if raw.get("preset") not in (None, "", "custom") else None,
                                          raw.get("systems") or None)
    except (ValueError, KeyError) as e:
        errors.append(str(e) if not isinstance(e, KeyError) else f"未知のハウスブレンド: {e}")
        systems, preset = [], None
    bad = [s for s in systems if s not in catalog.CATALOG or catalog.CATALOG[s]["tier"] not in (1, 2)]
    if bad:
        msg = "選択できない占術（未実装または対象外）: " + "、".join(catalog.CATALOG.get(s, {}).get("name", s) for s in bad)
        (errors if strict else notes).append(msg)
        systems = [s for s in systems if s not in bad]
    if len(systems) > catalog.MAX_SYSTEMS:
        if strict:
            errors.append("占術は1〜3個選んでください")
        else:
            notes.append(f"占術が{len(systems)}個選ばれていたため、最初の3つを採用しました")
        systems = systems[: catalog.MAX_SYSTEMS]

    if not display_name:
        errors.append("名前は必須です")
    if not EMAIL_RE.match(job["email"]):
        errors.append("返送先メールアドレスが正しくありません")
    if not job["consent"]:
        errors.append("免責・個人情報・AI処理への同意が必要です")
    if not job["name_kana"]:
        errors.append("ふりがなは必須です")
    if not job["question"]:
        errors.append("占ってほしいこと（1つ）は必須です")

    have = {
        "birth_date": bool(job["birth_date"]),
        "birth_time": bool(job["birth_time"]) and job["birth_time_precision"] != "unknown",
        "birth_place": resolve_place(job["birth_place"]) is not None,
        "question": bool(job["question"]),
        "name_kanji": bool(job["surname_kanji"] and job["given_kanji"]),
        "name_kana": bool(job["name_kana"]),
    }
    kept = []
    for s in systems:
        missing = [catalog.INPUT_LABELS[r] for r in catalog.CATALOG[s]["required_inputs"] if not have.get(r, True)]
        if missing:
            msg = f"{catalog.CATALOG[s]['name']}には{'・'.join(missing)}が必要です"
            if strict:
                errors.append(msg)
            else:
                notes.append(msg + "（未入力のため今回のブレンドから外しました）")
            continue
        kept.append(s)
    if not strict and not kept and systems and job["question"]:
        kept = ["tarot"]
        notes.append("選ばれた占術に必要な入力が無かったため、タロット単体で鑑定しました")
    if not systems and not errors:
        errors.append("占術またはハウスブレンドを選んでください")
    job["systems"] = kept
    job["preset"] = preset if kept == (presets.PRESETS.get(preset or "", {}).get("systems")) else None
    job["intake_notes"] = notes
    if errors:
        raise IntakeError(errors)
    if not job["tarot_seed"]:
        job["tarot_seed"] = hashlib.sha256(f"{job['job_id']}|{received_at}".encode()).hexdigest()[:16]
    return job
