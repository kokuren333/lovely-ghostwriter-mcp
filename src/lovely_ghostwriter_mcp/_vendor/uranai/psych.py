"""心理学レンズ（AMENDMENT_08 §B）: 使ってよい概念の許可リストと、鑑定文のスタイル検査.

- 概念は「名前のある確立した心理学概念」だけを使う。許可リストに無い概念名は不合格（造語・俗流概念の混入を防ぐ）。
- origin は提唱者・由来として一般に定着しているものだけを書く（不確かなものは空）。論文名・年・数値は持たない（捏造防止）。
- gist はプロンプトに渡す一行定義。Claude はこの定義の範囲で説明する。
詳細なルールは docs/READING_STYLE.md。

予言詩（2ページ目・BRIEF §4）の公開 API（MCP サーバーからも使う）:
  check_poem(poem, job, calc)        … 検査一式（hard=助言調・災厄の断定・禁止表現／soft=モチーフ・逐語・字数・形）
  check_poem_motifs(poem, job, calc) … 入力・占術由来のモチーフを象徴として2つ以上使っているか
  check_poem_literary(poem, job)     … 助言・教訓・励まし調（AMENDMENT_16）＋断定的な災厄の宣告（check_poem_doom）
  poem_text / poem_stanzas / poem_chars … 詩の本文（連の配列）の取り出し
"""
from __future__ import annotations

import json
import re

# name: (origin, gist)
CONCEPTS: dict[str, tuple[str, str]] = {
    "自己効力感": ("バンデューラ", "「自分ならやれる」という見通し。小さな成功体験・身近な手本・励まし・心身の調子から育つ"),
    "統制の所在": ("ロッター", "結果の原因を自分の行動（内的）に置くか、運や他者（外的）に置くかの傾向"),
    "自己決定理論": ("デシとライアン", "自律性・有能感・関係性の3つの欲求が満たされると、内側からの意欲が続きやすいという理論"),
    "愛着スタイル": ("ボウルビィの愛着理論を大人の関係に広げた考え方", "親密さへの不安と、距離を取りたい気持ちの度合いで、人との関わり方の傾向を捉える枠組み"),
    "フロー": ("チクセントミハイ", "難しさと自分の技量がつり合った課題に没頭し、時間を忘れる状態"),
    "成長マインドセット": ("ドゥエック", "能力は工夫と練習で伸びるという捉え方。失敗を学習の材料として扱いやすくなる"),
    "認知の再構成": ("認知行動療法（ベック）", "出来事への受け止め方（とっさの考え）を見直し、別の解釈の可能性を検討すること"),
    "行動活性化": ("認知行動療法の技法", "気分が乗るのを待たず、小さな行動を先に起こして、気分や意欲を後から引き上げる方法"),
    "実行意図（if-thenプランニング）": ("ゴルヴィツァー", "「Xのとき、Yをする」と状況と行動を結びつけて決めておくと、実行に移しやすくなる"),
    "自己成就予言": ("マートン", "予期が行動を変え、その結果、予期どおりの現実が生まれやすくなる現象"),
    "バーナム効果": ("", "誰にでも当てはまるあいまいな記述を、自分だけに当てはまると感じやすい傾向"),
    "確証バイアス": ("", "自分の考えに合う情報ばかりに目が向き、合わない情報を軽く見やすい傾向"),
    "VIAの強み": ("ピーターソンとセリグマン", "人の性格的な強みを24項目で整理した枠組み。自分の強みを日常で使うことが重視される"),
    "心理的安全性": ("エドモンドソン", "集団の中で、率直な発言や失敗の共有をしても責められないと感じられる状態"),
    "境界（バウンダリー）設定": ("", "自分が引き受けること・引き受けないことの線を明確にし、相手に伝えること"),
    "習慣ループ（手がかり・行動・報酬）": ("", "手がかり→行動→報酬の繰り返しで、行動が自動化していくという捉え方"),
    "レジリエンス": ("", "困難やストレスから立ち直り、適応していく力。固定的な性質ではなく、育てられるものとされる"),
    "マインドフルネス": ("", "今この瞬間の体験に、良し悪しの評価を加えずに注意を向けること"),
    "内発的動機づけ": ("", "報酬や評価のためではなく、活動そのものの面白さから生まれる意欲"),
    "損失回避": ("カーネマンとトヴェルスキー", "同じ額なら、得る喜びより失う痛みを大きく感じやすい傾向"),
    "メンタル・アカウンティング": ("セイラー", "お金を出どころや用途ごとに、心の中の別々の「口座」に分けて扱う傾向"),
    "現在バイアス": ("", "将来の大きな利益より、目先の小さな利益を優先しやすい傾向"),
    "計画錯誤": ("カーネマンとトヴェルスキー", "作業にかかる時間や費用を、楽観的に少なく見積もりやすい傾向"),
    "社会的比較": ("フェスティンガー", "自分の能力や意見を、他者と比べて評価しようとする傾向"),
    "認知的不協和": ("フェスティンガー", "考えと行動が食い違う不快感を減らそうとして、考えや行動を調整する傾向"),
    "セルフ・コンパッション": ("ネフ", "失敗やつらい時に、親しい友人に向けるような思いやりを自分に向けること"),
    "自己開示": ("", "自分の考えや気持ちを相手に伝えること。ほどよい自己開示の返し合いは親密さを深めやすい"),
    "ジョブ・クラフティング": ("レズネスキーとダットン", "仕事の進め方・人との関わり・仕事の意味づけを、自分で工夫して手直しすること"),
    "意図的練習": ("エリクソン", "明確な目標・すぐのフィードバック・少し難しい課題で、弱点を狙って行う練習"),
    "アサーション": ("", "相手も自分も尊重しながら、率直に意見や気持ちを伝えるコミュニケーション"),
    "単純接触効果": ("ザイアンス", "くり返し接するだけで、対象への好意が高まりやすい現象"),
    "感情のラベリング": ("", "感じている気持ちに言葉で名前をつけること。気持ちと少し距離を取りやすくなる"),
    "拡張―形成理論": ("フレドリクソン", "前向きな感情が注意や発想の幅を広げ、長い目で見た心の資源を育てるという理論"),
}

