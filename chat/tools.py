"""
Chat tool layer.

**Rule:** any numeric answer must include citations derived from `provenance` rows
so downstream LLMs cannot present uncited figures.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db import crud
from db.models import Order, Shipment
from db.schema import ChatAnswer, Citation, ToolExecutionResult
from services.provenance import merge_citations_unique, provenance_rows_to_citations


def _total_revenue_result(db: Session) -> ToolExecutionResult:
    """Deterministic revenue aggregate over normalized order rows."""
    orders = crud.list_orders(db, limit=10_000)
    if not orders:
        return ToolExecutionResult(
            metric="total_revenue",
            value=0,
            currency="INR",
            calculation={"order_count": 0},
            citations=[],
        )

    total = Decimal("0")
    order_ids: list[str] = []
    for o in orders:
        total += Decimal(o.amount)
        order_ids.append(o.internal_order_id)

    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=order_ids,
        field_names=["amount"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))

    currency = orders[0].currency
    return ToolExecutionResult(
        metric="total_revenue",
        value=float(total),
        currency=currency,
        calculation={"order_count": len(orders)},
        records=[{"internal_order_id": order_id} for order_id in order_ids],
        citations=citations,
    )


def _average_daily_revenue_result(db: Session, *, days: int = 30) -> ToolExecutionResult:
    """Deterministic average daily revenue for the last N days."""
    safe_days = max(1, int(days))
    orders = list(crud.list_orders(db, limit=10_000))
    if not orders:
        return ToolExecutionResult(
            metric="average_daily_revenue",
            value=0,
            currency="INR",
            calculation={"total_revenue": 0, "days": safe_days},
            filters={"days": safe_days},
            citations=[],
        )

    latest_created_at = max(order.created_at for order in orders)
    start_window = latest_created_at - timedelta(days=safe_days - 1)
    in_window = [order for order in orders if order.created_at >= start_window]
    total = sum(Decimal(order.amount) for order in in_window)
    average = total / Decimal(safe_days)
    order_ids = [order.internal_order_id for order in in_window]

    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=order_ids,
        field_names=["amount"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))

    return ToolExecutionResult(
        metric="average_daily_revenue",
        value=float(average),
        currency=in_window[0].currency if in_window else "INR",
        calculation={"total_revenue": float(total), "days": safe_days, "order_count": len(in_window)},
        filters={"days": safe_days, "window_start": start_window.isoformat()},
        records=[{"internal_order_id": order_id} for order_id in order_ids],
        citations=citations,
    )


def _rto_orders_result(db: Session, *, min_amount: float = 0.0) -> ToolExecutionResult:
    """Deterministic RTO order metric with optional high-value filter."""
    stmt = (
        select(Order)
        .join(Shipment, Shipment.internal_order_id == Order.internal_order_id)
        .where(Shipment.shipment_status == "rto")
        .distinct()
    )
    orders = db.scalars(stmt).all()
    threshold = Decimal(str(min_amount))
    if threshold > 0:
        orders = [order for order in orders if Decimal(order.amount) >= threshold]
    count = len(orders)
    order_ids = [o.internal_order_id for o in orders]
    ship_stmt = select(Shipment).where(
        Shipment.internal_order_id.in_(order_ids),
        Shipment.shipment_status == "rto",
    )
    shipments = db.scalars(ship_stmt).all()
    shipment_ids = [s.internal_shipment_id for s in shipments]

    prov_orders = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=order_ids,
        field_names=["amount"],
    )
    prov_ship = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=shipment_ids,
        field_names=["shipment_status"],
    )
    citations = merge_citations_unique(
        provenance_rows_to_citations(list(prov_orders) + list(prov_ship))
    )

    if count == 0 and not citations:
        any_ship = crud.latest_provenance_for_entities(
            db,
            internal_entity_ids=[
                s.internal_shipment_id for s in crud.list_shipments(db, limit=20)
            ],
            field_names=["shipment_status"],
        )
        citations = provenance_rows_to_citations(any_ship)

    return ToolExecutionResult(
        metric="rto_orders",
        value=count,
        filters={"min_amount": float(threshold)},
        calculation={"order_count": count, "shipment_count": len(shipments)},
        records=[
            {
                "internal_order_id": order.internal_order_id,
                "customer_name": order.customer_name,
                "amount": float(order.amount),
                "currency": order.currency,
            }
            for order in orders
        ],
        citations=citations,
    )


def _order_by_id_result(db: Session, *, internal_order_id: str) -> ToolExecutionResult:
    """Deterministic lookup for a single internal order."""
    order = crud.get_order(db, internal_order_id)
    if order is None:
        return ToolExecutionResult(
            metric="order_by_id",
            value="not_found",
            filters={"internal_order_id": internal_order_id},
            citations=[],
        )

    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[internal_order_id],
        field_names=["amount", "customer_name", "order_status"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))

    return ToolExecutionResult(
        metric="order_by_id",
        value=order.internal_order_id,
        records=[
            {
                "internal_order_id": order.internal_order_id,
                "customer_name": order.customer_name,
                "amount": float(order.amount),
                "currency": order.currency,
                "order_status": order.order_status,
            }
        ],
        citations=citations,
    )


def _is_failed_shipment_status(status: str) -> bool:
    s = status.lower()
    return s in {"rto", "lost", "failed", "undelivered"}


def _failed_shipments_result(db: Session) -> ToolExecutionResult:
    """Deterministic failed-shipment metric."""
    shipments = crud.list_shipments(db, limit=10_000)
    failed = [s for s in shipments if _is_failed_shipment_status(s.shipment_status)]
    count = len(failed)
    shipment_ids = [s.internal_shipment_id for s in failed]

    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=shipment_ids,
        field_names=["shipment_status"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))

    # If we claim zero, cite at least one system row — use any shipment status lineage.
    if count == 0 and not citations:
        any_ship = crud.latest_provenance_for_entities(
            db,
            internal_entity_ids=[s.internal_shipment_id for s in shipments[:5]],
            field_names=["shipment_status"],
        )
        citations = provenance_rows_to_citations(any_ship)

    return ToolExecutionResult(
        metric="failed_shipments",
        value=count,
        calculation={"shipment_count": count},
        records=[
            {
                "internal_shipment_id": s.internal_shipment_id,
                "internal_order_id": s.internal_order_id,
                "shipment_status": s.shipment_status,
                "courier_name": s.courier_name,
            }
            for s in failed
        ],
        citations=citations,
    )


def get_total_revenue_data(db: Session) -> ToolExecutionResult:
    return _total_revenue_result(db)


def get_average_daily_revenue_data(db: Session, *, days: int = 30) -> ToolExecutionResult:
    return _average_daily_revenue_result(db, days=days)


def get_rto_orders_data(db: Session, *, min_amount: float = 0.0) -> ToolExecutionResult:
    return _rto_orders_result(db, min_amount=min_amount)


def get_order_by_id_data(db: Session, *, internal_order_id: str) -> ToolExecutionResult:
    return _order_by_id_result(db, internal_order_id=internal_order_id)


def get_failed_shipments_data(db: Session) -> ToolExecutionResult:
    return _failed_shipments_result(db)

def get_orders_by_id_delivered_data(db: Session, *, internal_order_id: str) -> ToolExecutionResult: 
    """Lookup delivered orders by internal_order_id."""
    stmt = (
        select(Order)
        .join(Shipment, Shipment.internal_order_id == Order.internal_order_id)
        .where(
            Order.internal_order_id == internal_order_id,
            Shipment.shipment_status == "delivered",
        )
    )
    order = db.scalars(stmt).first()
    if order is None:
        return ToolExecutionResult(
            metric="order_by_id_delivered",
            value="not_found",
            filters={"internal_order_id": internal_order_id},
            citations=[],
        )

    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[internal_order_id],
        field_names=["amount", "customer_name", "order_status"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))

    return ToolExecutionResult(
        metric="order_by_id_delivered",
        value=order.internal_order_id,
        records=[
            {
                "internal_order_id": order.internal_order_id,
                "customer_name": order.customer_name,
                "amount": float(order.amount),
                "currency": order.currency,
                "order_status": order.order_status,
            }
        ],
        citations=citations,
    )


def _as_chat_answer(metric_result: ToolExecutionResult) -> ChatAnswer:
    """Backwards-compatible wrapper for legacy endpoints expecting ChatAnswer."""
    metric = metric_result.metric
    if metric == "total_revenue":
        answer = f"Total revenue from normalized orders is {metric_result.currency} {metric_result.value}"
    elif metric == "average_daily_revenue":
        answer = (
            f"Average daily revenue for the last {metric_result.calculation.get('days', '?')} days is "
            f"{metric_result.currency} {metric_result.value}"
        )
    elif metric == "rto_orders":
        answer = f"There are {metric_result.value} orders with an RTO shipment in the normalized dataset."
    elif metric == "failed_shipments":
        answer = f"There are {metric_result.value} failed or RTO-class shipments."
    elif metric == "order_by_id":
        if metric_result.value == "not_found":
            answer = (
                f"No order found for internal_order_id="
                f"{metric_result.filters.get('internal_order_id', '<unknown>')!r}."
            )
        else:
            row = metric_result.records[0]
            answer = (
                f"Order {row['internal_order_id']}: customer={row['customer_name']}, "
                f"amount={row['currency']} {row['amount']}, status={row['order_status']}"
            )
    else:
        answer = f"{metric_result.metric}: {metric_result.value}"

    return ChatAnswer(
        answer=answer,
        citations=metric_result.citations,
    )


def get_total_revenue(db: Session) -> ChatAnswer:
    return _as_chat_answer(_total_revenue_result(db))


def get_average_daily_revenue(db: Session, *, days: int = 30) -> ChatAnswer:
    return _as_chat_answer(_average_daily_revenue_result(db, days=days))


def get_rto_orders(db: Session, *, min_amount: float = 0.0) -> ChatAnswer:
    return _as_chat_answer(_rto_orders_result(db, min_amount=min_amount))


def get_order_by_id(db: Session, internal_order_id: str) -> ChatAnswer:
    return _as_chat_answer(_order_by_id_result(db, internal_order_id=internal_order_id))


def get_failed_shipments(db: Session) -> ChatAnswer:
    return _as_chat_answer(_failed_shipments_result(db))


def assert_numeric_claims_are_cited(answer: ChatAnswer) -> None:
    """
    Guardrail for developers: chat answers that mention digits should carry citations.

    Not used in runtime hot path; available for tests or CI hooks.
    """
    if any(ch.isdigit() for ch in answer.answer) and not answer.citations:
        raise ValueError("Numeric chat answers must include at least one citation.")
