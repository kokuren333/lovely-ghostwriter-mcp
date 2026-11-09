# lovely-ghostwriter-mcp — 天使の自動筆記（ラブリーゴーストライター）MCP サーバー

> **本プロジェクトは HUNTER×HUNTER の非公式ファン作品（パロディ）です。原作・公式とは関係ありません。**
> 原作: HUNTER×HUNTER ©冨樫義博／集英社
>
> 占いはエンターテインメントです。医療・法律・投資等の専門的な助言や、確定的な予言ではありません。重要な判断は専門家にご相談ください。

占術を 1〜3 種「カクテル」のようにブレンドして鑑定する **MCP サーバー**（Python・stdio トランスポート）です。
Claude Desktop / Claude Code などの MCP ホストから、次のことができます。

- 占術カタログとハウスブレンドの参照
- **決定論的な占術計算**（四柱推命・タロット（ケルティッククロス）・九星気学・数秘術・姓名判断・西洋占星術・インド占星術・宿曜・マヤ暦ほか。外部 API なし、値の捏造なし）
- 鑑定文の作成（仕事・恋愛・才能・金運 ＋ 占ってほしいこと 1 件。心理学レンズつき）
- 2 ページ目の**予言詩**（自動筆記の詩。象徴と暗示で近い未来を綴る。助言・命令・教訓・励ましは書かない）
- **証明書の描画**: 印刷用 PDF（A4・白黒・1 ページ）、デジタル版 PDF（A4・カラー・2 ページ）＋各ページの PNG 2 枚

鑑定文と予言詩は二段構えです。`ANTHROPIC_API_KEY` が設定されていれば Anthropic API（既定 `claude-opus-5-5`）で生成して検査器にかけ、
設定されていなければ **ホスト LLM（あなたが使っている Claude など）向けの構造化プロンプト＋計算結果** を返します。

## インストール

Python 3.10 以上。

```bash
git clone https://github.com/kokuren333/lovely-ghostwriter-mcp.git
cd lovely-ghostwriter-mcp
python -m venv .venv
# Windows: .venv\Scripts\activate   macOS/Linux: source .venv/bin/activate
pip install -e .                 # 基本
pip install -e ".[anthropic]"    # API で鑑定文・予言詩を生成したい場合
pip install -e ".[dev]"          # テスト（pytest）
```

### ブラウザ（証明書の描画に必要）

PDF/PNG の描画には Chromium 系ブラウザを Playwright 経由で使います。次の順に試します。

1. Microsoft Edge（Windows には標準で入っています。追加ダウンロード不要）
2. Google Chrome
3. Playwright 同梱の Chromium（`python -m playwright install chromium` で入ります）

環境変数 `LGW_BROWSER_CHANNEL`（`msedge` / `chrome` など）で最初に試すチャネルを指定できます。
どれも起動できない場合、`render_certificate` は理由つきのエラーを返します（サーバーは落ちません）。

## MCP ホストの設定

### Claude Desktop（`claude_desktop_config.json`）

```json
{
  "mcpServers": {
    "lovely-ghostwriter": {
      "command": "C:\\path\\to\\lovely-ghostwriter-mcp\\.venv\\Scripts\\lovely-ghostwriter-mcp.exe",
      "env": {
        "LGW_OUTPUT_DIR": "C:\\Users\\you\\Documents\\lgw-output"
      }
    }
  }
}
```

macOS/Linux では `command` を `/path/to/lovely-ghostwriter-mcp/.venv/bin/lovely-ghostwriter-mcp` にします。
API で生成させたい場合は `env` に `"ANTHROPIC_API_KEY": "..."` を足します（キーはリポジトリに書かないこと）。

### Claude Code

```bash
claude mcp add lovely-ghostwriter -- /path/to/lovely-ghostwriter-mcp/.venv/bin/lovely-ghostwriter-mcp
# Windows の例
claude mcp add lovely-ghostwriter -- C:\path\to\lovely-ghostwriter-mcp\.venv\Scripts\lovely-ghostwriter-mcp.exe
```

`python -m lovely_ghostwriter_mcp` でも起動できます（stdio）。

## ツール

すべてのツールは同じ `person`（入力）を受け取ります。サーバーは状態を持たず、同じ `person` からは毎回同じ計算結果（タロットのシードを含む）が出ます。