# 表記ゆれ → 正式名
ALIASES = {
    "if-thenプランニング": "実行意図（if-thenプランニング）", "実行意図": "実行意図（if-thenプランニング）",
    "if-then プランニング": "実行意図（if-thenプランニング）",
    "バウンダリー": "境界（バウンダリー）設定", "境界設定": "境界（バウンダリー）設定", "バウンダリー設定": "境界（バウンダリー）設定",
    "習慣ループ": "習慣ループ（手がかり・行動・報酬）", "習慣の手がかり・報酬ループ": "習慣ループ（手がかり・行動・報酬）",
    "VIA": "VIAの強み", "VIA の強み": "VIAの強み", "強み（VIA）": "VIAの強み",
    "統制の所在（内的／外的）": "統制の所在", "ローカス・オブ・コントロール": "統制の所在",
    "自己決定理論（自律性・有能感・関係性）": "自己決定理論", "メンタルアカウンティング": "メンタル・アカウンティング",
    "セルフコンパッション": "セルフ・コンパッション", "拡張-形成理論": "拡張―形成理論", "拡張形成理論": "拡張―形成理論",
    "感情ラベリング": "感情のラベリング", "グロースマインドセット": "成長マインドセット",
}

# 二層構造の明示（AMENDMENT_08: 鑑定書のどこかで一度だけ）。テンプレートと report.md が固定文として1回だけ出す。
FRAME_NOTE = "この鑑定書では、占術を自己理解のきっかけ（フレーム）として、心理学の概念を行動の根拠として使っています。"
FRAME_NOTE_SHORT = "占術＝自己理解のきっかけ（フレーム）／心理学＝行動の根拠。"

# 禁止パターン（捏造された出典・数値、診断めいた表現）
FORBIDDEN = [
    (re.compile(r"[0-9０-９]+(\.[0-9０-９]+)?\s*[%％]"), "百分率の数値（出典の無い数値的主張）"),
    (re.compile(r"[0-9０-９]+\s*割(の|が|は|も)"), "割合の数値（出典の無い数値的主張）"),
    (re.compile(r"(研究|調査|実験)(によると|によれば|で[はも]?[0-9０-９])"), "研究・調査の引用風の表現"),
    (re.compile(r"(19|20)[0-9]{2}\s*年[^。]{0,6}(研究|論文|調査|実験)"), "年つきの研究・論文の引用"),
    (re.compile(r"論文|学術誌|ジャーナル|et\s*al", re.I), "論文・出典の引用"),
    (re.compile(r"障害|症候群|疾患|うつ病|発達障|ADHD|ASD|依存症|病的|診断"), "障害・病名・診断めいた表現"),
    (re.compile(r"あなたは[^。、]{0,10}型(です|だ|の人)"), "タイプの断定（傾向・スタイルの水準で書く）"),
    (re.compile(r"フレーム"), "二層構造の明示は固定文が1回だけ出すので、生成文では書かない"),
    # AMENDMENT_09 §B: 根拠のない断定の金銭・医療助言
    (re.compile(r"(株|投資|仮想通貨|暗号資産|FX|NISA|銘柄|不動産)[^。]{0,12}(買いましょう|買うべき|売りましょう|売るべき|始めるべき|必ず儲|間違いなく)"),
     "投資の断定的な指示"),
    (re.compile(r"(薬|治療|通院)[^。]{0,6}(やめ|不要|必要ありません|しなくて)|(病気|症状)[^。]{0,8}(治ります|治る|心配ありません)"),
     "医療的な判断（健康の悩みは医療機関への相談を勧める）"),
]

