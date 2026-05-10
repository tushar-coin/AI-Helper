"""Natural-language summarization from grounded deterministic tool results."""

from __future__ import annotations

from db.schema import ToolExecutionResult


def summarize_tool_result(result: ToolExecutionResult) -> str:
    """Render a concise answer without introducing uncited numbers."""
    if result.metric == "total_revenue":
        return f"Total revenue is {result.currency} {result.value}."
    if result.metric == "average_daily_revenue":
        days = result.calculation.get("days", "?")
        return f"Average daily revenue over the last {days} days is {result.currency} {result.value}."
    if result.metric == "rto_orders":
        threshold = result.filters.get("min_amount", 0)
        if threshold:
            return (
                f"There are {result.value} RTO orders with amount >= {threshold} "
                "in the normalized dataset."
            )
        return f"There are {result.value} orders with an RTO shipment in the normalized dataset."
    if result.metric == "failed_shipments":
        return f"There are {result.value} failed or RTO-class shipments."
    if result.metric == "order_by_id":
        if result.value == "not_found":
            order_id = result.filters.get("internal_order_id", "<unknown>")
            return f"No order found for internal_order_id='{order_id}'."
        row = result.records[0]
        return (
            f"Order {row['internal_order_id']}: customer={row['customer_name']}, "
            f"amount={row['currency']} {row['amount']}, status={row['order_status']}."
        )
    return f"{result.metric}: {result.value}"