| フィールド | 説明 |
|---|---|
| `preset` / `systems` | ハウスブレンド ID（`classic` `love` `work` `flow` `name` `moon` `stars` `single`）か、占術 ID 1〜3 個（例 `["bazi","tarot"]`） |
| `display_name` | 証明書に印字する呼び名（既定「ゲスト」） |
| `name_kanji` / `name_kana` | 漢字の姓名（姓と名の間にスペース。姓名判断）／ふりがな（数秘術・カバラ数秘） |
| `birth_date` / `birth_time` / `birth_place` | `YYYY-MM-DD` ／ `HH:MM`（不明なら省略）／都道府県（西洋占星術） |
| `gender` | `male` / `female` / `other`（四柱推命の大運の順逆。省略可） |
| `question` | 占ってほしいこと（1 件） |
| `worries` / `self_desc` / `about_me` / `concern_theme` / `personality` | 悩み・自己紹介・気になるテーマ・性格のタップ回答（任意。鑑定文と予言詩の素材） |
| `tarot_seed` / `as_of` | タロットのシード（任意）／鑑定日（既定は今日・JST） |

| ツール | 内容 |
|---|---|
| `list_systems` | 占術カタログ（実装 tier つき）、ハウスブレンド、鑑定の枠 |
| `calculate` | 決定論計算。`calc`（全結果）・`facts`（図表用の要点）・`calc_sha256` を返す。必要な入力が足りなければ理由を返す |
| `compose_reading` | 鑑定データ（`reading` JSON：4 テーマ＋回答＋統合解釈＋ケルティッククロスの読み＋予言詩）。`mode`: `auto`（既定）/ `prompt` / `api` |
| `prophecy_poem` | 予言詩だけを作る（`title` / `stanzas` / `motifs`）。同じく二段構え |
| `validate_reading` | 鑑定データの検査（スキーマ、占術の整合、心理学レンズの用語、予言詩の助言調・断定的な災厄表現など）。`errors` は描画を止めるもの、`warnings` は記録して採用してよいもの |
| `render_certificate` | `person` と `reading` から `print.pdf`・`digital.pdf`・`digital_p1.png`・`digital_p2.png` を出力し、QA 結果（ページ数・白黒・A4 など）を返す。出力先は `out_dir` → `LGW_OUTPUT_DIR` → `./lgw-output/<job_id>/` |

### API キーが無いときの流れ（ホスト LLM が書く）

1. `compose_reading`（または `prophecy_poem`）を呼ぶ → `system_prompt`・`user_prompt`・`output_schema`・`calc` が返る
2. ホスト LLM がそれに従って JSON を書く（計算値は `calc` にあるものだけを使う）
3. `validate_reading` で検査 → 直す
4. `render_certificate` で PDF/PNG を作る

### 環境変数

| 変数 | 既定 | 説明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | なし | あれば API で生成 |
| `LGW_MODEL` | `claude-opus-5-5` | 生成に使うモデル |
| `LGW_EFFORT` | `medium` | effort（`low`〜`max`） |
| `LGW_FALLBACKS` | `1` | モデルが生成を辞退（refusal）したときに、サーバー側のフォールバックモデルで再実行する（`0` で無効） |
| `LGW_OUTPUT_DIR` | `./lgw-output` | 証明書の出力先 |
| `LGW_BROWSER_CHANNEL` | `msedge` | 最初に試すブラウザ |
| `LGW_SHOP_NAME` / `LGW_TITLE` / `LGW_CONTACT` | 同梱設定 | 証明書の屋号・表題・フッターの連絡先表記の上書き |

## サンプル

`examples/sample_person.json` は**架空の人物**です。`examples/sample_reading.json` は描画確認用のダミー文面の鑑定データです。

## 開発

- 占術計算・テンプレート・デザイン素材・検査器は、親アプリ（天使の自動筆記）から `tools/sync_from_app.py` で
  `src/lovely_ghostwriter_mcp/_vendor/` に同期したものです（直接編集しないでください）。
  同期時に、メールアドレス・トークン・フォーム ID 様の文字列が混ざっていないかを検査します。
- テスト: `pytest -q`（stdio 経由で実際に MCP クライアントから呼ぶテストを含む。ブラウザが無い環境では描画テストを skip）

## English (short)

**lovely-ghostwriter-mcp** is an unofficial HUNTER×HUNTER fan-parody project (not affiliated with the original work or its rights holders; HUNTER×HUNTER ©Yoshihiro Togashi / Shueisha).
It is a stdio MCP server for an entertainment fortune-telling "blend" (1–3 divination systems): deterministic calculations (no external APIs, nothing fabricated),
a structured reading (work / love / talent / money + one question), a prophetic poem, and certificate rendering (A4 B/W print PDF, A4 2-page color PDF + 2 PNGs).
Readings and poems are generated via the Anthropic API when `ANTHROPIC_API_KEY` is set (default model `claude-opus-5-5`); otherwise the tools return a structured prompt, output schema and calculation results for the host LLM to write the JSON itself.
Install with `pip install -e .` (add `.[anthropic]` for API mode). Rendering needs a Chromium-based browser (Edge, Chrome, or `python -m playwright install chromium`).
Fortune-telling here is for entertainment only — not medical, legal or financial advice.

License: not specified