# ---------------------------------------------------------------- AMENDMENT_09: 本人の言葉への接地（grounding）
# 自由記入（question / worries / self_desc / about_me）から特徴語を取り出し、回答セクションと詩に現れるかを機械で確かめる。
# 形態素解析器は使わず、漢字・カタカナ・英数字の連なり（2字以上）と、本人の言い回しとして詩に引いた anchors を使う。
GENERIC_WORDS = {
    "自分", "今後", "将来", "運勢", "全体", "全体的", "全体運", "総合運", "運気", "金運", "仕事運", "恋愛運", "今後数年", "占い", "占っ", "今年", "来年", "今月", "最近", "気持", "気持ち", "感じ",
    "方向", "方向性", "状況", "ところ", "こと", "もの", "質問", "相談", "悩み", "いま", "今", "時期", "仕事", "恋愛", "お金",
    "人間関係", "健康", "性格", "様子", "最初", "全部", "毎日", "普通", "大丈夫", "具体的", "教え", "知りた", "どう",
}
_WORD_RX = re.compile(r"[一-龥々〆ヵヶ]{2,}|[ァ-ヴー]{2,}|[A-Za-zＡ-Ｚａ-ｚ][A-Za-z0-9Ａ-Ｚａ-ｚ０-９]{1,}|[0-9０-９]+[年月日歳回人]")
CONCRETE_RX = re.compile(
    r"[0-9０-９一二三四五六七八九十百]+\s*(分|秒|回|日|週|か月|ヶ月|カ月|時間|時|行|件|人|個|枚|文字|字|ページ|往復|駅)|"
    r"(毎朝|毎晩|毎日|毎週|毎月|毎回|月末|月初|給料日|昼休み|休憩|帰宅後|出勤前|会議|週に|月に|日に|その場で|朝|夜|昼|寝る前|起きたら|帰り道|通勤|週末|月曜|火曜|水曜|木曜|金曜|土曜|日曜|今日|明日|今週|今月|今夜|定休日|次に|のとき|ときは|時は|時に|たら|前に|後に)|"
    r"「[^」]+」|『[^』]+』|(友人|友達|上司|同僚|家族|親|相手|パートナー|先輩|後輩|恋人|誰か|ひとり)")
ABSTRACT_ENDINGS = re.compile(r"(前向きに|自分を信じ|ポジティブに|大切にしましょう|意識しましょう|心がけましょう|感謝の気持ち)")


def input_texts(job: dict) -> dict:
    pr = job.get("profile") or {}
    return {"question": job.get("question", ""), "worries": pr.get("worries", "") or pr.get("worry", ""),
            "self_desc": pr.get("self_desc", ""), "about_me": pr.get("about_me", "")}


def feature_words(job: dict, keys=("question", "worries")) -> list[str]:
    """本人の自由記入から特徴語（汎用語を除く）を出現順・重複なしで返す."""
    src = input_texts(job)
    out: list[str] = []
    for k in keys:
        for w in _WORD_RX.findall(src.get(k) or ""):
            if w in GENERIC_WORDS or len(w) < 2:
                continue
            if w not in out:
                out.append(w)
    return out


def has_free_text(job: dict) -> bool:
    src = input_texts(job)
    return bool((src["worries"] or "").strip() or (src["self_desc"] or "").strip() or (src["about_me"] or "").strip())


