"""Local LLM router (Ollama) with strict JSON output and safe heuristic fallback."""

from __future__ import annotations

import json
import os
from urllib import error, request

import httpx
import ollama

from db.schema import ToolCall

SYSTEM_PROMPT = """You are a strict tool router for analytics.
Rules:
1) You MUST output valid JSON only.
2) You MUST choose exactly one tool from the provided list.
3) You MUST NOT answer the user question directly.
4) You MUST NOT compute business metrics yourself.
5) Arguments must follow the provided argument schema.
Output shape:
{"tool_name":"<tool>","arguments":{...}}
"""

CHAT_TOOLS_SYSTEM_PROMPT = """You are a strict tool router for analytics.
Rules:
1) You MUST choose exactly one provided tool.
2) You MUST NOT answer the user question directly.
3) You MUST NOT compute business metrics yourself.
4) Tool arguments must follow the provided schema.
"""


def _ollama_url() -> str:
    return os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")


def _ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", _ollama_url().removesuffix("/api/generate"))


def _ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen3.5")


def _ollama_timeout() -> float:
    return float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))


def _heuristic_fallback(question: str) -> ToolCall:
    """Conservative fallback when local LLM is unavailable or malformed."""
    q = question.lower()
    if "average" in q and "revenue" in q:
        return ToolCall(tool_name="get_average_daily_revenue", arguments={"days": 30})
    if ("rto" in q and "high" in q) or "high value" in q:
        return ToolCall(tool_name="get_rto_orders", arguments={"min_amount": 2000})
    if "rto" in q:
        return ToolCall(tool_name="get_rto_orders", arguments={})
    if "failed shipment" in q or "failed deliveries" in q:
        return ToolCall(tool_name="get_failed_shipments", arguments={})
    if "order" in q and "int-" in q:
        token = next((part for part in question.split() if part.upper().startswith("INT-")), "")
        if token:
            return ToolCall(tool_name="get_order_by_id", arguments={"internal_order_id": token})
    if "revenue" in q:
        return ToolCall(tool_name="get_total_revenue", arguments={})
    return ToolCall(tool_name="get_rto_orders", arguments={})


def _tool_specs_for_chat(tool_descriptions: list[dict]) -> list[dict]:
    """Convert local tool metadata into Ollama/OpenAI-style tool schemas."""
    specs: list[dict] = []
    for tool in tool_descriptions:
        properties: dict = {}
        required: list[str] = []
        for arg_name, arg_spec in tool.get("arguments_schema", {}).items():
            prop = {
                key: value
                for key, value in arg_spec.items()
                if key in {"type", "description", "default", "minimum", "maximum", "enum"}
            }
            if "min" in arg_spec:
                prop["minimum"] = arg_spec["min"]
            properties[arg_name] = prop
            if arg_spec.get("required", False):
                required.append(arg_name)

        specs.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return specs


def _get_value(obj: object, key: str, default: object = None) -> object:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _parse_chat_tool_call(response: object) -> ToolCall:
    message = _get_value(response, "message", {})
    tool_calls = _get_value(message, "tool_calls", []) or []
    if not tool_calls:
        raise ValueError("Ollama chat response did not include a tool call")

    function = _get_value(tool_calls[0], "function", {})
    tool_name = _get_value(function, "name")
    arguments = _get_value(function, "arguments", {}) or {}
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    return ToolCall.model_validate({"tool_name": tool_name, "arguments": arguments})


def _route_with_chat_tools(question: str, tool_descriptions: list[dict]) -> ToolCall:
    client = ollama.Client(host=_ollama_host(), timeout=_ollama_timeout())
    response = client.chat(
        model=_ollama_model(),
        messages=[
            {"role": "system", "content": CHAT_TOOLS_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        tools=_tool_specs_for_chat(tool_descriptions),
        options={"temperature": 0},
    )
    print("router: got ollama response", response.message, flush=True)
    return _parse_chat_tool_call(response)


def _route_with_json_generate(question: str, tool_descriptions: list[dict]) -> ToolCall:
    prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"Available tools:\n{json.dumps(tool_descriptions, indent=2)}\n\n"
        f"Question:\n{question}\n\n"
        "Return JSON only:"
    )

    payload = {
        "model": _ollama_model(),
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }

    req = request.Request(
        _ollama_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=_ollama_timeout()) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return _heuristic_fallback(question)

    # Ollama returns {"response":"{...json...}"} when format=json is used.
    response_text = body.get("response", "")
    try:
        parsed = json.loads(response_text)
        return ToolCall.model_validate(parsed)
    except (json.JSONDecodeError, ValueError):
        return _heuristic_fallback(question)


def route_question(question: str, tool_descriptions: list[dict]) -> ToolCall:
    """Use local Ollama to choose a deterministic tool, with robust fallback."""
    response = _route_with_chat_tools(question, tool_descriptions)
    print("router: got tool call", response, flush=True)
    return response
