"""鑑定文生成: Claude Code CLI（claude-opus-5-5, effort medium）を JSON Schema つきで呼び、構造化データを得る.
得られたデータから構造化 Markdown（report.md）を決定論的に組み立てる。

予言詩（2ページ目・BRIEF §4）の公開 API（MCP サーバーからも使う）:
  build_poem_prompt(job, calc) -> (system_prompt, user_prompt)  … 予言詩だけを生成するプロンプト
  poem_schema() -> dict                                          … 出力スキーマ（reading.schema.json の properties.poem）
  poem_payload(job, calc) / poem_motif_sources(job, calc)        … コンテキストとモチーフの出どころ一覧
  POEM_STYLE_GUIDE                                               … 文体ガイド（鑑定全体の SYSTEM_PROMPT にも埋め込み）
  検査は psych.check_poem(poem, job, calc)。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import jsonschema

from . import catalog, psych
from .config import ROOT, settings

SCHEMA_PATH = ROOT / "schemas" / "reading.schema.json"

SYSTEM_PROMPT_BASE = """あなたは「天使の自動筆記（ラブリーゴーストライター）」の占術ブレンド鑑定士です。お客様に渡す鑑定書の文章（1ページ目の鑑定プロフィールと、2ページ目の予言詩）を書きます。
入力として、ハーネスが検証済みの計算結果（calc）、計算スキルの分析メモ（analysis、無い場合あり）、お客様の自己申告（profile）と占ってほしいことが渡されます。
文体は「心理学レンズ付きの啓蒙的な鑑定」です（docs/READING_STYLE.md）。占術の結果を並べるだけで終わらせず、読み手が「占いが当たった」ではなく「自分の心の動きが分かった」と持ち帰れる文章にします。

# 鑑定の作法（必ず守る）
1. 数値・干支・星・カード・画数などの計算値は calc に書かれたものだけを使う。自分で計算・推測・補完しない。calc に無い値は書かない。
2. status が partial / unavailable の項目、unavailable に挙がっている項目、warnings にある境界付近の値は断定しない（「時刻不明のため時柱は判定していません」のように正直に書く）。
3. 占術間の矛盾は優劣をつけずに併記する。同じ生年月日に由来する占術同士の一致を「独立した裏付け」と書かない。
4. 鑑定の枠は固定: 仕事・恋愛・才能・金運の4テーマ＋占ってほしいこと1件だけ。占ってほしいことが複数書かれていたら最初の1件だけに答え、adopted_question にそれを書く。他のテーマを増やさない。
5. 死亡・病気・事故・災害などの断定的予言をしない。医療・法律・投資の助言をしない（健康の悩みには医療機関への相談を勧める）。脅す・不安をあおる表現、依存をうながす表現を使わない。
6. 第三者（恋人・家族など）を本人の同意なく鑑定しない。相手の性格や運命を断定しない。
7. 個人情報（氏名・メール・生年月日・住所）を文章に書き写さない。「あなた」で呼びかける。
8. 文体: やさしく前向きで、です・ます調。占いは文化的・象徴的な読み物であり、確定的な予言ではないという姿勢を保つ。
9. スコア（1〜5）は今の巡りの目安。計算結果と矛盾しない範囲でつけ、basis に根拠の占術と値を書く。
10. ブレンドが1占術だけの場合、integration では同じ占術の中の要素同士（例：五行の偏りと大運）や自己申告との照合で一致点・ずれる点を書く。
11. 字数の目安（スキーマの description）を守る。print_* と *_print は A4 1枚に収めるための短縮版なので特に厳守。情報を増やすのではなく、文章を濃くする。