def check_grounding(reading: dict, job: dict, calc: dict | None = None) -> dict:
    """AMENDMENT_09 §B ＋ 予言詩（BRIEF §4）の接地検査。不合格でも描画は止めない（1回だけ再生成し、それでも駄目なら qa.md に理由を記録）.
    calc を渡すと、詩のモチーフのうち calc 由来のもの（source が calc.*）も実在確認できる（渡さなければ calc 由来は数えない）.
    戻り値: {"answer": {...}, "poem": {...}, "steps": {...}, "errors": [...]}"""
    errs: list[str] = []
    # 回答は「占ってほしいこと」の最初の1件だけに答える規則（鑑定の作法4）なので、question の特徴語は採用した質問に含まれるものに限る
    adopted = reading.get("adopted_question", "") or ""
    q_words = feature_words(job, ("question",))
    q_adopted = [w for w in q_words if w in adopted] if adopted else q_words
    feats_q = q_adopted + [w for w in feature_words(job, ("worries",)) if w not in q_adopted]
    ans = reading.get("answer", {})
    ans_text = "".join(ans.get(k, "") for k in ("finding", "lens", "why", "step"))
    hit_a = [w for w in feats_q if w in ans_text]
    need_a = 1 if feats_q else 0
    if len(hit_a) < need_a:
        errs.append(f"回答セクションに本人の言葉（{'・'.join(feats_q[:6])} のどれか）が出てきません。悩みの具体的な言葉を引き受けて書いてください")
    # 予言詩（BRIEF §4）: 本人の言葉の逐語引用ではなく、入力・占術結果に由来するモチーフを象徴として2つ以上織り込む
    pm = check_poem_motifs(reading.get("poem") or {}, job, calc)
    errs += pm["errors"]
    # 一歩の具体性（いつ／頻度／誰に／何と言うか）と精神論の禁止
    steps = {f"themes.{k}": v.get("step", "") for k, v in reading.get("themes", {}).items()}
    steps["answer"] = ans.get("step", "")
    vague = [k for k, v in steps.items() if not CONCRETE_RX.search(v)]
    abstract = [k for k, v in steps.items() if ABSTRACT_ENDINGS.search(v)]
    if vague:
        errs.append(f"一歩に具体形（いつ・頻度・誰に・何と言うか）が無い: {', '.join(vague)}")
    if abstract:
        errs.append(f"一歩が精神論で終わっている: {', '.join(abstract)}")
    return {"answer": {"features": feats_q[:10], "hits": hit_a, "required": need_a, "ok": len(hit_a) >= need_a},
            "poem": {k: v for k, v in pm.items() if k != "errors"},
            "steps": {"vague": vague, "abstract": abstract, "ok": not vague and not abstract},
            "free_text": has_free_text(job), "errors": errs}


# ---------------------------------------------------------------- BRIEF §4: 予言詩（2ページ目）
# 詩は「予言詩」: 四行連を基本とする数連の詩（合計 600〜900字）。本人の入力と占術結果は、言葉そのままの引用ではなく
# モチーフ・象徴として織り込む。生成側は poem.motifs に {source, origin, symbol} を申告し、機械検査で次を確かめる:
#   - source が本人の入力（input.*）または計算結果（calc.<占術ID>…）を指し、origin がそこに実在する
#   - symbol（象徴の語）が詩の本文に現れる
#   - 有効なモチーフが2つ以上（うち本人の入力由来が1つ以上。入力が空なら calc 由来だけでよい）
#   - 本人の自由記入からの長い逐語引用（POEM_VERBATIM_RUN 字以上の連続一致）が無い
POEM_MIN_CHARS, POEM_MAX_CHARS = 600, 900          # 生成の目安（プロンプト・スキーマ）
POEM_TOL_MIN, POEM_TOL_MAX = 540, 960              # 検査の許容幅（はみ出したら再生成1回）
POEM_MAX_LINES, POEM_MAX_LINE_CHARS = 32, 40       # p2 の1ページに収まる上限（fit の W 段階の設計値）
POEM_MIN_MOTIFS = 2
POEM_VERBATIM_RUN = 12
INPUT_SOURCES = ("question", "worries", "self_desc", "about_me", "concern_theme",
                 "personality.decision", "personality.money", "personality.stress", "personality.love")


def poem_stanzas(poem) -> list[list[str]]:
    """詩を連（行のリスト）のリストにする。新形式 {stanzas:[...]}、旧形式 {body}（段落＝連）、文字列のどれでもよい."""
    if isinstance(poem, dict):
        if poem.get("stanzas"):
            raw = [str(x) for x in poem["stanzas"]]
        else:
            raw = re.split(r"\n\s*\n", poem.get("body") or "")
    else:
        raw = re.split(r"\n\s*\n", poem or "")
    out = []
    for st in raw:
        lines = [ln.strip() for ln in st.split("\n") if ln.strip()]
        if lines:
            out.append(lines)
    return out


def poem_text(poem) -> str:
    """詩の本文（連は空行、行は改行で区切る）."""
    return "\n\n".join("\n".join(lines) for lines in poem_stanzas(poem))


def poem_chars(poem) -> int:
    """字数（改行を除く。行内の全角スペースは字として数える）."""
    return len(re.sub(r"[\r\n]", "", poem_text(poem)))


