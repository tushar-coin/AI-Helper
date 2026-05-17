"""LLM router with strict tool selection and safe heuristic fallback."""

from __future__ import annotations

import json

from chat.debug import chat_debug
from chat.llm_client import LlmClient, LlmClientError
from db.schema import AgentAction, ToolCall, ToolExecutionResult

IDENTITY_POLICY = """Identity policy:
- internal_order_id means normalized system id, usually starts with INT-ORD-.
- external order id/reference means source/vendor id, usually starts with ORD-.
- shipment ids may start with SHIP-; payment ids may start with PAY-.
- If the user provides SHIP-... and asks about date/status/courier, choose a shipment lookup tool, not an RTO aggregate.
- If the user provides ORD-... and asks for shipment id/date/courier, choose the shipment-for-order tool.
- If the user provides ORD-... and a tool asks for internal_order_id, pass the user's id exactly; deterministic tools can resolve external order refs safely.
- If a prior tool result contains internal_order_id values, reuse those exact values for follow-up tools.
- Never invent, rewrite, or guess ids yourself.
"""

SYSTEM_PROMPT = """You are a strict tool router for analytics.
Rules:
1) You MUST output valid JSON only.
2) You MUST choose exactly one tool from the provided list.
3) You MUST NOT answer the user question directly.
4) You MUST NOT compute business metrics yourself.
5) Arguments must follow the provided argument schema.
""" + IDENTITY_POLICY + """
Output shape:
{"tool_name":"<tool>","arguments":{...}}
"""

CHAT_TOOLS_SYSTEM_PROMPT = """You are a strict tool router for analytics.
Rules:
1) You MUST choose exactly one provided tool.
2) You MUST NOT answer the user question directly.
3) You MUST NOT compute business metrics yourself.
4) Tool arguments must follow the provided schema.
""" + IDENTITY_POLICY

NEXT_STEP_SYSTEM_PROMPT = """You are a bounded analytics agent planner.
Rules:
1) Choose the next action only.
2) Output valid JSON only.
3) If more source data is needed, choose exactly one provided tool.
4) If prior tool results are sufficient, return {"action":"final_answer"}.
5) You MUST NOT answer the user question directly.
6) You MUST NOT compute business metrics yourself.
""" + IDENTITY_POLICY + """
JSON OUTPUT FORMAT (MANDATORY):

To call a tool:
{"action":"tool","tool_name":"get_rto_orders","arguments":{}}

To call a tool with arguments:
{"action":"tool","tool_name":"get_revenue_for_order_ids","arguments":{"order_ids":["INT-ORD-1","INT-ORD-2"]}}

To stop and provide final answer:
{"action":"final_answer"}

CRITICAL: 
- Inside the JSON object, the first field is "action"
- For tools, action MUST be the string "tool" (not the tool name)
- For tools, tool_name MUST be a separate field with the actual tool name
- All tool parameters go inside "arguments" object
"""


def _heuristic_fallback(question: str) -> ToolCall:
    """Conservative fallback when local LLM is unavailable or malformed."""
    q = question.lower()
    order_ref = _extract_order_ref(question)
    shipment_ref = _extract_shipment_ref(question)
    if shipment_ref:
        return ToolCall(tool_name="get_shipment_by_id", arguments={"shipment_id": shipment_ref})
    if order_ref and any(word in q for word in ["shipment", "shipments", "courier", "delivery", "delivered"]):
        return ToolCall(tool_name="get_shipments_for_order", arguments={"order_id": order_ref})
    if "average" in q and "revenue" in q:
        return ToolCall(tool_name="get_average_daily_revenue", arguments={"days": 30})
    if ("rto" in q and "high" in q) or "high value" in q:
        return ToolCall(tool_name="get_rto_orders", arguments={"min_amount": 2000})
    if "rto" in q:
        return ToolCall(tool_name="get_rto_orders", arguments={})
    if "failed shipment" in q or "failed deliveries" in q:
        return ToolCall(tool_name="get_failed_shipments", arguments={})
    if "order" in q and order_ref:
        return ToolCall(tool_name="get_order_by_id", arguments={"internal_order_id": order_ref})
    if "revenue" in q:
        return ToolCall(tool_name="get_total_revenue", arguments={})
    return ToolCall(tool_name="get_rto_orders", arguments={})