# 心理学レンズ（4テーマと回答は、この4層で書く）
① finding（占術の所見）: calc に根拠を持つ所見。カード名・星・数などの根拠の値を文中に入れる。
② concept＋lens（心理学のレンズ）: 所見を、下の許可リストにある名前のある心理学概念1つに翻訳し、1〜2文で解説する。concept には許可リストの正式名をそのまま書く。内容に合う概念だけを選び、無理に詰め込まない。4テーマで同じ概念をくり返さない。
③ why（なぜそう言えるか＝啓蒙の核）: 占いを外しても成り立つ心の機序を短く説明する（例：「小さな達成を記録すると、次も行動できるという見通しが育つため」）。
④ step（具体的な一歩）: 小さく、やったかどうか本人が確かめられる行動（回数・時間・場面が入るとよい）。
- 性格の自己申告（profile）との照合は継続する。integration.self_report_link では、一致点とギャップを否定せず両面として描き、integration.concepts の概念と結びつける。
- integration.concepts はテーマとは別に1〜2個まで。synthesis はそれらに触れて総評をまとめる。当たっていると感じる時の注意として「バーナム効果」「確証バイアス」を使うのは歓迎。

# 心理学の用語の使い方（禁止事項）
- 概念名と、許可リストにある提唱者名は使ってよい。実在しない論文タイトル・著者・年・数値を作らない。「研究によると68%が…」「○割の人が…」のような数値的主張、論文・調査の引用風の書き方をしない（「心理学では〜と考えられています」の水準に留める）。
- 用語は啓蒙のための教育的な使用に限る。障害・病名・診断めいた言い方（「あなたは回避型愛着障害」等）や、タイプの断定（「あなたは〇〇型です」）をしない。「傾向」「スタイル」の水準で書く。
- 「占いはきっかけ、心理学は根拠」という二層構造の説明は、鑑定書に固定文として1回だけ印字されるので、生成する文章には書かない（「フレーム」という語も使わない）。

# 実用的な助言（AMENDMENT_09 §B。最重要）
- 入力の `person` に本人の言葉がまとまっています: question（占ってほしいこと）、worries（悩み・状況の自由記入）、self_desc（自分の性格・最近の様子）、about_me、concern_theme（いちばん気になるテーマ）、性格のタップ回答。
- `person.gender` は本人の性別（「男性」「女性」、または空）。男性・女性の場合は本人の属性の一つとして自然に扱い、性別による役割や向き不向きを決めつけない。空（その他・無回答）の場合は性別に触れず、性別に依存しない読み方にする（性別を推測しない）。大運の順逆は計算側で決まっているので、calc の値をそのまま使う。
- 「占ってほしいことへの回答（answer）」と各テーマの「④一歩（step）」は、本人の悩み・自由記入・性格回答の**具体的な言葉を必ず引き受けて**書く。悩みをなぞる言い換えではなく、本人の状況に置いた助言にする（例：worries に「後輩が心配で転職に踏み出せない」とあれば、後輩への引き継ぎメモを週1枚書く、のように状況の中の行動にする）。
- 助言は実行可能な粒度まで落とす: いつ／どのくらいの頻度で／誰に／何と言うか、のいずれかを必ず含める。「前向きに」「自分を信じて」「大切にしましょう」のような精神論で終わらせない。
- answer.finding・answer.step には、question / worries に出てくる本人の言葉（固有の事物・状況を表す語）を、そのままの表記で最低1つ入れる。
- 自由記入（worries / self_desc / about_me）が空の場合は、concern_theme と性格回答から焦点を作り、focus_note にその旨を正直に書く。入力が薄い分、断定を弱める。自由記入がある場合 focus_note は空文字でよい。
- 投資の断定的な指示、医療的な判断（薬・治療をやめる等）は書かない。健康の悩みには医療機関への相談を勧める。
- 実用的な助言・行動提案・励ましは、1ページ目（answer・各テーマの step・advice）だけが担当する。2ページ目の予言詩には持ち込まない（AMENDMENT_16）。

# タロット（ケルティッククロス。AMENDMENT_09 §C）
- タロットがブレンドにある場合、calc.results.tarot はケルティッククロス10枚（spread の position: present 現状／challenge 課題（交差）／foundation 土台／past 過去／potential 目標・可能性／near_future 近未来／self 自分の立場／environment 周囲と環境／hopes_fears 願望と恐れ／outcome 結論）。占う対象は calc.results.tarot.target.label。
- tarot_cross に10件すべて（spread と同じ順・同じ position）を書く。各 note はその位置の意味とカードを本人の悩み・状況に結びつけた一言にする（カード名の列挙で終わらせない）。タロットが無いブレンドでは tarot_cross は空配列。
- system_readings の tarot では、占う対象と、要所（1 現状・2 課題・10 結論）のカードを使って読む。

