"""Offline stand-in for Claude output (max-length texts, psych-lens schema) — used only by tests/layout checks."""
from .uranai import catalog
from .uranai.calc.tarot import SPREAD

# 2ページ目の予言詩（BRIEF §4）の見本: 四行連×7・約880字（上限 900字・32行に近い、レイアウト負荷の大きい形）。
# tests の RAW 入力（後輩・転職・カフェ・資格・慎重・疲れ）を、引用ではなく象徴（若い燕・琥珀の杯・まだ読まれぬ頁・錆びた羅針）で織り込む。
POEM_STANZAS = [
    "十一番目の月が　西の端から欠けはじめるころ\n北の窓辺に置かれた錆びた羅針が　かすかにふるえだす\n針はまだどの方角も指さず　眠たげに首を振りながら\n古い港の名前を三度　誰にも聞こえない声でくりかえす",
    "軒下には若い燕が一羽　去年の巣にまだ身を寄せている\nあなたが門を出れば巣は冷えると　夜ごと風がささやく\nけれど燕の翼はもう　季節の匂いを知りはじめていて\nその細い影が朝ごとに　あなたの足もとを横切ってゆく",
    "週末の灯の下には琥珀の杯がひとつ　底に文字が沈む\nまだ読まれぬ頁が幾枚も　息をひそめて順番を待つ\n六枚目の頁がめくられる朝　杯の琥珀はわずかに澄み\nその底に　まだ誰も歩いたことのない街の地図が浮かぶ",
    "東の空に灰色の鳥が三羽　低く輪を描いて渡ってくる\n一羽は過ぎた日々の重さを　濡れた羽根に包んで運び\n一羽は告げられなかった言葉を　嘴の先にくわえている\n最後の一羽だけが　まだ行き先を誰にも明かさない",
    "橋の上で風が二つに裂ける夜が　冬の入口に用意されている\n片方の風は帰り道の匂い　もう片方は遠い潮の匂い\nどちらの風もあなたの外套の裾を　同じ強さで引きながら\nどちらの風も名前を呼ばずに　欄干の向こうへ過ぎてゆく",
    "錆びた羅針は　やがて長い眠りから目を覚ますだろう\nそれは嵐の朝ではなく　雨が上がったあとの静かな刻\n軒下の巣がようやく空になり　燕の声が遠くなる日に\n針ははじめて迷わずに　ただ一つの方角を指しはじめる",
    "そのとき琥珀の杯は乾き　頁は最後の一行まで読まれ\n灰色の鳥の最後の一羽が　あなたの胸の内に静かに降りる\n七つ目の扉の鍵は　いつのまにか冷たい掌の中にあり\n鐘が鳴る　まだこの町の誰も聞いたことのない澄んだ音で",
]
POEM_MOTIFS = [
    {"source": "input.worries", "origin": "後輩", "symbol": "若い燕"},
    {"source": "input.worries", "origin": "カフェ", "symbol": "琥珀の杯"},
    {"source": "input.worries", "origin": "資格の勉強", "symbol": "まだ読まれぬ頁"},
    {"source": "input.self_desc", "origin": "慎重すぎて動けない", "symbol": "錆びた羅針"},
]


def L(n, base="あなたの持ち味は、落ち着いた観察力と粘り強さです。"):
    s = ""
    while len(s) < n:
        s += base
    return s[:n - 1] + "。"


CONCEPTS = ["自己効力感", "フロー", "VIAの強み", "メンタル・アカウンティング"]


def lensed(concept, f, l, w, st, pf, pl):
    return {"finding": L(f), "concept": concept, "lens": L(l), "why": L(w), "step": L(st, "朝に10分だけ計画を書き出す"),
            "print_finding": L(pf), "print_lens": L(pl)}


def make(job):
    sy = job["systems"]
    th = lambda c: {"score": 4, "basis": "四柱推命の日主と今年の通変星", **lensed(c, 75, 65, 65, 30, 30, 45)}
    return {
        "headline": "静かな観察眼で、次の一歩を選ぶ年",
        "summary": L(90), "adopted_question": "来年の仕事の方向性は？",
        "blend_roles": [{"system": s, "role": catalog.CATALOG[s]["role"][:20]} for s in sy],
        "system_readings": [{"system": s, "key_facts": ["値A", "値B"], "reading": L(110), "reading_print": L(50)} for s in sy],
        "themes": {k: th(c) for k, c in zip(("work", "love", "talent", "money"), CONCEPTS)},
        "integration": {"agreements": [L(45), L(45)], "differences": [L(45), L(45)], "self_report_link": L(100),
                        "self_report_print": L(50), "concepts": ["確証バイアス", "成長マインドセット"],
                        "synthesis": L(200), "synthesis_print": L(90), "flavor": "ほろ苦さの奥に甘さが残る一杯"},
        "answer": lensed("実行意図（if-thenプランニング）", 110, 80, 80, 34, 45, 55),
        "advice": {"caution": L(45)},
        "focus_note": L(60, "自由記入が空のため、気になるテーマと性格の回答から焦点を作りました。"),
        "tarot_cross": ([{"position": k, "note": L(30, "後輩への引き継ぎが、踏み出す足場になる。")} for k, _ in SPREAD]
                        if "tarot" in sy else []),
        "poem": {"title": "七つ目の扉が鳴る夜に", "stanzas": list(POEM_STANZAS), "motifs": [dict(m) for m in POEM_MOTIFS]},
    }


def max_poem():
    """レイアウトの最悪形: 8連×4行＝32行・900字（スキーマ・検査の上限）."""
    lines = [ln for st in POEM_STANZAS for ln in st.split(chr(10))]
    out, total = [], 0
    for i in range(8):
        st = []
        for j in range(4):
            ln = lines[(i * 4 + j) % len(lines)]
            ln = (ln + "　" + ln)[:28]
            st.append(ln)
            total += len(ln)
        out.append(chr(10).join(st))
    out[-1] = out[-1] + "　" * max(0, 900 - total - 1) if total < 900 else out[-1]
    return {"title": "七つ目の扉が鳴る夜に", "stanzas": out, "motifs": [dict(m) for m in POEM_MOTIFS]}