def _extract_order_ref(question: str) -> str | None:
    for raw_part in question.replace(",", " ").split():
        token = raw_part.strip(" .:;()[]{}'\"").upper()
        if token.startswith(("INT-ORD-", "ORD-")):
            return token
    return None


def _extract_shipment_ref(question: str) -> str | None:
    for raw_part in question.replace(",", " ").split():
        token = raw_part.strip(" .:;()[]{}'\"").upper()
        if token.startswith(("INT-SHIP-", "SHIP-")):
            return token
    return None


def _heuristic_next_action(question: str, previous_results: list[ToolExecutionResult]) -> AgentAction:
    """Conservative local planner when the LLM cannot pick the next step."""
    if not previous_results:
        tool_call = _heuristic_fallback(question)
        return AgentAction(
            action="tool",
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
        )

    q = question.lower()
    last = previous_results[-1]
    if (
        last.metric == "rto_orders"
        and "revenue" in q
        and last.records
    ):
        order_ids = [
            str(row["internal_order_id"])
            for row in last.records
            if "internal_order_id" in row
        ]
        if order_ids:
            return AgentAction(
                action="tool",
                tool_name="get_revenue_for_order_ids",
                arguments={"order_ids": order_ids},
            )
    return AgentAction(action="final_answer")


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
                if key in {"type", "description", "default", "minimum", "maximum", "enum", "items"}
            }
            if "min" in arg_spec:
                prop["minimum"] = arg_spec["min"]
            if "min_items" in arg_spec:
                prop["minItems"] = arg_spec["min_items"]
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


def _route_with_chat_tools(question: str, tool_descriptions: list[dict]) -> ToolCall:
    raw_tool_call = LlmClient().choose_tool(
        system_prompt=CHAT_TOOLS_SYSTEM_PROMPT,
        user_prompt=question,
        tools=_tool_specs_for_chat(tool_descriptions),
    )
    return ToolCall.model_validate(raw_tool_call)


def _route_with_json_generate(question: str, tool_descriptions: list[dict]) -> ToolCall:
    prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"Available tools:\n{json.dumps(tool_descriptions, indent=2)}\n\n"
        f"Question:\n{question}\n\n"
        "Return JSON only:"
    )

    parsed = LlmClient().complete_json(prompt=prompt)
    return ToolCall.model_validate(parsed)


def _ensure_known_tool(tool_call: ToolCall, tool_descriptions: list[dict]) -> ToolCall:
    known_tools = {str(tool["name"]) for tool in tool_descriptions}
    if tool_call.tool_name not in known_tools:
        raise ValueError(f"Unknown routed tool: {tool_call.tool_name}")
    return tool_call


def _ensure_known_action(action: AgentAction, tool_descriptions: list[dict]) -> AgentAction:
    if action.action == "final_answer":
        return action
    if action.action != "tool":
        raise ValueError(f"Unknown agent action: {action.action}")
    if not action.tool_name:
        raise ValueError("Tool action must include tool_name")
    known_tools = {str(tool["name"]) for tool in tool_descriptions}
    if action.tool_name not in known_tools:
        raise ValueError(f"Unknown routed tool: {action.tool_name}")
    return action


def _action_available(action: AgentAction, tool_descriptions: list[dict]) -> bool:
    if action.action == "final_answer":
        return True
    if action.action != "tool" or not action.tool_name:
        return False
    return action.tool_name in {str(tool["name"]) for tool in tool_descriptions}