"""

POEM_STYLE_GUIDE = """# 予言詩（poem。2ページ目。BRIEF §4／AMENDMENT_16）
- 詩の役割: 「天使の自動筆記」がその人のために書き留めた、近い未来についての**予言詩**。抽象的・文学的・意味深に、象徴と暗示で未来を告げる。助言のエッセイでも、今の状況の説明文でもない。読み手が「何をすべきか」ではなく「これから何かが訪れる」気配を受け取る詩にする。
- 形: 四行連を基本に4〜7連（stanzas の1要素＝1連。連の中の行は改行 \\n で区切る）。全体で600〜900字（改行を除く。厳守）、合計32行以内、1行は12〜34字。予言めいたタイトルを付ける（16字以内）。
- 時の流れ: 連ごとに、月の満ち欠け・季節・時刻・序数（「三つ目の新月」「四度目の雨」「冬の入口」）のような時の目印を置き、これから起こることを順に暗示する。暦の日付や期限は断定しない。最後の連は、予言が成就する情景（結論の暗示）と余韻で閉じる。
- 中心の象徴: 入力の poem_theme（seed テーマ）を詩の中心のイメージにする。
- モチーフ（最重要）: 本人の入力（person）と占術結果（calc）から2〜5個を選び、**言葉そのままではなく象徴に置き換えて**織り込む。
  - 例（形の例。題材は毎回その人から作る）: 悩みにある「後輩」→「軒下の若い燕」／「資格の勉強」→「まだ読まれぬ頁」／タロットの結論のカップの3 →「三つの杯」／五行で水が多い →「満ちてくる潮」／大運の切り替わり →「渡し舟の交代」。
  - 本人の言葉を引用しない（12字以上そのまま写すと不合格）。固有の事物は象徴に変え、本人だけが「これは私のことだ」と気づける距離に置く。名前を差し替えても成立する汎用の詩は不合格。
  - poem.motifs に、使ったモチーフを {source, origin, symbol} で申告する。source は入力の poem_motif_sources にあるキー（input.〜）か calc.<占術ID>（必要なら calc.tarot.spread[9] のように細かく）、origin はその出どころにある元の語・値をそのままの表記で、symbol は詩の本文に同じ表記で出てくる象徴の語。2つ以上、うち本人の入力由来を1つ以上（本人の入力が空なら calc 由来だけでよい）。
- 不吉さの扱い: 予言らしい翳り（欠ける月、沈む鐘、灰色の鳥、閉じかけた扉、凍る川）や曖昧さは文学表現として歓迎する。ただし死・事故・病気・災害・破産・離婚・失業などを、本人に起きる出来事として**断定しない**（「死ぬ」「事故に遭う」「病に倒れる」「破産する」等の直接表現は不合格）。翳りは象徴に留め、その先にほどける兆し・ひらく兆しも同じ象徴の言葉で暗示する。
- 禁止（1つでもあれば不合格・出し直し。助言・励ましは1ページ目だけの役割）:
  - 命令・勧告・勧誘（「〜しなさい」「〜すべき」「〜しよう」「〜しましょう」「〜してみて」「〜してください」「〜すればいい」）。託宣調の命令（「〜せよ」「気をつけよ」）も不可
  - 教訓・まとめ（「大切なのは〜」「忘れずに」「心がけ」）、実践ステップや行動提案（回数・時間つきの行動、「まずは〜」）
  - 読者への直接の励まし・許可・祈り（「あなたなら大丈夫」「急がなくていい」「〜ますように」）
- 文末は叙述・予兆の形にする（「〜だろう」「〜が鳴る」「〜を指す」「〜が訪れる」）。「あなた」は描写の主語として使ってよいが、働きかけ（〜して／〜していい／〜しないで）には使わない。
- 占術の結果は運命の断定ではなく象徴として扱う。数値の主張・捏造引用・診断的表現は詩でも禁止。名前・個人情報（氏名・生年月日・地名）は書かない。
- 形の見本（このまま使わない・言い回しをまねない。調子だけの参考）:
  三つ目の新月が　北の窓を叩くころ
  錆びた羅針は　眠りの中で向きを変える
  軒下の若い燕は　まだ巣の温もりを数え
  外套の裾に　知らない港の潮が染みてゆく