def input_sources(job: dict) -> dict[str, str]:
    """詩のモチーフの出どころになる本人の入力（キー → テキスト）。空のものは含めない."""
    pr = job.get("profile") or {}
    src = {**input_texts(job), "concern_theme": pr.get("concern_theme", "")}
    for k in ("decision", "money", "stress", "love"):
        src[f"personality.{k}"] = pr.get(k, "")
    return {k: str(v) for k, v in src.items() if v and str(v).strip()}


def _calc_subtree(calc: dict | None, path: str):
    """'tarot.spread[9]' のようなパスを calc["results"] の中でたどれる所までたどる（LLM の書き方の揺れに寛容に）."""
    if not calc:
        return None
    node = calc.get("results") or {}
    parts = [p for p in re.split(r"\.|\[|\]", path) if p != ""]
    if not parts or parts[0] not in node:
        return None
    for i, key in enumerate(parts):
        if isinstance(node, dict) and key in node:
            node = node[key]
        elif isinstance(node, list) and key.isdigit() and int(key) < len(node):
            node = node[int(key)]
        else:
            break  # 以降は寛容に無視（サブツリー全体で origin を探す）
    return node


def _norm(s: str) -> str:
    return re.sub(r"[\s　]", "", str(s or ""))


def motif_source_text(source: str, job: dict, calc: dict | None) -> str | None:
    """モチーフの source（input.worries / calc.tarot.spread[9] 等）が指すテキスト。実在しなければ None."""
    s = (source or "").strip()
    if s.startswith("input."):
        return input_sources(job).get(s[len("input."):])
    if s.startswith("calc."):
        node = _calc_subtree(calc, s[len("calc."):])
        if node is None:
            return None
        return node if isinstance(node, str) else json.dumps(node, ensure_ascii=False)
    return None


def _verbatim_runs(body: str, job: dict, n: int = POEM_VERBATIM_RUN) -> list[str]:
    """本人の自由記入から n 字以上を連続してそのまま写した箇所（逐語引用）."""
    b = _norm(body)
    found: list[str] = []
    for k in ("question", "worries", "self_desc", "about_me"):
        t = _norm(input_texts(job).get(k, ""))
        i = 0
        while i + n <= len(t):
            if t[i:i + n] in b:
                j = i + n
                while j < len(t) and t[i:j + 1] in b:
                    j += 1
                found.append(t[i:j])
                i = j
            else:
                i += 1
    return found


def check_poem_motifs(poem, job: dict, calc: dict | None = None) -> dict:
    """予言詩のモチーフ（象徴）検査（BRIEF §4。旧「本人の言葉3か所以上・逐語」の置き換え）.
    戻り値: {"motifs": [{source, origin, symbol, ok, reason}], "valid": n, "from_input": n, "required": 2,
             "chars": 字数, "stanzas": 連数, "lines": 行数, "verbatim": [...], "ok": bool, "errors": [...]}"""
    poem = poem if isinstance(poem, dict) else {"body": poem or ""}
    body = poem_text(poem)
    nb = _norm(body)
    rows, errs = [], []
    for m in poem.get("motifs") or []:
        src, origin, symbol = (m.get("source") or "").strip(), (m.get("origin") or "").strip(), (m.get("symbol") or "").strip()
        st = motif_source_text(src, job, calc)
        reason = ""
        if not src.startswith(("input.", "calc.")):
            reason = "source は input.<項目> か calc.<占術ID>… で書く"
        elif st is None:
            reason = "source が本人の入力・計算結果に存在しない（空欄の項目を含む）"
        elif not origin or _norm(origin) not in _norm(st):
            reason = "origin が source のテキストに実在しない"
        elif not symbol or _norm(symbol) not in nb:
            reason = "symbol（象徴の語）が詩の本文に出てこない"
        rows.append({"source": src, "origin": origin, "symbol": symbol, "ok": not reason, "reason": reason})
    valid = [r for r in rows if r["ok"]]
    from_input = [r for r in valid if r["source"].startswith("input.")]
    has_input = bool(input_sources(job))
    if len(valid) < POEM_MIN_MOTIFS or (has_input and not from_input):
        errs.append(f"詩のモチーフ（入力・占術結果に由来する象徴）が有効なもので{len(valid)}つしかありません"
                    f"（{POEM_MIN_MOTIFS}つ以上、うち本人の入力由来を1つ以上。poem.motifs の source/origin を実在のものに、symbol は本文と同じ表記に）")
    bad = [r for r in rows if not r["ok"]]
    if bad:
        errs.append("poem.motifs の不備: " + " / ".join(f"{r['symbol'] or '?'}（{r['source'] or '?'}）— {r['reason']}" for r in bad[:4]))
    verb = _verbatim_runs(body, job)
    if verb:
        errs.append(f"詩に本人の自由記入の逐語引用があります（{POEM_VERBATIM_RUN}字以上の一致: {'／'.join(v[:20] for v in verb[:3])}）。言葉そのままではなく象徴に置き換える")
    n = poem_chars(poem)
    stz = poem_stanzas(poem)
    nlines = sum(len(s) for s in stz)
    long_lines = [ln for s in stz for ln in s if len(_norm(ln)) > POEM_MAX_LINE_CHARS]
    if body and not (POEM_TOL_MIN <= n <= POEM_TOL_MAX):
        errs.append(f"詩の長さが {n} 字（目安 {POEM_MIN_CHARS}〜{POEM_MAX_CHARS}字）")
    if body and (len(stz) < 3 or nlines > POEM_MAX_LINES):
        errs.append(f"詩の形が p2 の1ページに合いません（{len(stz)}連・{nlines}行。3〜8連・合計{POEM_MAX_LINES}行以内）")
    if long_lines:
        errs.append(f"1行が長すぎます（{POEM_MAX_LINE_CHARS}字以内）: {long_lines[0][:24]}…")
    return {"motifs": rows, "valid": len(valid), "from_input": len(from_input), "required": POEM_MIN_MOTIFS,
            "hits": [r["symbol"] for r in valid], "chars": n, "stanzas": len(stz), "lines": nlines, "verbatim": verb,
            "ok": not errs, "errors": errs}