def _compact_result_for_prompt(result: ToolExecutionResult) -> dict:
    records = result.records[:10]
    return {
        "metric": result.metric,
        "value": result.value,
        "currency": result.currency,
        "calculation": result.calculation,
        "filters": result.filters,
        "records": records,
        "citations_count": len(result.citations),
    }


def _next_step_prompt(
    question: str,
    tool_descriptions: list[dict],
    previous_results: list[ToolExecutionResult],
) -> str:
    return (
        f"Available tools:\n{json.dumps(tool_descriptions, indent=2)}\n\n"
        f"Question:\n{question}\n\n"
        "Previous deterministic tool results:\n"
        f"{json.dumps([_compact_result_for_prompt(r) for r in previous_results], indent=2)}\n\n"
        "INSTRUCTIONS:\n"
        "1. Return ONLY valid JSON (no extra text)\n"
        "2. If you need to call a tool, output: {\"action\":\"tool\",\"tool_name\":\"tool_name_here\",\"arguments\":{...}}\n"
        "3. If you have enough data, output: {\"action\":\"final_answer\"}\n"
        "4. Do NOT put the tool name in the action field\n"
        "5. Do NOT put arguments outside the arguments object\n\n"
        "Choose the next action as JSON only:"
    )


def route_question(question: str, tool_descriptions: list[dict]) -> ToolCall:
    """Use local Ollama to choose a deterministic tool, with robust fallback."""
    chat_debug(
        "router.route_question.start",
        question=question,
        available_tools=[tool["name"] for tool in tool_descriptions],
    )
    try:
        tool_call = _ensure_known_tool(_route_with_chat_tools(question, tool_descriptions), tool_descriptions)
        chat_debug("router.route_question.selected", source="ollama_chat", tool_call=tool_call.model_dump())
        return tool_call
    except (LlmClientError, ValueError) as exc:
        chat_debug("router.route_question.chat_fallback", error=str(exc))
        try:
            tool_call = _ensure_known_tool(
                _route_with_json_generate(question, tool_descriptions),
                tool_descriptions,
            )
            chat_debug("router.route_question.selected", source="ollama_generate", tool_call=tool_call.model_dump())
            return tool_call
        except (LlmClientError, ValueError) as fallback_exc:
            tool_call = _heuristic_fallback(question)
            chat_debug(
                "router.route_question.selected",
                source="heuristic",
                error=str(fallback_exc),
                tool_call=tool_call.model_dump(),
            )
            return tool_call


def route_next_step(
    question: str,
    tool_descriptions: list[dict],
    previous_results: list[ToolExecutionResult],
) -> AgentAction:
    """Choose the next bounded loop action from question and prior tool results."""
    prompt = _next_step_prompt(question, tool_descriptions, previous_results)
    chat_debug(
        "router.route_next_step.start",
        question=question,
        previous_metrics=[result.metric for result in previous_results],
        available_tools=[tool["name"] for tool in tool_descriptions],
    )
    try:
        parsed = LlmClient().complete_json(prompt=f"{NEXT_STEP_SYSTEM_PROMPT}\n\n{prompt}")
        action = _ensure_known_action(AgentAction.model_validate(parsed), tool_descriptions)
        chat_debug("router.route_next_step.selected", source="ollama_generate", action=action.model_dump())
        return action
    except (LlmClientError, ValueError) as exc:
        action = _heuristic_next_action(question, previous_results)
        if not _action_available(action, tool_descriptions):
            chat_debug(
                "router.route_next_step.heuristic_tool_unavailable",
                requested_action=action.model_dump(),
                available_tools=[tool["name"] for tool in tool_descriptions],
            )
            action = AgentAction(action="final_answer")
        action = _ensure_known_action(action, tool_descriptions)
        chat_debug(
            "router.route_next_step.selected",
            source="heuristic",
            error=str(exc),
            action=action.model_dump(),
        )
        return action
