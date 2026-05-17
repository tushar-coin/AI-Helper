"""Natural-language summarization from grounded deterministic tool results."""

from __future__ import annotations

from db.schema import ToolExecutionResult


def summarize_tool_result(result: ToolExecutionResult) -> str:
    """Render a concise answer without introducing uncited numbers."""
    if result.metric == "total_revenue":
        return f"Total revenue is {result.currency} {result.value}."
    if result.metric == "revenue_for_order_ids":
        order_count = result.calculation.get("order_count", 0)
        return f"Revenue for the selected {order_count} orders is {result.currency} {result.value}."
    if result.metric == "average_daily_revenue":
        days = result.calculation.get("days", "?")
        return f"Average daily revenue over the last {days} days is {result.currency} {result.value}."
    if result.metric == "order_status_breakdown":
        return f"Order status breakdown: {result.value}."
    if result.metric == "orders_by_status":
        status = result.filters.get("status", "<unknown>")
        return f"There are {result.value} orders with status '{status}'."
    if result.metric == "customer_order_summary":
        customer = result.filters.get("customer_name", "<unknown>")
        count = result.calculation.get("order_count", 0)
        return f"Customer {customer} has {count} orders totaling {result.currency} {result.value}."
    if result.metric == "shipment_status_breakdown":
        return f"Shipment status breakdown: {result.value}."
    if result.metric == "shipments_by_status":
        status = result.filters.get("status", "<unknown>")
        return f"There are {result.value} shipments with status '{status}'."
    if result.metric == "shipment_by_id":
        if result.value == "not_found":
            shipment_id = result.filters.get("shipment_id", "<unknown>")
            return f"No shipment found for shipment_id='{shipment_id}'."
        row = result.records[0]
        return (
            f"Shipment {row['internal_shipment_id']} was shipped at {row['shipped_at']}; "
            f"status={row['shipment_status']}, courier={row['courier_name']}."
        )
    if result.metric == "shipments_for_order":
        if result.value == "not_found":
            order_id = result.filters.get("order_id", "<unknown>")
            return f"No shipments found for order_id='{order_id}'."
        if not result.records:
            order_id = result.filters.get("order_id", "<unknown>")
            return f"There are 0 shipments linked to order_id='{order_id}'."
        rows = [
            (
                f"{row['internal_shipment_id']} shipped_at={row['shipped_at']}, "
                f"status={row['shipment_status']}, courier={row['courier_name']}"
            )
            for row in result.records
        ]
        return f"There are {result.value} shipments linked to this order: " + "; ".join(rows) + "."
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
    if result.metric == "payment_status_breakdown":
        return f"Payment status breakdown: {result.value}."
    if result.metric == "payments_by_status":
        status = result.filters.get("status", "<unknown>")
        total = result.calculation.get("total_amount", 0)
        return f"There are {result.value} payments with status '{status}', totaling {result.currency} {total}."
    if result.metric == "payment_method_breakdown":
        return f"Payment method breakdown: {result.value}."
    if result.metric == "orders_by_payment_method":
        method = result.filters.get("payment_method", "<unknown>")
        total = result.calculation.get("total_revenue", 0)
        return f"There are {result.value} orders paid by {method}, totaling {result.currency} {total}."
    if result.metric == "order_by_id":
        if result.value == "not_found":
            order_id = result.filters.get("internal_order_id", "<unknown>")
            return f"No order found for internal_order_id='{order_id}'."
        row = result.records[0]
        return (
            f"Order {row['internal_order_id']}: customer={row['customer_name']}, "
            f"amount={row['currency']} {row['amount']}, status={row['order_status']}."
        )
    if result.metric == "order_timeline":
        if result.value == "not_found":
            order_id = result.filters.get("order_id", "<unknown>")
            return f"No order timeline found for order_id='{order_id}'."
        return (
            f"Order {result.value} timeline has "
            f"{result.calculation.get('event_count', 0)} events."
        )
    return f"{result.metric}: {result.value}"


def summarize_tool_results(results: list[ToolExecutionResult]) -> str:
    """Render a concise multi-step answer from deterministic tool results only."""
    if not results:
        return "I could not run a grounded tool for this question."
    if len(results) == 1:
        return summarize_tool_result(results[0])

    rto = next((result for result in results if result.metric == "rto_orders"), None)
    selected_revenue = next(
        (result for result in results if result.metric == "revenue_for_order_ids"),
        None,
    )
    if rto and selected_revenue:
        threshold = rto.filters.get("min_amount", 0)
        if threshold:
            return (
                f"There are {rto.value} RTO orders with amount >= {threshold}. "
                f"Revenue for those {selected_revenue.calculation.get('order_count', 0)} orders is "
                f"{selected_revenue.currency} {selected_revenue.value}."
            )
        return (
            f"There are {rto.value} orders with an RTO shipment. "
            f"Revenue for those {selected_revenue.calculation.get('order_count', 0)} orders is "
            f"{selected_revenue.currency} {selected_revenue.value}."
        )

    return " ".join(summarize_tool_result(result) for result in results)
