"""Grounded conversational orchestration with a bounded multi-tool loop."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from chat.debug import chat_debug
from chat.llm_router import route_next_step, route_question
from chat.summarizer import summarize_tool_result, summarize_tool_results
from chat.tool_executor import execute_tool_call
from chat.tool_registry import select_tool_descriptions_for_prompt, tool_descriptions_for_prompt
from chat.validator import validate_grounded_answer, validate_grounded_answer_against_results
from db.schema import (
    AgentStepLog,
    GroundedChatResponse,
    MultiStepGroundedChatResponse,
    ToolCall,
    ToolExecutionResult,
)

MAX_STEPS = 3


def _merge_citations(results: list[ToolExecutionResult]):
    seen: set[tuple[str, str, str, str, str | None]] = set()
    citations = []
    for result in results:
        for citation in result.citations:
            key = (
                citation.internal_entity_id,
                citation.source_system,
                citation.source_field,
                citation.source_row_id,
                citation.field_name,
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(citation)
    return citations


def _tool_call_key(tool_call: ToolCall) -> str:
    return json.dumps(
        {"tool_name": tool_call.tool_name, "arguments": tool_call.arguments},
        sort_keys=True,
        default=str,
    )


def _log_step(step: int, tool_call: ToolCall, result: ToolExecutionResult) -> AgentStepLog:
    return AgentStepLog(
        step=step,
        action="tool",
        tool_name=tool_call.tool_name,
        arguments=tool_call.arguments,
        result_metric=result.metric,
        result_value=result.value,
        citations_count=len(result.citations),
    )


def _safe_multi_step_response(
    *,
    question: str,
    results: list[ToolExecutionResult],
    run_logs: list[AgentStepLog],
    tool_names: list[str],
) -> MultiStepGroundedChatResponse:
    answer = (
        "I could not produce a fully grounded narrative for this question. "
        "Returning deterministic structured output only."
    )
    return MultiStepGroundedChatResponse(
        question=question,
        tool_used=tool_names,
        answer=answer,
        structured_data=results,
        citations=_merge_citations(results),
        run_logs=run_logs,
    )


def run_grounded_query(db: Session, question: str) -> GroundedChatResponse:
    """Execute one grounded query end-to-end with safety fallbacks."""
    chat_debug("orchestrator.single.start", question=question)
    tool_call = route_question(question, select_tool_descriptions_for_prompt(question))
    chat_debug("orchestrator.single.tool_selected", tool_call=tool_call.model_dump())
    result = execute_tool_call(db, tool_call)
    chat_debug(
        "orchestrator.single.tool_result",
        metric=result.metric,
        value=result.value,
        citations_count=len(result.citations),
    )
    answer = summarize_tool_result(result)
    try:
        validate_grounded_answer(answer, result)
    except ValueError:
        # Safe fallback never invents extra numbers.
        answer = (
            "I could not produce a fully grounded narrative for this question. "
            "Returning deterministic structured output only."
        )
        chat_debug("orchestrator.single.validation_failed", answer=answer)
    chat_debug("orchestrator.single.answer", answer=answer, tool_used=tool_call.tool_name)
    return GroundedChatResponse(
        question=question,
        tool_used=tool_call.tool_name,
        answer=answer,
        structured_data=result,
        citations=result.citations,
    )


def run_grounded_query_loop(db: Session, question: str) -> MultiStepGroundedChatResponse:
    """Execute a bounded agentic tool loop with deterministic tools only."""
    chat_debug("orchestrator.loop.start", question=question, max_steps=MAX_STEPS)
    tool_descriptions = select_tool_descriptions_for_prompt(question)
    results: list[ToolExecutionResult] = []
    run_logs: list[AgentStepLog] = []
    tool_names: list[str] = []
    seen_calls: set[str] = set()

    for step in range(1, MAX_STEPS + 1):
        previous_metrics = [result.metric for result in results]
        tool_descriptions = select_tool_descriptions_for_prompt(
            question,
            previous_metrics=previous_metrics,
        )
        action = route_next_step(question, tool_descriptions, results)
        chat_debug("orchestrator.loop.action", step=step, action=action.model_dump())
        if action.action == "final_answer":
            run_logs.append(AgentStepLog(step=step, action="final_answer"))
            break

        tool_call = ToolCall(
            tool_name=str(action.tool_name),
            arguments=action.arguments,
        )
        key = _tool_call_key(tool_call)
        if key in seen_calls:
            chat_debug(
                "orchestrator.loop.repeat_stop",
                step=step,
                tool_call=tool_call.model_dump(),
            )
            run_logs.append(
                AgentStepLog(
                    step=step,
                    action="final_answer",
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                )
            )
            break
        seen_calls.add(key)

        try:
            result = execute_tool_call(db, tool_call)
        except ValueError as exc:
            chat_debug(
                "orchestrator.loop.tool_error",
                step=step,
                tool_call=tool_call.model_dump(),
                error=str(exc),
            )
            run_logs.append(
                AgentStepLog(
                    step=step,
                    action="tool_error",
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                )
            )
            break
        results.append(result)
        tool_names.append(tool_call.tool_name)
        run_logs.append(_log_step(step, tool_call, result))
        chat_debug(
            "orchestrator.loop.tool_result",
            step=step,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            metric=result.metric,
            value=result.value,
            citations_count=len(result.citations),
        )

    if not results:
        chat_debug("orchestrator.loop.no_results_fallback")
        fallback_call = route_question(question, tool_descriptions_for_prompt())
        fallback_result = execute_tool_call(db, fallback_call)
        results.append(fallback_result)
        tool_names.append(fallback_call.tool_name)
        run_logs.append(_log_step(1, fallback_call, fallback_result))

    answer = summarize_tool_results(results)
    try:
        validate_grounded_answer_against_results(answer, results)
    except ValueError:
        chat_debug("orchestrator.loop.validation_failed", answer=answer)
        return _safe_multi_step_response(
            question=question,
            results=results,
            run_logs=run_logs,
            tool_names=tool_names,
        )

    response = MultiStepGroundedChatResponse(
        question=question,
        tool_used=tool_names,
        answer=answer,
        structured_data=results,
        citations=_merge_citations(results),
        run_logs=run_logs,
    )
    chat_debug(
        "orchestrator.loop.answer",
        answer=response.answer,
        tools=response.tool_used,
        citations_count=len(response.citations),
        run_logs=[log.model_dump() for log in response.run_logs],
    )
    return response
