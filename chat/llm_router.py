"""Local LLM router (Ollama) with strict JSON output and safe heuristic fallback."""

from __future__ import annotations

import json
import os
from urllib import error, request

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


def _ollama_url() -> str:
    return os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")


def _ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen3.5")


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


def route_question(question: str, tool_descriptions: list[dict]) -> ToolCall:
    """Use local Ollama to choose a deterministic tool, with robust fallback."""
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
        with request.urlopen(req, timeout=8) as resp:
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
