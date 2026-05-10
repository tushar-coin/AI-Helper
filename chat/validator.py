"""Validation layer to block unsupported numeric claims and uncited outputs."""

from __future__ import annotations

import json
import re

from db.schema import ToolExecutionResult

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_numbers(text: str) -> list[str]:
    return _NUMBER_RE.findall(text)


def validate_grounded_answer(answer: str, result: ToolExecutionResult) -> None:
    """
    Validate that summarization stayed grounded in tool output and citations.

    Rule: if summary has numbers, citations must be present.
    Rule: summary numbers must appear in serialized structured result.
    """
    numbers = _extract_numbers(answer)
    if not numbers:
        return
    if not result.citations:
        raise ValueError("Numeric answer cannot be returned without citations.")
    serialized = json.dumps(result.model_dump(), default=str)
    for number in numbers:
        if number not in serialized:
            raise ValueError(
                f"Detected unsupported numeric claim '{number}' that is absent from tool output."
            )
