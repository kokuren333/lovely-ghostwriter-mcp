"""軽量スモークテスト: ツール関数の直接呼び出し＋stdio の MCP クライアント経由の呼び出し.

API キーは使わない（compose_reading / prophecy_poem はプロンプトモードで確認）。
描画はブラウザ（Edge / Chrome / Playwright Chromium）が無ければ skip する。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from lovely_ghostwriter_mcp import core
from lovely_ghostwriter_mcp._vendor import fake_reading

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
PERSON = json.loads((EXAMPLES / "sample_person.json").read_text(encoding="utf-8"))  # 架空の人物


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_list_systems():
    s = core.list_systems()
    ids = {x["id"] for x in s["systems"]}
    assert {"bazi", "tarot", "numerology"} <= ids
    assert s["max_systems"] == 3
    assert {p["id"] for p in s["presets"]} >= {"classic", "love", "single"}


def test_calculate_deterministic():
    a = core.calculate(PERSON)
    b = core.calculate(PERSON)
    assert a["calc_sha256"] == b["calc_sha256"]
    assert a["calc"]["systems"] == ["tarot", "numerology", "bazi"]
    assert len(a["calc"]["results"]["tarot"]["spread"]) == 10
    assert "email" not in a["job"]


def test_calculate_missing_input():
    with pytest.raises(core.InputError):
        core.calculate({"systems": ["bazi"], "question": "x"})  # 生年月日なし


def test_compose_reading_prompt_mode():
    r = core.compose_reading(PERSON)
    assert r["mode"] == "prompt"
    assert "calc" in r and r["output_schema"]["type"] == "object"
    assert "poem" in r["output_schema"]["properties"]
    assert "```json" in r["user_prompt"]


def test_prophecy_poem_prompt_mode():
    r = core.prophecy_poem(PERSON)
    assert r["mode"] == "prompt"
    assert r["poem_theme"]
    assert r["output_schema"]["type"] == "object"
    assert "詩" in r["system_prompt"]


def _fake(person):
    job = core.build_job(person)
    return fake_reading.make(job), job


def test_validate_fake_reading_schema():
    rd, job = _fake(PERSON)
    v = core.validate_reading(rd, job)
    assert not [e for e in v["errors"] if e.startswith("スキーマ不一致")], v["errors"]


def test_render_certificate(tmp_path):
    rd, _ = _fake(PERSON)
    res = core.render_certificate(PERSON, rd, out_dir=str(tmp_path), strict=False)
    if not res["ok"] and res.get("stage") == "browser":
        pytest.skip(res["errors"][0])
    assert res["ok"], res
    f = res["files"]
    for p in [f["print_pdf"], f["digital_pdf"], *f["digital_pngs"]]:
        assert Path(p).exists() and Path(p).stat().st_size > 1000
    assert res["qa"]["print"]["pages"] == 1
    assert res["qa"]["digital"]["pages"] == 2


# ---------------------------------------------------------------- stdio (real MCP client)

def _structured(result):
    sc = getattr(result, "structured_content", None)
    if sc is None:
        sc = getattr(result, "structuredContent", None)
    if sc is None:
        sc = json.loads(result.content[0].text)
    if isinstance(sc, dict) and set(sc) == {"result"}:
        sc = sc["result"]
    return sc


async def _stdio_session():
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        from mcp import Client, StdioServerParameters  # mcp 2.x
    except ImportError:
        Client = None
        from mcp import StdioServerParameters
    params = StdioServerParameters(command=sys.executable, args=["-m", "lovely_ghostwriter_mcp"], env=env)
    calls = {}
    if Client is not None:
        async with Client(params) as c:
            tools = await c.list_tools()
            calls["tools"] = [t.name for t in tools.tools]
            calls["list_systems"] = _structured(await c.call_tool("list_systems", {}))
            calls["calculate"] = _structured(await c.call_tool("calculate", {"person": PERSON}))
            calls["compose"] = _structured(await c.call_tool("compose_reading", {"person": PERSON, "mode": "prompt"}))
            calls["poem"] = _structured(await c.call_tool("prophecy_poem", {"person": PERSON}))
    else:  # mcp 1.x
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as c:
                await c.initialize()
                tools = await c.list_tools()
                calls["tools"] = [t.name for t in tools.tools]
                calls["list_systems"] = _structured(await c.call_tool("list_systems", {}))
                calls["calculate"] = _structured(await c.call_tool("calculate", {"person": PERSON}))
                calls["compose"] = _structured(await c.call_tool("compose_reading", {"person": PERSON, "mode": "prompt"}))
                calls["poem"] = _structured(await c.call_tool("prophecy_poem", {"person": PERSON}))
    return calls


def test_stdio_server():
    calls = asyncio.run(asyncio.wait_for(_stdio_session(), timeout=120))
    assert set(calls["tools"]) >= {"list_systems", "calculate", "compose_reading", "prophecy_poem",
                                   "render_certificate", "validate_reading"}
    assert calls["list_systems"]["max_systems"] == 3
    assert calls["calculate"]["calc_sha256"] == core.calculate(PERSON)["calc_sha256"]
    assert calls["compose"]["mode"] == "prompt"
    assert calls["poem"]["mode"] == "prompt"


def test_compose_reading_api_mode_mocked(monkeypatch):
    """API モードの流れ（生成→検査→返却）を、Anthropic を呼ばずに確認する."""
    from lovely_ghostwriter_mcp import llm
    rd, _ = _fake(PERSON)
    monkeypatch.setattr(core, "api_available", lambda: True)
    monkeypatch.setattr(llm, "generate_json", lambda system, user, schema, **kw: (rd, {"model": "mock"}))
    r = core.compose_reading(PERSON, mode="api")
    assert r["mode"] == "api"
    assert "reading" in r and r["reading"]["headline"]
