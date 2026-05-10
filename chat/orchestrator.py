"""Grounded conversational orchestration: router -> executor -> validator -> summarizer."""

from __future__ import annotations

from sqlalchemy.orm import Session

from chat.llm_router import route_question
from chat.summarizer import summarize_tool_result
from chat.tool_executor import execute_tool_call
from chat.tool_registry import tool_descriptions_for_prompt
from chat.validator import validate_grounded_answer
from db.schema import GroundedChatResponse


def run_grounded_query(db: Session, question: str) -> GroundedChatResponse:
    """Execute one grounded query end-to-end with safety fallbacks."""
    tool_call = route_question(question, tool_descriptions_for_prompt())
    result = execute_tool_call(db, tool_call)
    answer = summarize_tool_result(result)
    try:
        validate_grounded_answer(answer, result)
    except ValueError:
        # Safe fallback never invents extra numbers.
        answer = (
            "I could not produce a fully grounded narrative for this question. "
            "Returning deterministic structured output only."
        )
    return GroundedChatResponse(
        question=question,
        tool_used=tool_call.tool_name,
        answer=answer,
        structured_data=result,
        citations=result.citations,
    )
