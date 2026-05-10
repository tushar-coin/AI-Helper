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
    "get_average_daily_revenue": ToolDefinition(
        name="get_average_daily_revenue",
        description="Compute average daily revenue from deterministic order totals over N days.",
        function=tools.get_average_daily_revenue_data,
        arguments_schema={"days": {"type": "integer", "required": False, "default": 30, "min": 1}},
    ),
    "get_rto_orders": ToolDefinition(
        name="get_rto_orders",
        description="Return count and records of orders that have RTO shipments.",
        function=tools.get_rto_orders_data,
        arguments_schema={
            "min_amount": {"type": "number", "required": False, "default": 0.0, "min": 0.0}
        },
    ),
    "get_failed_shipments": ToolDefinition(
        name="get_failed_shipments",
        description="Return count and records of failed-class shipments (rto/lost/failed/undelivered).",
        function=tools.get_failed_shipments_data,
        arguments_schema={},
    ),
    "get_order_by_id": ToolDefinition(
        name="get_order_by_id",
        description="Lookup one order by internal_order_id.",
        function=tools.get_order_by_id_data,
        arguments_schema={"internal_order_id": {"type": "string", "required": True}},
    ),
}


def tool_descriptions_for_prompt() -> list[dict]:
    """Compact tool metadata for the router prompt."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "arguments_schema": tool.arguments_schema,
        }
        for tool in TOOLS.values()
    ]
