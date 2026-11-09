"""MCP サーバー（stdio）: 天使の自動筆記（ラブリーゴーストライター）の占術ブレンド鑑定.

tools: list_systems / calculate / compose_reading / prophecy_poem / validate_reading / render_certificate
"""
from __future__ import annotations

from typing import Any, Literal

import anyio
from pydantic import BaseModel, Field

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from . import __version__, core

INSTRUCTIONS = """天使の自動筆記（ラブリーゴーストライター）— 占術を1〜3種ブレンドする鑑定の MCP サーバー（HUNTER×HUNTER の非公式ファンパロディ・エンタメ用途）。
使い方の流れ: list_systems で占術とハウスブレンドを確認 → calculate で決定論計算 → compose_reading で鑑定文（仕事・恋愛・才能・金運＋占ってほしいこと1件）
→ 必要なら prophecy_poem で2ページ目の予言詩 → render_certificate で印刷用 PDF（A4白黒1ページ）とデジタル版 PDF（A4 2ページ）＋PNG 2枚。
ANTHROPIC_API_KEY が無い場合、compose_reading / prophecy_poem は「ホスト LLM 用のプロンプト＋計算結果」を返すので、あなた（ホスト LLM）が
output_schema どおりの JSON を書き、validate_reading で検査してから render_certificate に渡してください。計算値は calc にあるものだけを使い、捏造しないこと。"""

mcp = _Server("lovely-ghostwriter", instructions=INSTRUCTIONS)


class Person(BaseModel):
    """鑑定の入力（すべて架空・本人同意済みのデータで使うこと）。preset か systems のどちらかが必要."""
    preset: str | None = Field(None, description="ハウスブレンドID（classic / love / work / flow / name / moon / stars / single）")
    systems: list[str] | None = Field(None, description="占術ID 1〜3個（例: [\"bazi\", \"tarot\"]）。preset より優先")
    display_name: str | None = Field(None, description="証明書に印字する呼び名（既定: ゲスト）")
    name_kanji: str | None = Field(None, description="漢字の姓名（姓と名の間にスペース。姓名判断に必要）")
    name_kana: str | None = Field(None, description="ふりがな（数秘術・カバラ数秘に必要）")
    birth_date: str | None = Field(None, description="生年月日 YYYY-MM-DD")
    birth_time: str | None = Field(None, description="出生時刻 HH:MM（不明なら省略）")
    birth_place: str | None = Field(None, description="出生地の都道府県（西洋占星術に必要）")
    gender: str | None = Field(None, description="male / female / other（大運の順逆に使う。省略可）")
    question: str | None = Field(None, description="占ってほしいこと（1件）")
    worries: str | None = Field(None, description="悩み・状況の自由記入")
    self_desc: str | None = Field(None, description="自分の性格・最近の様子")
    about_me: str | None = Field(None, description="自己紹介（任意）")
    concern_theme: str | None = Field(None, description="いちばん気になるテーマ（仕事／恋愛／お金／人間関係／進路・転機／健康／その他）")
    personality: dict[str, str] | None = Field(None, description="性格のタップ回答（decision / money / stress / love などのキー）")
    tarot_seed: str | None = Field(None, description="タロットのシード（省略時は入力から決定的に作る）")
    as_of: str | None = Field(None, description="鑑定日 YYYY-MM-DD（省略時は今日・JST）")


def _p(person: Person | dict) -> dict:
    return person.model_dump(exclude_none=True) if isinstance(person, BaseModel) else dict(person or {})


def _err(e: Exception) -> dict:
    return {"ok": False, "error": str(e), "error_type": type(e).__name__}


async def _run(fn, *args) -> dict:
    """ブロッキング処理（Playwright の sync API・HTTP 呼び出し）はワーカースレッドで実行する."""
    try:
        return await anyio.to_thread.run_sync(lambda: fn(*args))
    except core.InputError as e:
        return _err(e)
    except Exception as e:  # ツールの失敗はエラー内容を返す（サーバーは落とさない）
        return _err(e)


@mcp.tool()
def list_systems() -> dict[str, Any]:
    """占術カタログ（実装 tier つき）とハウスブレンド（推奨の組み合わせ）、鑑定の枠（4テーマ＋占ってほしいこと1件）を返す。"""
    return core.list_systems()


@mcp.tool()
async def calculate(person: Person) -> dict[str, Any]:
    """決定論的な占術計算（外部 API なし）。ブレンド（1〜3種）と生年月日・時刻・出生地・氏名などから、命式・カード・星などの計算結果（calc）と図表用の要点（facts）を返す。値を捏造しない。"""
    return await _run(core.calculate, _p(person))


@mcp.tool()
async def compose_reading(person: Person, mode: Literal["auto", "prompt", "api"] = "auto") -> dict[str, Any]:
    """鑑定文（仕事・恋愛・才能・金運＋占ってほしいこと1件、心理学レンズつき、2ページ目の予言詩を含む）を作る。
    ANTHROPIC_API_KEY があれば Anthropic API で生成してスキーマとアプリの検査器で検証する（mode=auto/api）。
    無ければ（または mode=prompt）ホスト LLM 用の system/user プロンプト・出力スキーマ・計算結果を返す。"""
    return await _run(core.compose_reading, _p(person), mode)


@mcp.tool()
async def prophecy_poem(person: Person, mode: Literal["auto", "prompt", "api"] = "auto") -> dict[str, Any]:
    """2ページ目の予言詩（自動筆記の詩。抽象的・文学的・未来を暗示する数連の詩。助言・命令・教訓・励ましは書かない）を作る。
    compose_reading と同じ二段構え（API キーがあれば生成＋検査、無ければホスト LLM 用プロンプト）。結果は鑑定データの poem 欄に入れられる。"""
    return await _run(core.prophecy_poem, _p(person), mode)


@mcp.tool()
async def validate_reading(person: Person, reading: dict[str, Any]) -> dict[str, Any]:
    """鑑定データ（reading JSON）を検査する: スキーマ・占術の整合・心理学レンズのスタイル・予言詩の助言調チェック（接地は警告）。"""
    def run():
        job = core.build_job(_p(person))
        v = core.validate_reading(reading, job, core.compute(job))
        return {"ok": v["ok"], "errors": v["errors"], "warnings": v["warnings"]}
    return await _run(run)


@mcp.tool()
async def render_certificate(person: Person, reading: dict[str, Any], out_dir: str | None = None,
                             strict: bool = True) -> dict[str, Any]:
    """鑑定データ（reading JSON）から証明書を描画する: 印刷用 PDF（A4・白黒・1ページ）、デジタル版 PDF（A4・カラー・2ページ）、
    デジタル版の各ページの PNG 2枚。アプリ版と同じテンプレートとデザイン素材を使う。Chromium 系ブラウザ（Edge / Chrome /
    Playwright の Chromium）が必要。out_dir 省略時は LGW_OUTPUT_DIR か ./lgw-output/<job_id>/ に出力する。"""
    return await _run(core.render_certificate, _p(person), reading, out_dir, strict)


def main() -> None:
    mcp.run()  # stdio


if __name__ == "__main__":
    main()
