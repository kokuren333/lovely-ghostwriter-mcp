"""ハウスブレンド（推奨組み合わせ）— 路上で迷わないためのメニュー。目安であり自由選択も可.
ラベルは Google フォーム（docs/FORM_SPEC.md）の選択肢と一致させること。"""
from __future__ import annotations

PRESETS = {
    "classic": {"name": "王道ブレンド", "systems": ["bazi", "tarot"],
                "label": "王道ブレンド（四柱推命×タロット）", "tagline": "生まれ持った資質 × 今の答え。迷ったらこれ"},
    "love": {"name": "恋愛ブレンド", "systems": ["tarot", "numerology", "bazi"],
             "label": "恋愛ブレンド（タロット×数秘術×四柱推命）", "tagline": "今の気持ち・人生のテーマ・資質を重ねる"},
    "work": {"name": "仕事ブレンド", "systems": ["bazi", "kyusei"],
             "label": "仕事ブレンド（四柱推命×九星気学）", "tagline": "資質と運気の波から、動きどきを知る"},
    "flow": {"name": "運気と方位ブレンド", "systems": ["tarot", "numerology", "kyusei"],
             "label": "運気と方位ブレンド（タロット×数秘術×九星気学）", "tagline": "今年のリズムと方位、今の一手"},
    "name": {"name": "名前ブレンド", "systems": ["seimei", "numerology", "kabbalah"],
             "label": "名前ブレンド（姓名判断×数秘術×カバラ数秘）", "tagline": "名前の画数と響きから、あなたの核を読む"},
    "moon": {"name": "月の暦ブレンド", "systems": ["shukuyo", "vedic", "maya"],
             "label": "月の暦ブレンド（宿曜×インド占星術×マヤ暦）", "tagline": "月と暦の巡りで読む、心の質"},
    "stars": {"name": "星読みブレンド", "systems": ["westastro", "bazi"],
              "label": "星読みブレンド（西洋占星術×四柱推命）※生まれた時刻と都道府県が必要", "tagline": "東西の暦で読む資質"},
    "single": {"name": "お試しシングル", "systems": ["tarot"],
               "label": "お試しシングル（タロットのみ・生年月日なしOK）", "tagline": "タロットだけで今の質問に答える"},
}
CUSTOM_LABEL = "自分で選ぶ（最大3つ）"


def resolve(preset: str | None, systems: list[str] | None) -> tuple[list[str], str | None]:
    if systems:
        return list(dict.fromkeys(systems)), None
    if preset:
        return list(PRESETS[preset]["systems"]), preset
    raise ValueError("占術またはハウスブレンドを選んでください")