# 予言としての不吉な暗示・曖昧さは文学表現として許容するが、断定的な災厄の宣告（直接表現）は禁止（BRIEF §4）。
# 象徴（「灰色の鳥」「欠けた月」「死神のカード」）は対象外。人・本人に起きる出来事としての直接の宣告だけを拾う。
POEM_DOOM_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"死(?:ぬ|にます|んでしまう|が訪れ|が迫|期が)|命を(?:落と|失)|亡くな(?:る|ります|ってしまう)|息絶え|帰らぬ人"), "死の宣告"),
    (re.compile(r"事故(?:に遭|にあ|が起き|が起こ|を起こ)|(?:大)?怪我を(?:する|します|負)|大怪我"), "事故・怪我の宣告"),
    (re.compile(r"(?:病気|病|大病|重病)に(?:なる|なります|かか|倒れ)|病に倒れ|余命|(?:癌|がん)(?:になる|が見つか)"), "病気の宣告"),
    (re.compile(r"(?:災害|地震|火事|火災|津波)に(?:遭|あ|巻き込まれ)|家が燃え"), "災害の宣告"),
    (re.compile(r"(?:破産|倒産|離婚|失業|解雇|破局)(?:する|します|に至る|が待って|は避けられ)|(?:解雇|捨て|裏切)られ(?:る|ます)[。\n]?$"),
     "破綻・別離の断定"),
    (re.compile(r"(?:殺さ|襲わ|盗ま)れ(?:る|ます)|不幸が(?:訪れ|襲)|呪われ|災いが(?:降りかか|訪れ)"), "加害・不幸の断定"),
]


def check_poem_doom(poem) -> list[str]:
    """予言詩の禁止事項: 断定的な災厄の宣告（死・事故・病・災害・破綻の直接表現）。戻り値は理由のリスト（空=合格）."""
    out: list[str] = []
    for _, sent in _poem_sentences(poem_text(poem) if not isinstance(poem, str) else poem):
        for rx, why in POEM_DOOM_PATTERNS:
            if rx.search(sent.strip()):
                s = sent.strip()
                out.append(f"詩に断定的な災厄の表現「{s if len(s) <= 60 else s[:58] + '…'}」— {why}（不吉さは象徴に留める）")
                break
    return out[:12]


def check_poem(poem, job: dict, calc: dict | None = None) -> dict:
    """予言詩の検査一式（MCP サーバー等から単独で使う入口）.
    戻り値: {"hard": [...], "soft": [...], "motifs": check_poem_motifs の結果, "ok": bool}
      hard = 助言・教訓・励まし調（AMENDMENT_16）と断定的な災厄の宣告。1回だけ再生成し、残れば描画しない
      soft = モチーフ（2つ以上）・逐語引用・字数・連の形。1回だけ再生成し、残れば理由を記録して採用してよい"""
    hard = check_poem_literary(poem, job)
    pm = check_poem_motifs(poem, job, calc)
    soft = list(pm["errors"])
    if isinstance(poem, dict):
        for path, text in [("poem.title", poem.get("title") or "")] + [(f"poem.stanzas[{i}]", s) for i, s in enumerate(poem.get("stanzas") or [])]:
            for rx, why in FORBIDDEN:
                m = rx.search(text)
                if m:
                    hard.append(f"{path}: 「{m.group(0)}」— {why}")
    return {"hard": hard, "soft": soft, "motifs": {k: v for k, v in pm.items() if k != "errors"}, "ok": not hard and not soft}


