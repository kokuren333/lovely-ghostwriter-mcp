"""Anthropic API で JSON を生成する（ANTHROPIC_API_KEY があるときだけ使う）.

環境変数:
  ANTHROPIC_API_KEY  必須（無ければ各ツールはホスト LLM 用のプロンプトを返すモードになる）
  LGW_MODEL          既定 claude-opus-5-5
  LGW_EFFORT         既定 medium（low / medium / high / xhigh / max）
  LGW_FALLBACKS      既定 1。拒否（refusal）時にサーバー側のフォールバックモデルで再実行する（0 で無効）

構造化出力（output_config.format=json_schema）で頼み、使えない構成なら（400）プロンプト指示だけで JSON を返させる。
戻り値は必ず呼び出し側で jsonschema とアプリの検査器にかける（ここでは JSON として読めることだけを保証する）。
"""
from __future__ import annotations

import json
import os
import re


class GenerationError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.S)
    if m:
        return json.loads(m.group(1))
    i, j = text.find("{"), text.rfind("}")
    if i >= 0 and j > i:
        return json.loads(text[i:j + 1])
    raise GenerationError("応答から JSON を取り出せませんでした")


def generate_json(system: str, user: str, schema: dict, max_tokens: int = 32000) -> tuple[dict, dict]:
    import anthropic

    client = anthropic.Anthropic()
    model = os.environ.get("LGW_MODEL", "claude-opus-5-5")
    effort = os.environ.get("LGW_EFFORT", "medium")
    use_fallbacks = os.environ.get("LGW_FALLBACKS", "1") != "0"
    plain_user = user + "\n\n# 出力形式\n次の JSON Schema に従う JSON オブジェクトだけを出力してください。\n```json\n" \
        + json.dumps(schema, ensure_ascii=False) + "\n```"
    configs = []
    if use_fallbacks:
        configs.append({"fallbacks": True, "format": True})
    configs += [{"fallbacks": False, "format": True}, {"fallbacks": False, "format": False}]
    last_err: Exception | None = None
    for cfg in configs:
        output_config: dict = {"effort": effort}
        if cfg["format"]:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        kwargs = dict(model=model, max_tokens=max_tokens, system=system, output_config=output_config,
                      messages=[{"role": "user", "content": user if cfg["format"] else plain_user}])
        try:
            if cfg["fallbacks"]:
                with client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"],
                                                 extra_body={"fallbacks": "default"}, **kwargs) as stream:
                    msg = stream.get_final_message()
            else:
                with client.messages.stream(**kwargs) as stream:
                    msg = stream.get_final_message()
        except anthropic.BadRequestError as e:  # 構成（フォールバック・構造化出力のスキーマ制約）が使えない → 次の構成へ
            last_err = e
            continue
        except anthropic.AuthenticationError as e:
            raise GenerationError("ANTHROPIC_API_KEY が無効です") from e
        except anthropic.RateLimitError as e:
            raise GenerationError("レート制限に達しました。時間をおいて再実行してください") from e
        except anthropic.APIConnectionError as e:
            raise GenerationError("Anthropic API に接続できません（ネットワークを確認）") from e
        if msg.stop_reason == "refusal":
            raise GenerationError("モデルが生成を辞退しました（refusal）。入力内容を見直してください")
        if msg.stop_reason == "max_tokens":
            raise GenerationError("出力が max_tokens で途切れました")
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        try:
            data = _extract_json(text)
        except (json.JSONDecodeError, GenerationError) as e:
            last_err = e
            continue
        usage = getattr(msg, "usage", None)
        meta = {"model": getattr(msg, "model", model), "effort": effort, "structured_output": cfg["format"],
                "input_tokens": getattr(usage, "input_tokens", None), "output_tokens": getattr(usage, "output_tokens", None)}
        return data, meta
    raise GenerationError(f"Anthropic API での生成に失敗しました: {str(last_err)[:400]}")
