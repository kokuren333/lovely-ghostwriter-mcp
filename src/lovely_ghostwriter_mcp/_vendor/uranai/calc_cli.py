"""決定論的計算 CLI: 正規化済みジョブJSON -> calc.json

usage: python -m uranai.calc_cli <job.json> <out_calc.json> [--as-of YYYY-MM-DD]

同じ入力・同じ as-of なら必ずバイト単位で同じ出力（sort_keys, 固定インデント）。
Codex CLI はこのコマンドを実行するだけで、値を自分で計算しない。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path

from . import catalog
from .calc import astro, bazi, kyusei, numerology, seimei, tarot, westastro

ENGINE_VERSION = "1.2.0"  # 1.2.0: 大運の順逆を性別＋年干の陰陽で決定（AMENDMENT_15）／1.1.0: タロット=ケルティッククロス10枚・散文詩テーマ（AMENDMENT_09）


def _run_system(s: str, job: dict, now: datetime) -> dict:
    bd, bt = job.get("birth_date"), job.get("birth_time")
    if s == "bazi":
        return bazi.calculate(bd, bt, job.get("daiun_basis"), now=now, gender=job.get("gender"))
    if s == "kyusei":
        return kyusei.calculate(bd, bt, now=now)
    if s == "numerology":
        return numerology.calculate(bd, job.get("name_kana"), now=now)
    if s == "tarot":
        return tarot.draw(job["tarot_seed"], job.get("question"), (job.get("profile") or {}).get("concern_theme"))
    if s == "seimei":
        return seimei.calculate(job.get("surname_kanji"), job.get("given_kanji"))
    if s == "westastro":
        return westastro.calculate(bd, bt, job.get("birth_place"), job.get("birth_time_precision", "exact"))
    mod = importlib.import_module(f".calc.{s}", __package__)
    if s in ("eto",):
        return mod.calculate(bd, bt, now=now)
    if s in ("vedic", "shukuyo"):
        return mod.calculate(bd, bt)
    if s == "kabbalah":
        return mod.calculate(job.get("name_kana"), bd)
    if s == "sanmei":
        return mod.calculate(bd, now=now) if "now" in mod.calculate.__code__.co_varnames else mod.calculate(bd)
    return mod.calculate(bd)  # maya, birthcard, birthstone


def compute(job: dict, as_of: str) -> dict:
    now = datetime.fromisoformat(as_of + "T12:00:00").replace(tzinfo=astro.JST)
    res: dict = {}
    for s in job["systems"]:
        res[s] = _run_system(s, job, now)
        res[s]["tier"] = catalog.CATALOG[s]["tier"]
    return {
        "engine": "uranai.calc", "engine_version": ENGINE_VERSION, "as_of": as_of,
        "job_id": job["job_id"], "systems": job["systems"],
        "blend": {"label": catalog.blend_label(job["systems"]),
                  "roles": [{"system": s, "name": catalog.CATALOG[s]["name"], "role": catalog.CATALOG[s]["role"],
                             "tier": catalog.CATALOG[s]["tier"]} for s in job["systems"]]},
        "results": res,
        "poem": poem_theme(job),
    }


# AMENDMENT_09 §D／BRIEF §4: 予言詩のテーマ（中心の象徴）。ジョブのシードから決定的に1つ選ぶ（再生成で変わらない）
POEM_THEMES = ["欠けた月", "七つ目の扉", "砂時計", "錆びた鍵", "灰色の鳥", "北の星", "水底の鐘", "霧の橋",
               "白い羽根", "燃える手紙", "逆さの塔", "潮目", "眠る種", "古い地図", "鏡の向こう", "夜明けの鐘",
               "銀の糸", "日蝕", "迷い蝶", "閉じた窓", "風見鶏", "三つの灯", "冬の扉", "夜の書架"]


def poem_theme(job: dict) -> dict:
    seed = job.get("tarot_seed") or job["job_id"]
    i = int.from_bytes(hashlib.sha256(f"{seed}:poem-theme".encode("utf-8")).digest(), "big") % len(POEM_THEMES)
    return {"theme": POEM_THEMES[i], "index": i, "seed": seed,
            "rule": "SHA-256(seed + ':poem-theme') mod 24 で POEM_THEMES から選択"}


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("out")
    ap.add_argument("--as-of", default=None)
    a = ap.parse_args(argv)
    job = json.loads(Path(a.job).read_text(encoding="utf-8"))
    as_of = a.as_of or job["as_of"]
    text = dumps(compute(job, as_of))
    Path(a.out).write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(json.dumps({"ok": True, "out": str(a.out), "sha256": sha256_text(text)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