# ---------------------------------------------------------------- AMENDMENT_16: 散文詩は「文学」であって「助言」ではない
# 詩（poem.body）に助言・教訓・行動提案・読者への励ましが混ざっていないかを機械で確かめる。p1 の助言層の検査
# （check_grounding の具体性・接地）とは別物で、混ぜない。描写文の誤検出を避けるため、多くは文末・定型の形に限定している。
POEM_ADVICE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?<!ごめん)(?<!おやすみ)(?<!かえり)(?<!帰り)なさい"), "命令形（〜しなさい）"),
    (re.compile(r"[てで](?:くだ|下)さい"), "依頼・勧告（〜てください）"),
    (re.compile(r"べき(?:です|でしょう|だ(?!っ)|では|なの)|べき[。！!」]|べし[。！!]"), "当為（〜すべき）"),
    (re.compile(r"ましょう"), "勧誘（〜しましょう）"),
    (re.compile(r"(?<!どう)(?<!こう)(?<!そう)(?<!ああ)しよう(?![とがもにな])"), "勧誘（〜しよう）"),
    (re.compile(r"[てで]み(?:よう|ませんか|て(?:ね|ほしい|[。！!」])|たら(?:どう|いい))"), "働きかけ（〜してみて）"),
    (re.compile(r"[てで](?:いこう|行こう|おこう|ごらん)"), "勧誘（〜していこう）"),
    (re.compile(r"(?:[えけげせぜてでねべめれきじびみり]よう|(?:踏み出そ|進も|歩こ|行こ|休も|話そ|書こ|選ぼ|頼ろ|任せよ)う)[。！!]$"),
     "勧誘・意志の呼びかけ（〜よう）"),
    (re.compile(r"(?:し|行き|始め|休み|話し)ませんか"), "勧誘（〜しませんか）"),
    (re.compile(r"(?:大切|大事|肝心)(?:です|なのは|なこと(?:は|です)|なんです)|ことが(?:大切|大事|肝心|必要)"), "教訓・まとめ（大切なのは〜）"),
    (re.compile(r"忘れずに|忘れないで(?:ください|ね|ほしい|[。！!」])"), "教訓（忘れずに）"),
    (re.compile(r"心がけ|心掛け|意識して(?:みて|ください|いき)"), "教訓（心がけたい）"),
    (re.compile(r"一歩として|一歩を踏み出し(?:ましょう|てみ|て(?:ください|ね|[。！!]))"), "行動提案（p1「一歩」の領分）"),
    (re.compile(r"まずは[^。！？!?\n]{0,24}?(?:する|して|しよう|しましょう|から(?:始め|はじめ))"), "行動提案（まずは〜）"),
    (re.compile(r"(?:[けげせてねべめれ]ば|たら|ると|のが|方が|ほうが)(?:いい|よい|良い)(?:んです|のです|です|でしょう|よ)?[。！!]"), "勧告（〜すればいい）"),
    (re.compile(r"なくて(?:も)?(?:いい|大丈夫|かまわない)(?:んです|のです|です|よ)?[。！!]"), "読者への許可・励まし（〜しなくていい）"),
    (re.compile(r"(?:あなた|君|きみ)(?:なら|だから)[^。！!]{0,12}(?:大丈夫|できる|やれる|乗り越え)|きっと大丈夫|大丈夫(?:です)?よ|"
                r"応援して(?:います|る)|自分を信じ|前向きに|頑張って|がんばって"), "読者への励まし（あなたなら大丈夫）"),
    (re.compile(r"ますように[。！!]?$"), "読者への祈り・励ましで閉じている（〜ますように）"),
    # 予言詩（BRIEF §4）: 託宣調の命令（「〜せよ」「気をつけよ」）も助言の一種として禁止。「いずれにせよ」は対象外
    (re.compile(r"(?<!に)せよ[。！!、]?$|(?:気をつけ|用心|注意)(?:よ|ろ|せよ)[。！!]?$|(?:恐れる|迷う)な[。！!]?$"), "託宣調の命令（〜せよ／気をつけよ）"),
]
# 二人称（あなた／君）が出てくる文に限って見る、助言文脈の形（単独では描写にも現れるため）
POEM_SECOND_PERSON = re.compile(r"あなた|君|きみ")
POEM_SECOND_PERSON_ADVICE = re.compile(
    r"[てで](?:ほしい|ね[。！!]?$)|(?<!の)ように[。！!]?$|[てで]もいい|[てで]いい(?:んです|のです|よ)?[。！!]?$|ないで[。！!]?$|"
    r"必要は(?:ない|ありません)|(?:し|行っ|休ん|話し)ていい")
