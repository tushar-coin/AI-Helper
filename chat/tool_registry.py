"""Deterministic tool catalog used by router and executor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from chat import tools
from db.schema import ToolExecutionResult


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    function: Callable[..., ToolExecutionResult]
    arguments_schema: dict[str, dict]


TOOLS: dict[str, ToolDefinition] = {
    "get_total_revenue": ToolDefinition(
        name="get_total_revenue",
        description="Compute deterministic total order revenue from normalized orders.",
        function=tools.get_total_revenue_data,
        arguments_schema={},
    ),
    "get_order_status_breakdown": ToolDefinition(
        name="get_order_status_breakdown",
        description="Count normalized orders by order_status, such as paid, pending, fulfilled.",
        function=tools.get_order_status_breakdown_data,
        arguments_schema={},
    ),
    "get_orders_by_status": ToolDefinition(
        name="get_orders_by_status",
        description="List/count normalized orders for one order_status with optional min_amount filter.",
        function=tools.get_orders_by_status_data,
        arguments_schema={
            "status": {
                "type": "string",
                "description": "Normalized order status, usually paid, pending, fulfilled, or unknown.",
                "required": True,
            },
            "min_amount": {"type": "number", "required": False, "default": 0.0, "min": 0.0},
        },
    ),
    "get_customer_order_summary": ToolDefinition(
        name="get_customer_order_summary",
        description="Summarize orders and revenue for an exact customer_name.",
        function=tools.get_customer_order_summary_data,
        arguments_schema={
            "customer_name": {
                "type": "string",
                "description": "Exact customer name from normalized orders, e.g. Rahul or Priya.",
                "required": True,
            }
        },
    ),
    "get_average_daily_revenue": ToolDefinition(
        name="get_average_daily_revenue",
        description="Compute average daily revenue from deterministic order totals over N days.",
        function=tools.get_average_daily_revenue_data,
        arguments_schema={"days": {"type": "integer", "required": False, "default": 30, "min": 1}},
    ),
    "get_revenue_for_order_ids": ToolDefinition(
        name="get_revenue_for_order_ids",
        description=(
            "Compute deterministic revenue for selected orders. Prefer internal normalized "
            "order ids from prior tool results (INT-ORD-...). If the user supplied external "
            "order refs like ORD-101, pass them exactly; the tool resolves known mappings."
        ),
        function=tools.get_revenue_for_order_ids_data,
        arguments_schema={
            "order_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of order identifiers. Prefer internal_order_id values (INT-ORD-...). "
                    "External order refs such as ORD-101 are accepted and resolved if mapped."
                ),
                "required": True,
                "min_items": 1,
            }
        },
    ),
    "get_rto_orders": ToolDefinition(
        name="get_rto_orders",
        description="Return count and records of orders that have RTO shipments.",
        function=tools.get_rto_orders_data,
        arguments_schema={
            "min_amount": {"type": "number", "required": False, "default": 0.0, "min": 0.0}
        },
    ),
    "get_shipment_status_breakdown": ToolDefinition(
        name="get_shipment_status_breakdown",
        description="Count shipments by shipment_status, such as delivered, rto, lost.",
        function=tools.get_shipment_status_breakdown_data,
        arguments_schema={},
    ),
    "get_shipments_by_status": ToolDefinition(
        name="get_shipments_by_status",
        description="List/count shipments for one shipment_status, such as delivered, rto, lost.",
        function=tools.get_shipments_by_status_data,
        arguments_schema={
            "status": {
                "type": "string",
                "description": "Normalized shipment status, e.g. delivered, rto, lost, failed, undelivered.",
                "required": True,
            }
        },
    ),
    "get_shipment_by_id": ToolDefinition(
        name="get_shipment_by_id",
        description=(
            "Lookup one shipment by shipment id and return shipped_at date, status, courier, "
            "and linked internal_order_id. Accepts external ids like SHIP-778 or internal ids "
            "like INT-SHIP-..."
        ),
        function=tools.get_shipment_by_id_data,
        arguments_schema={
            "shipment_id": {
                "type": "string",
                "description": "External shipment id like SHIP-778 or internal shipment id.",
                "required": True,
            }
        },
    ),
    "get_shipments_for_order": ToolDefinition(
        name="get_shipments_for_order",
        description=(
            "Find shipment ids, shipment dates, statuses, and courier names linked to one order. "
            "Use this when the user gives an order id/ref like ORD-101 and asks for shipment id, "
            "courier, delivery, or shipped_at."
        ),
        function=tools.get_shipments_for_order_data,
        arguments_schema={
            "order_id": {
                "type": "string",
                "description": "Internal order id like INT-ORD-... or mapped external order ref like ORD-101.",
                "required": True,
            }
        },
    ),
    "get_failed_shipments": ToolDefinition(
        name="get_failed_shipments",
        description="Return count and records of failed-class shipments (rto/lost/failed/undelivered).",
        function=tools.get_failed_shipments_data,
        arguments_schema={},
    ),
    "get_payment_status_breakdown": ToolDefinition(
        name="get_payment_status_breakdown",
        description="Count payments by payment_status, such as paid, pending, failed.",
        function=tools.get_payment_status_breakdown_data,
        arguments_schema={},
    ),
    "get_payments_by_status": ToolDefinition(
        name="get_payments_by_status",
        description="List/count payments for one payment_status and include total amount.",
        function=tools.get_payments_by_status_data,
        arguments_schema={
            "status": {
                "type": "string",
                "description": "Normalized payment status, e.g. paid, pending, failed.",
                "required": True,
            }
        },
    ),
    "get_payment_method_breakdown": ToolDefinition(
        name="get_payment_method_breakdown",
        description="Count and sum payments by payment_method, such as cod or upi.",
        function=tools.get_payment_method_breakdown_data,
        arguments_schema={},
    ),
    "get_orders_by_payment_method": ToolDefinition(
        name="get_orders_by_payment_method",
        description="List/count orders whose payment used a specific payment_method, such as cod or upi.",
        function=tools.get_orders_by_payment_method_data,
        arguments_schema={
            "payment_method": {
                "type": "string",
                "description": "Normalized payment method, e.g. cod or upi.",
                "required": True,
            }
        },
    ),
    "get_order_by_id": ToolDefinition(
        name="get_order_by_id",
        description=(
            "Lookup one normalized order. Argument name is internal_order_id, but this tool "
            "also accepts a mapped external order ref such as ORD-101 and resolves it."
        ),
        function=tools.get_order_by_id_data,
        arguments_schema={
            "internal_order_id": {
                "type": "string",
                "description": (
                    "Internal normalized order id like INT-ORD-...; mapped external refs like "
                    "ORD-101 are also accepted. Do not pass shipment/payment ids."
                ),
                "required": True,
            }
        },
    ),
    "get_order_timeline": ToolDefinition(
        name="get_order_timeline",
        description=(
            "Return order, shipment, and payment events for one order. Accepts internal "
            "INT-ORD-... ids or mapped external refs like ORD-101."
        ),
        function=tools.get_order_timeline_data,
        arguments_schema={
            "order_id": {
                "type": "string",
                "description": "Internal normalized order id or mapped external order ref.",
                "required": True,
            }
        },
    ),
    "get_orders_by_id_delivered": ToolDefinition(
        name="get_orders_by_id_delivered",
        description=(
            "Lookup a delivered order. Prefer internal_order_id (INT-ORD-...), but mapped "
            "external order refs like ORD-101 are accepted and resolved."
        ),
        function=tools.get_orders_by_id_delivered_data,
        arguments_schema={
            "internal_order_id": {
                "type": "string",
                "description": "Internal normalized order id or mapped external order ref.",
                "required": True,
            }
        },
    ),
}


def tool_descriptions_for_prompt() -> list[dict]:
    """Compact tool metadata for the router prompt."""
    return _descriptions_for_tools(TOOLS.keys())


def select_tool_descriptions_for_prompt(
    question: str,
    *,
    previous_metrics: list[str] | None = None,
) -> list[dict]:
    """Return a relevant subset of tools so the LLM is not overloaded."""
    q = question.lower()
    selected: set[str] = set()

    # Always include broad safe defaults and useful follow-up tools.
    selected.update({"get_total_revenue", "get_order_by_id", "get_order_timeline"})

    if any(word in q for word in ["revenue", "sales", "amount", "value"]):
        selected.update(
            {
                "get_total_revenue",
                "get_average_daily_revenue",
                "get_revenue_for_order_ids",
                "get_orders_by_status",
            }
        )
    if any(word in q for word in ["order", "orders", "customer", "paid", "pending", "fulfilled"]):
        selected.update(
            {
                "get_order_status_breakdown",
                "get_orders_by_status",
                "get_customer_order_summary",
                "get_order_by_id",
            }
        )
    if any(word in q for word in ["shipment", "shipments", "delivery", "delivered", "lost", "rto", "courier", "failed", "ship-"]):
        selected.update(
            {
                "get_shipment_by_id",
                "get_shipments_for_order",
                "get_rto_orders",
                "get_failed_shipments",
                "get_shipment_status_breakdown",
                "get_shipments_by_status",
            }
        )
    if any(word in q for word in ["payment", "payments", "cod", "upi", "prepaid", "captured", "authorized"]):
        selected.update(
            {
                "get_payment_status_breakdown",
                "get_payments_by_status",
                "get_payment_method_breakdown",
                "get_orders_by_payment_method",
            }
        )
    if previous_metrics:
        if "rto_orders" in previous_metrics or "orders_by_status" in previous_metrics:
            selected.add("get_revenue_for_order_ids")
        if "order_by_id" in previous_metrics:
            selected.add("get_order_timeline")

    # Keep the prompt compact and deterministic.
    priority: list[str] = []
    if "ship-" in q:
        priority.append("get_shipment_by_id")
    if "ord-" in q and any(word in q for word in ["shipment", "shipments", "courier", "delivery", "delivered"]):
        priority.append("get_shipments_for_order")
    if "ord-" in q:
        priority.extend(["get_order_by_id", "get_order_timeline"])

    ordered = []
    for name in priority:
        if name in selected and name not in ordered:
            ordered.append(name)
    ordered.extend(name for name in TOOLS if name in selected and name not in ordered)
    return _descriptions_for_tools(ordered[:8])


def _descriptions_for_tools(tool_names) -> list[dict]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "arguments_schema": tool.arguments_schema,
        }
        for name in tool_names
        for tool in [TOOLS[name]]
    ]
