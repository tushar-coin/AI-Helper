from chat import llm_router
from chat.llm_client import LlmClientError
from chat.tool_registry import tool_descriptions_for_prompt


class FailingLlmClient:
    def choose_tool(self, **_kwargs):
        raise LlmClientError("chat unavailable")

    def complete_json(self, **_kwargs):
        raise LlmClientError("generate unavailable")


class UnknownToolThenFallbackClient:
    def choose_tool(self, **_kwargs):
        return {"tool_name": "raw_sql", "arguments": {}}

    def complete_json(self, **_kwargs):
        return {"tool_name": "get_total_revenue", "arguments": {}}


class NextStepToolClient:
    def complete_json(self, **_kwargs):
        return {"action": "tool", "tool_name": "get_total_revenue", "arguments": {}}


class NextStepFinalClient:
    def complete_json(self, **_kwargs):
        return {"action": "final_answer"}


def test_route_question_uses_heuristic_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(llm_router, "LlmClient", FailingLlmClient)

    tool_call = llm_router.route_question(
        "show high value rto orders",
        tool_descriptions_for_prompt(),
    )

    assert tool_call.tool_name == "get_rto_orders"
    assert tool_call.arguments == {"min_amount": 2000}


def test_route_question_rejects_unknown_tool_and_uses_json_fallback(monkeypatch):
    monkeypatch.setattr(llm_router, "LlmClient", UnknownToolThenFallbackClient)

    tool_call = llm_router.route_question(
        "what is total revenue?",
        tool_descriptions_for_prompt(),
    )

    assert tool_call.tool_name == "get_total_revenue"
    assert tool_call.arguments == {}


def test_route_question_heuristic_accepts_external_order_ref(monkeypatch):
    monkeypatch.setattr(llm_router, "LlmClient", FailingLlmClient)

    tool_call = llm_router.route_question(
        "show me order ORD-101",
        tool_descriptions_for_prompt(),
    )

    assert tool_call.tool_name == "get_order_by_id"
    assert tool_call.arguments == {"internal_order_id": "ORD-101"}


def test_route_question_heuristic_accepts_external_shipment_ref(monkeypatch):
    monkeypatch.setattr(llm_router, "LlmClient", FailingLlmClient)

    tool_call = llm_router.route_question(
        "SHIP-778 what is the shipment date of this id",
        tool_descriptions_for_prompt(),
    )

    assert tool_call.tool_name == "get_shipment_by_id"
    assert tool_call.arguments == {"shipment_id": "SHIP-778"}


def test_route_question_heuristic_selects_shipments_for_order(monkeypatch):
    monkeypatch.setattr(llm_router, "LlmClient", FailingLlmClient)

    tool_call = llm_router.route_question(
        "shipment id linked to order id ORD-101 and also tell me courier name",
        tool_descriptions_for_prompt(),
    )

    assert tool_call.tool_name == "get_shipments_for_order"
    assert tool_call.arguments == {"order_id": "ORD-101"}


def test_route_next_step_returns_registered_tool(monkeypatch):
    monkeypatch.setattr(llm_router, "LlmClient", NextStepToolClient)

    action = llm_router.route_next_step(
        "what is total revenue?",
        tool_descriptions_for_prompt(),
        [],
    )

    assert action.action == "tool"
    assert action.tool_name == "get_total_revenue"
    assert action.arguments == {}


def test_route_next_step_can_stop(monkeypatch):
    monkeypatch.setattr(llm_router, "LlmClient", NextStepFinalClient)

    action = llm_router.route_next_step(
        "what is total revenue?",
        tool_descriptions_for_prompt(),
        [],
    )

    assert action.action == "final_answer"