_SENT_RX = re.compile(r"[^。！？!?\n]*[。！？!?]?")


def _poem_sentences(body: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(0)) for m in _SENT_RX.finditer(body or "") if m.group(0).strip()]


def check_poem_literary(poem, job: dict | None = None) -> list[str]:
    """AMENDMENT_16: 散文詩の助言調検出。戻り値は理由（該当箇所つき）のリスト。空なら合格.
    poem は reading["poem"]（dict。stanzas または旧 body）または本文の文字列。job を渡すと、本人の入力にそのまま実在する
    「」内の引用（本人の言葉）は対象外にする（例: 「転職するべきか」）。
    予言詩（BRIEF §4）の断定的な災厄の宣告（check_poem_doom）も同じ「描画を止める」系の検査としてここで返す。"""
    body = poem_text(poem) if isinstance(poem, dict) else (poem or "")
    own = "\n".join(input_texts(job).values()) if job else ""
    own_spans = [(m.start(), m.end()) for m in re.finditer(r"「([^」]+)」", body) if own and m.group(1) in own]
    out: list[str] = []
    seen: set[tuple[str, str]] = set()

    def add(start: int, sent: str, why: str):
        s = sent.strip()
        if (s, why) in seen or len(out) >= 12:  # 同じ文の重複は1回だけ。理由の列挙は12件まで
            return
        seen.add((s, why))
        out.append(f"詩に助言調の表現「{s if len(s) <= 60 else s[:58] + '…'}」— {why}")

    for start, sent in _poem_sentences(body):
        stripped = sent.rstrip()
        for rx, why in POEM_ADVICE_PATTERNS:
            for m in rx.finditer(stripped):
                pos = start + m.start()
                if any(a <= pos < b for a, b in own_spans):
                    continue
                add(start, sent, why)
                break
        if POEM_SECOND_PERSON.search(stripped):
            m = POEM_SECOND_PERSON_ADVICE.search(stripped)
            if m and not any(a <= start + m.start() < b for a, b in own_spans):
                add(start, sent, "二人称への直接の働きかけ（助言文脈）")
    return out + check_poem_doom(body)


def normalize_concept(name: str) -> str | None:
    n = (name or "").strip()
    if n in CONCEPTS:
        return n
    if n in ALIASES:
        return ALIASES[n]
    return None


def prompt_table() -> str:
    lines = []
    for k, (origin, gist) in CONCEPTS.items():
        lines.append(f"- {k}" + (f"（{origin}）" if origin else "") + f": {gist}")
    return "\n".join(lines)


def _texts(reading: dict) -> list[tuple[str, str]]:
    """(path, text) for every generated prose field (the customer's own question is excluded)."""
    out = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.startswith("_") or k in ("adopted_question", "origin", "source"):  # origin/source は本人の入力・calc の写し
                    continue
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
        elif isinstance(o, str):
            out.append((path, o))
    walk(reading, "")
    return out


def check_style(reading: dict) -> list[str]:
    """Return a list of style violations (empty = OK). Normalizes concept names in place."""
    errs: list[str] = []
    lensed = [(f"themes.{k}", v) for k, v in reading["themes"].items()] + [("answer", reading["answer"])]
    for path, o in lensed:
        c = normalize_concept(o.get("concept", ""))
        if not c:
            errs.append(f"{path}.concept「{o.get('concept')}」は許可リストにない概念名")
        else:
            o["concept"] = c
        for f in ("finding", "lens", "why", "step"):
            if not (o.get(f) or "").strip():
                errs.append(f"{path}.{f} が空")
    ig = reading["integration"]
    fixed = []
    for c in ig.get("concepts", []):
        n = normalize_concept(c)
        if not n:
            errs.append(f"integration.concepts「{c}」は許可リストにない概念名")
        else:
            fixed.append(n)
    ig["concepts"] = fixed
    if len(fixed) > 2:
        errs.append("integration.concepts は2つまで")
    for path, text in _texts(reading):
        for rx, why in FORBIDDEN:
            m = rx.search(text)
            if m:
                errs.append(f"{path}: 「{m.group(0)}」— {why}")
    return errs
