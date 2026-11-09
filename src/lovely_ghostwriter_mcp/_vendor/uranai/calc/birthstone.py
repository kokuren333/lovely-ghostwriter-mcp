"""誕生石（日本） — 1958年の伝統的な一覧によるデータ参照（計算ではない）."""
from __future__ import annotations

STONES = {
    1: ["ガーネット"],
    2: ["アメシスト"],
    3: ["アクアマリン", "コーラル"],
    4: ["ダイヤモンド"],
    5: ["エメラルド", "ヒスイ"],
    6: ["パール", "ムーンストーン"],
    7: ["ルビー"],
    8: ["ペリドット", "サードオニクス"],
    9: ["サファイア"],
    10: ["オパール", "トルマリン"],
    11: ["トパーズ", "シトリン"],
    12: ["ターコイズ", "ラピスラズリ"],
}

CONVENTIONS = [
    "1958年に全国宝石卸商協同組合が制定した日本の誕生石一覧（伝統版）による",
    "2021年の改定で追加された石は本アプリでは含めていない（1958年の伝統版のみ）",
    "誕生月から表を引くデータ参照（実装Tier2）であり、天文計算などの算出ではない",
    "誕生月はグレゴリオ暦の月（JST）",
]


def calculate(birth_date: str) -> dict:
    y, m, d = (int(x) for x in birth_date.split("-"))
    return {
        "system": "birthstone",
        "status": "ok",
        "tier": "Tier2",
        "input": {"birth_date": birth_date},
        "month": m,
        "stones": list(STONES[m]),
        "label": "・".join(STONES[m]),
        "source": "全国宝石卸商協同組合制定（1958年）",
        "conventions": CONVENTIONS,
        "warnings": [],
        "unavailable": [],
    }
