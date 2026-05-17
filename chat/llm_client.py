"""Centralized local LLM client.

This module is the only chat module that knows how to talk to Ollama. Routers,
summarizers, and tools should depend on this small interface instead of creating
provider clients directly.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

import ollama

from chat.debug import chat_debug


class LlmClientError(RuntimeError):
    """Raised when the configured LLM provider is unavailable or malformed."""


def _ollama_url() -> str:
    return os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")


def _ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", _ollama_url().removesuffix("/api/generate"))


def _ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")


def _ollama_timeout() -> float:
    return float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))


def _get_value(obj: object, key: str, default: object = None) -> object:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class LlmClient:
    """Thin provider wrapper for JSON completions and function/tool calling."""

    def __init__(
        self,
        *,
        host: str | None = None,
        url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.host = host or _ollama_host()
        self.url = url or _ollama_url()
        self.model = model or _ollama_model()
        self.timeout = timeout or _ollama_timeout()

    def choose_tool(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Ask Ollama chat to choose one tool and return raw function call data."""
        client = ollama.Client(host=self.host, timeout=self.timeout)
        chat_debug(
            "llm.chat.request",
            model=self.model,
            host=self.host,
            tool_names=[
                tool.get("function", {}).get("name")
                for tool in tools
                if isinstance(tool, dict)
            ],
            user_prompt=user_prompt,
        )
        try:
            response = client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=tools,
                options={"temperature": 0},
            )
        except Exception as exc:
            chat_debug("llm.chat.error", error=str(exc))
            raise LlmClientError(f"Ollama chat request failed: {exc}") from exc

        message = _get_value(response, "message", {})
        chat_debug("llm.chat.response", message=message)
        tool_calls = _get_value(message, "tool_calls", []) or []
        if not tool_calls:
            raise LlmClientError("Ollama chat response did not include a tool call")

        function = _get_value(tool_calls[0], "function", {})
        tool_name = _get_value(function, "name")
        arguments = _get_value(function, "arguments", {}) or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise LlmClientError("Ollama tool arguments were not valid JSON") from exc
        if not isinstance(arguments, dict):
            raise LlmClientError("Ollama tool arguments must be a JSON object")
        raw_tool_call = {"tool_name": tool_name, "arguments": arguments}
        chat_debug("llm.chat.tool_call", **raw_tool_call)
        return raw_tool_call

    def complete_json(self, *, prompt: str) -> dict[str, Any]:
        """Ask Ollama generate endpoint for a strict JSON object response."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        req = request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        chat_debug("llm.generate.request", model=self.model, url=self.url, prompt=prompt)
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            response_text = body.get("response", "").strip()
            chat_debug("llm.generate.raw_response", response=response_text, response_length=len(response_text))
            if not response_text:
                raise LlmClientError("Ollama model returned empty response (possible timeout or model issue)")
            parsed = json.loads(response_text)
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            chat_debug("llm.generate.error", error=str(exc), model=self.model, timeout=self.timeout)
            raise LlmClientError(f"Ollama JSON request failed: {exc}") from exc

        if not isinstance(parsed, dict):
            raise LlmClientError("Ollama JSON response must be an object")
        chat_debug("llm.generate.parsed_response", response=parsed)
        return parsed