"""

CONCEPTS_HEADER = "# 使ってよい心理学概念（許可リスト。名称・由来・定義はこの範囲で使う）\n"

SYSTEM_PROMPT = SYSTEM_PROMPT_BASE + "\n" + POEM_STYLE_GUIDE + "\n" + CONCEPTS_HEADER + psych.prompt_table() + "\n"

# 予言詩だけを単独で生成するときの system prompt（MCP サーバーの prophecy_poem 等。build_poem_prompt を参照）
POEM_SYSTEM_PROMPT = """あなたは「天使の自動筆記（ラブリーゴーストライター）」の筆記者です。依頼者のために、近い未来を象徴と暗示で告げる予言詩を1篇だけ書きます。
入力として、ハーネスが検証済みの占術の計算結果（calc）、seed から決まった詩のテーマ（poem_theme）、本人の入力（person）が渡されます。
計算値は calc に書かれたものだけを使い、自分で計算・推測しない。占いは文化的・象徴的な読み物（エンターテインメント）であり、確定的な予言ではないという姿勢を、断定を避けた暗示の書き方で保つ。

""" + POEM_STYLE_GUIDE


def poem_motif_sources(job: dict, calc: dict) -> dict:
    """予言詩のモチーフの出どころ一覧（プロンプトに渡し、psych.check_poem_motifs が同じキーで実在を確かめる）."""
    return {**{f"input.{k}": v for k, v in psych.input_sources(job).items()},
            **{f"calc.{s}": catalog.CATALOG[s]["name"] for s in (calc.get("results") or {})}}


def poem_payload(job: dict, calc: dict) -> dict:
    """予言詩のコンテキスト（seed テーマ × 占術結果 × 本人の入力）。build_prompt と build_poem_prompt で共通."""
    pr = job.get("profile", {}) or {}
    return {"poem_theme": (calc.get("poem") or {}).get("theme"),
            "poem_motif_sources": poem_motif_sources(job, calc),
            "person": {**psych.input_texts(job), "concern_theme": pr.get("concern_theme", ""),
                       "personality_answers": {k: pr[k] for k in ("decision", "money", "stress", "love") if pr.get(k)}},
            "calc": calc.get("results") or {}}


def poem_schema() -> dict:
    """予言詩の出力スキーマ（reading.schema.json の properties.poem をそのまま使う）."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["properties"]["poem"]


def build_poem_prompt(job: dict, calc: dict) -> tuple[str, str]:
    """予言詩だけを生成するための (system_prompt, user_prompt)。出力は poem_schema() の JSON.
    検査は psych.check_poem(poem, job, calc)（hard があれば1回だけ出し直し、残れば不採用）。"""
    user = ("以下の入力から、予言詩を1篇、スキーマどおりの JSON（title / stanzas / motifs）で書いてください。\n\n```json\n"
            + json.dumps(poem_payload(job, calc), ensure_ascii=False, indent=1) + "\n```")
    return POEM_SYSTEM_PROMPT, user


def claude_exe() -> str:
    exe = settings()["claude"].get("exe", "auto")
    if exe and exe != "auto":
        return exe
    native = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    if native.exists():
        return str(native)
    found = shutil.which("claude")
    if not found:
        raise RuntimeError("claude CLI が見つかりません")
    return found


def build_prompt(job: dict, calc: dict, analysis: dict | None) -> str:
    roles = [{"system": s, "name": catalog.CATALOG[s]["name"], "default_role": catalog.CATALOG[s]["role"],
              "tier": catalog.CATALOG[s]["tier"]} for s in job["systems"]]
    pr = job.get("profile", {}) or {}
    person = {**psych.input_texts(job), "concern_theme": pr.get("concern_theme", ""),
              "free_text_given": psych.has_free_text(job),
              "gender": {"male": "男性", "female": "女性"}.get(job.get("gender") or "", ""),  # AMENDMENT_15
              "personality_answers": {k: pr[k] for k in ("decision", "money", "stress", "love") if pr.get(k)},
              "feature_words_from_input": psych.feature_words(job, ("question", "worries", "self_desc", "about_me"))[:12]}
    payload = {
        "blend": {"label": catalog.blend_label(job["systems"]), "systems": roles},
        "question_raw": job.get("question", ""),
        "person": person,
        "poem_theme": (calc.get("poem") or {}).get("theme"),
        "poem_motif_sources": poem_motif_sources(job, calc),
        "profile": pr,
        "intake_notes": job.get("intake_notes", []),
        "period": job.get("profile", {}).get("period") or "今年",
        "calc": calc["results"],
        "calc_as_of": calc["as_of"],
        "analysis": analysis,
    }
    return ("以下の入力から、スキーマどおりの鑑定データを作成してください。\n\n```json\n"
            + json.dumps(payload, ensure_ascii=False, indent=1) + "\n```")


def generate(job: dict, calc: dict, analysis: dict | None, log) -> dict:
    cfg = settings()["claude"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    argv = [claude_exe(), "-p", "--model", cfg["model"], "--effort", cfg["effort"], "--output-format", "json",
            "--json-schema", json.dumps(schema, ensure_ascii=False), "--tools", "", "--no-session-persistence",
            "--system-prompt", SYSTEM_PROMPT]
    base_prompt = build_prompt(job, calc, analysis)
    prompt = base_prompt
    last_err = None
    fallback = None  # 接地検査（AMENDMENT_09）だけが不合格だった出力。再生成でも駄目ならこれを理由つきで採用する
    cost_total = 0.0
    for attempt in (1, 2):
        log("reading", "claude_start", model=cfg["model"], effort=cfg["effort"], attempt=attempt)
        out, err = _call_claude(argv, prompt, cfg)
        try:
            d = json.loads(out)
            if d.get("is_error") or "structured_output" not in d:
                raise ValueError(f"claude error: {d.get('subtype')} {str(d.get('result'))[:300]}")
            reading = d["structured_output"]
            jsonschema.validate(reading, schema)
            _check_consistency(reading, job)
            style = psych.check_style(reading)
            lit = psych.check_poem_literary(reading.get("poem"), job)  # AMENDMENT_16 助言調＋BRIEF §4 災厄の断定（p1 の検査とは別）
            if style:
                raise StyleError(style + lit)
            usage = d.get("modelUsage", {})
            cost_total += d.get("total_cost_usd", 0) or 0
            g = psych.check_grounding(reading, job, calc)
            log("reading", "claude_done", models=list(usage.keys()), cost_usd=round(d.get("total_cost_usd", 0), 4),
                duration_ms=d.get("duration_ms"), concepts=concepts_used(reading), grounding_errors=g["errors"],
                poem_chars=psych.poem_chars(reading.get("poem") or {}), poem_motifs=g["poem"]["valid"], poem_advice=lit)
            reading["_meta"] = {"model": list(usage.keys()), "effort": cfg["effort"], "cost_usd": round(cost_total, 4),
                                "style": "psych-lens-v2-practical+prophecy-poem", "attempts": attempt, "grounding": g, "poem_literary": lit}
            if lit:
                # 助言調の詩は fallback にもしない（描画しない）。1回目なら理由を添えて出し直し、2回目なら失敗
                raise PoemAdviceError(lit, g["errors"])
            if g["errors"] and attempt == 1:
                fallback = reading
                raise GroundingError(g["errors"])
            if g["errors"]:
                reading["_meta"]["grounding_note"] = "再生成後も接地検査が不合格のため、理由を記録して描画（AMENDMENT_09 §B）"
                log("reading", "grounding_accepted_with_note", errors=g["errors"])
            return reading
        except PoemAdviceError as e:
            last_err = e
            log("reading", "poem_advice_retry" if attempt == 1 else "poem_advice_rejected", attempt=attempt, reasons=e.errors)
            if attempt == 2 and fallback is None:
                raise  # AMENDMENT_16: 再生成でも助言調 → 描画せず失敗（pipeline が qa.md に理由を書く）
            prompt = (base_prompt + "\n\n# 前回の出力は不合格でした。予言詩（poem）に助言・教訓調の表現、または断定的な災厄の宣告があります（AMENDMENT_16／BRIEF §4）。"
                      "詩は助言のエッセイではなく、象徴と暗示で未来を告げる予言詩として書き直してください。"
                      "命令・勧告・教訓・行動提案・読者への励ましを含めず、不吉さは象徴に留め、余韻で閉じること。該当箇所と、その他の直す点\n"
                      + "\n".join(f"- {x}" for x in e.errors + e.other))
        except GroundingError as e:
            last_err = e
            log("reading", "grounding_retry", attempt=attempt, errors=e.errors)
            prompt = (base_prompt + "\n\n# 前回の出力は、本人の言葉への接地・助言の具体性・予言詩のモチーフと形の検査で不合格でした。次の点を直して、全体を出し直してください\n"
                      + "\n".join(f"- {x}" for x in e.errors))
        except (json.JSONDecodeError, ValueError, jsonschema.ValidationError) as e:
            last_err = e
            log("reading", "claude_invalid", attempt=attempt, error=str(e)[:500],
                stderr=err[-300:])
            # 2回目は不合格の理由を添えて出し直してもらう（同じ失敗をくり返さないため）
            prompt = (base_prompt + "\n\n# 前回の出力は検証で不合格でした。次の点を直して、全体を出し直してください\n"
                      + "\n".join(f"- {x}" for x in (e.errors if isinstance(e, StyleError) else [str(e)[:400]])))
    if fallback is not None:
        # 再生成でも合格しなかった（または再生成が別の理由で失敗した）。AMENDMENT_09 §B: 理由を qa.md に記録して描画する
        fallback["_meta"]["grounding_note"] = "再生成後も接地検査が不合格のため、1回目の出力を理由つきで採用"
        fallback["_meta"]["cost_usd"] = round(cost_total, 4)
        log("reading", "grounding_accepted_with_note", errors=fallback["_meta"]["grounding"]["errors"])
        return fallback
    raise RuntimeError(f"Claude の鑑定データが検証に通りませんでした: {last_err}")


def _call_claude(argv: list[str], prompt: str, cfg: dict) -> tuple[str, str]:
    """Claude CLI を1回呼び、(stdout, stderr) を返す（テストではここを差し替える）."""
    proc = subprocess.run(argv, input=prompt.encode("utf-8"), capture_output=True, timeout=cfg.get("timeout_sec", 420),
                          cwd=str(ROOT))
    return proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


class PoemAdviceError(Exception):
    """AMENDMENT_16＋BRIEF §4: 予言詩が助言調、または断定的な災厄の宣告。再生成1回の後も残れば恒久失敗（描画しない）。ValueError ではない（接地の fallback に流さない）."""

    def __init__(self, errors: list[str], other: list[str] | None = None):
        super().__init__("予言詩が助言調・災厄の断定: " + " / ".join(errors))
        self.errors = errors
        self.other = other or []


class GroundingError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("接地検査不合格: " + " / ".join(errors))
        self.errors = errors


class StyleError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("スタイル検査不合格: " + " / ".join(errors))
        self.errors = errors


def concepts_used(reading: dict) -> dict:
    return {**{k: v["concept"] for k, v in reading["themes"].items()}, "answer": reading["answer"]["concept"],
            "integration": reading["integration"]["concepts"]}


def _check_consistency(reading: dict, job: dict) -> None:
    got = [r["system"] for r in reading["system_readings"]]
    if sorted(got) != sorted(job["systems"]):
        raise ValueError(f"system_readings の占術が一致しません: {got} != {job['systems']}")
    if sorted(r["system"] for r in reading["blend_roles"]) != sorted(job["systems"]):
        raise ValueError("blend_roles の占術が一致しません")
    reading["system_readings"].sort(key=lambda r: job["systems"].index(r["system"]))
    reading["blend_roles"].sort(key=lambda r: job["systems"].index(r["system"]))
    # AMENDMENT_09 §C: タロットがあればケルティッククロス10位置すべての読みが必要（無ければ空）
    from .calc.tarot import SPREAD
    tc = reading.get("tarot_cross") or []
    if "tarot" in job["systems"]:
        want = [k for k, _ in SPREAD]
        got_pos = [c["position"] for c in tc]
        if sorted(got_pos) != sorted(want):
            raise ValueError(f"tarot_cross はケルティッククロスの10位置すべて（{', '.join(want)}）が必要です: {got_pos}")
        tc.sort(key=lambda c: want.index(c["position"]))
    elif tc:
        reading["tarot_cross"] = []
    p = reading.get("poem") or {}
    if not (p.get("title") or "").strip() or psych.poem_chars(p) < 200:
        raise ValueError("poem.title / poem.stanzas がありません（2ページ目の予言詩）")


def stars(n: int) -> str:
    return "●" * n + "○" * (5 - n)


def _lens_md(o: dict) -> list[str]:
    return [f"- **占術の所見**: {o['finding']}",
            f"- **心理学のレンズ — {o['concept']}**: {o['lens']}",
            f"- **なぜそう言えるか**: {o['why']}",
            f"- **小さな一歩**: {o['step']}"]


def to_markdown(job: dict, calc: dict, reading: dict, brand: dict) -> str:
    L = [f"# {brand['title']}｜{brand['shop_name']}", "",
         f"**{reading['headline']}**", "",
         f"- お名前: {job['display_name']} さん",
         f"- ブレンド: {calc['blend']['label']}",
         f"- 発行日: {calc['as_of']}", "",
         "## ブレンド表記（各占術の担当）", ""]
    for r in reading["blend_roles"]:
        L.append(f"- **{catalog.CATALOG[r['system']]['name']}**: {r['role']}")
    L += ["", f"> {reading['integration']['flavor']}", "", "## 各占術の結果", ""]
    for sr in reading["system_readings"]:
        L.append(f"### {catalog.CATALOG[sr['system']]['name']}")
        L += [f"- {f}" for f in sr["key_facts"]]
        L += ["", sr["reading"], ""]
    if "tarot" in calc["results"] and reading.get("tarot_cross"):
        tr = calc["results"]["tarot"]
        notes = {c["position"]: c["note"] for c in reading["tarot_cross"]}
        L += ["## タロット — ケルティッククロス（10枚）", "",
              f"占う対象: {(tr.get('target') or {}).get('label', '全体運')}（シード {tr['seed']}）", "",
              "| 位置 | カード | 正逆 | 読み |", "|---|---|---|---|"]
        L += [f"| {c['position_label']} | {c['name_ja']} | {c['orientation']} | {notes.get(c['position'], '')} |" for c in tr["spread"]]
        L += [""]
    L += ["## 4つのテーマ", ""]
    for key, label in catalog.THEMES:
        t = reading["themes"][key]
        L += [f"### {label}  {stars(t['score'])} ({t['score']}/5)", ""] + _lens_md(t) + ["", f"<sub>根拠: {t['basis']}</sub>", ""]
    ig = reading["integration"]
    L += ["## 統合解釈（ブレンドの味わい）", "", "**一致する点**", ""] + [f"- {a}" for a in ig["agreements"]]
    L += ["", "**ずれる点**", ""] + [f"- {d}" for d in ig["differences"]]
    L += ["", f"**あなたの自己申告との照合**（{'・'.join(ig['concepts'])}）" if ig["concepts"] else "**あなたの自己申告との照合**",
          "", ig["self_report_link"], "", ig["synthesis"], ""]
    L += ["## 占ってほしいことへの回答", "", f"**ご質問**: {reading['adopted_question']}", ""]
    if reading.get("focus_note"):
        L += [f"> {reading['focus_note']}", ""]
    L += _lens_md(reading["answer"]) + [""]
    L += ["## 気をつけたいこと", "", reading["advice"]["caution"], ""]
    poem = reading.get("poem") or {}
    stz = psych.poem_stanzas(poem)
    if stz:
        theme = (calc.get("poem") or {}).get("theme", "")
        L += [f"## あなたへの予言詩 —『{poem['title']}』（テーマ：{theme}）", ""]
        for lines in stz:  # Markdown の行内改行は行末の2スペース
            L += ["  \n".join(lines), ""]
    notes = job.get("intake_notes") or []
    if notes:
        L += ["## 受付時の調整", ""] + [f"- {n}" for n in notes] + [""]
    L += ["---", "", psych.FRAME_NOTE,
          "占いは文化的・象徴的な読み物（エンターテインメント）であり、医療・法律・投資等の専門的助言や確定的な予言ではありません。"]
    return "\n".join(L) + "\n"
