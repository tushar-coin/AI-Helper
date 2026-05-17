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
from db.models import Order, Payment, Shipment
from db.schema import ChatAnswer, Citation, ToolExecutionResult
from services import mappings
from services.provenance import merge_citations_unique, provenance_rows_to_citations


def _resolve_order_identifier(db: Session, order_id_or_ref: str) -> str | None:
    """Resolve internal INT-ORD ids and mapped external order refs like ORD-101."""
    value = str(order_id_or_ref).strip()
    if not value:
        return None
    if value.upper().startswith("INT-ORD-"):
        return value
    return mappings.resolve_internal_order_id(db, value)


def _resolve_shipment_identifier(db: Session, shipment_id_or_ref: str) -> str | None:
    """Resolve internal INT-SHIP ids and mapped external shipment ids like SHIP-778."""
    value = str(shipment_id_or_ref).strip()
    if not value:
        return None
    if value.upper().startswith("INT-SHIP-"):
        return value
    return crud.find_internal_id_for_external(
        db,
        entity_type=mappings.ENTITY_SHIPMENT,
        external_id=value,
    )


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


def _orders_with_citations(
    db: Session,
    orders: list[Order],
    *,
    field_names: list[str],
    metric: str,
    value: int | float | str | dict | list,
    filters: dict | None = None,
    calculation: dict | None = None,
) -> ToolExecutionResult:
    order_ids = [order.internal_order_id for order in orders]
    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=order_ids,
        field_names=field_names,
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))
    return ToolExecutionResult(
        metric=metric,
        value=value,
        calculation=calculation or {},
        filters=filters or {},
        records=[
            {
                "internal_order_id": order.internal_order_id,
                "customer_name": order.customer_name,
                "amount": float(order.amount),
                "currency": order.currency,
                "order_status": order.order_status,
                "created_at": order.created_at.isoformat(),
            }
            for order in orders
        ],
        citations=citations,
    )


def _order_status_breakdown_result(db: Session) -> ToolExecutionResult:
    """Count orders by normalized order_status."""
    orders = list(crud.list_orders(db, limit=10_000))
    breakdown: dict[str, int] = {}
    for order in orders:
        breakdown[order.order_status] = breakdown.get(order.order_status, 0) + 1
    return _orders_with_citations(
        db,
        orders,
        field_names=["order_status"],
        metric="order_status_breakdown",
        value=breakdown,
        calculation={"order_count": len(orders)},
    )


def _orders_by_status_result(
    db: Session,
    *,
    status: str,
    min_amount: float = 0.0,
) -> ToolExecutionResult:
    """Return orders matching a normalized order status and optional amount threshold."""
    normalized_status = str(status).lower().strip()
    threshold = Decimal(str(min_amount))
    orders = db.scalars(
        select(Order).where(Order.order_status == normalized_status).order_by(Order.created_at.desc())
    ).all()
    if threshold > 0:
        orders = [order for order in orders if Decimal(order.amount) >= threshold]
    return _orders_with_citations(
        db,
        list(orders),
        field_names=["order_status", "amount"],
        metric="orders_by_status",
        value=len(orders),
        filters={"status": normalized_status, "min_amount": float(threshold)},
        calculation={"order_count": len(orders)},
    )


def _customer_order_summary_result(db: Session, *, customer_name: str) -> ToolExecutionResult:
    """Summarize orders for an exact customer name match."""
    name = str(customer_name).strip()
    orders = db.scalars(
        select(Order).where(Order.customer_name == name).order_by(Order.created_at.desc())
    ).all()
    total = sum(Decimal(order.amount) for order in orders)
    result = _orders_with_citations(
        db,
        list(orders),
        field_names=["customer_name", "amount", "order_status"],
        metric="customer_order_summary",
        value=float(total),
        filters={"customer_name": name},
        calculation={"order_count": len(orders), "total_revenue": float(total)},
    )
    result.currency = orders[0].currency if orders else "INR"
    return result


def _shipment_status_breakdown_result(db: Session) -> ToolExecutionResult:
    """Count shipments by normalized shipment_status."""
    shipments = list(crud.list_shipments(db, limit=10_000))
    breakdown: dict[str, int] = {}
    for shipment in shipments:
        breakdown[shipment.shipment_status] = breakdown.get(shipment.shipment_status, 0) + 1
    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[shipment.internal_shipment_id for shipment in shipments],
        field_names=["shipment_status"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))
    return ToolExecutionResult(
        metric="shipment_status_breakdown",
        value=breakdown,
        calculation={"shipment_count": len(shipments)},
        records=[
            {
                "internal_shipment_id": shipment.internal_shipment_id,
                "internal_order_id": shipment.internal_order_id,
                "shipment_status": shipment.shipment_status,
                "courier_name": shipment.courier_name,
            }
            for shipment in shipments
        ],
        citations=citations,
    )


def _shipments_by_status_result(db: Session, *, status: str) -> ToolExecutionResult:
    """Return shipments for one normalized shipment status."""
    normalized_status = str(status).lower().strip()
    shipments = db.scalars(
        select(Shipment).where(Shipment.shipment_status == normalized_status)
    ).all()
    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[shipment.internal_shipment_id for shipment in shipments],
        field_names=["shipment_status", "courier_name"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))
    return ToolExecutionResult(
        metric="shipments_by_status",
        value=len(shipments),
        filters={"status": normalized_status},
        calculation={"shipment_count": len(shipments)},
        records=[
            {
                "internal_shipment_id": shipment.internal_shipment_id,
                "internal_order_id": shipment.internal_order_id,
                "shipment_status": shipment.shipment_status,
                "courier_name": shipment.courier_name,
                "shipped_at": shipment.shipped_at.isoformat() if shipment.shipped_at else None,
            }
            for shipment in shipments
        ],
        citations=citations,
    )


def _shipment_by_id_result(db: Session, *, shipment_id: str) -> ToolExecutionResult:
    """Lookup one shipment by internal id or external shipment id."""
    requested_shipment_id = str(shipment_id).strip()
    resolved_shipment_id = _resolve_shipment_identifier(db, requested_shipment_id)
    if resolved_shipment_id is None:
        return ToolExecutionResult(
            metric="shipment_by_id",
            value="not_found",
            filters={
                "shipment_id": requested_shipment_id,
                "resolved_internal_shipment_id": None,
            },
            citations=[],
        )

    shipment = db.get(Shipment, resolved_shipment_id)
    if shipment is None:
        return ToolExecutionResult(
            metric="shipment_by_id",
            value="not_found",
            filters={
                "shipment_id": requested_shipment_id,
                "resolved_internal_shipment_id": resolved_shipment_id,
            },
            citations=[],
        )

    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[resolved_shipment_id],
        field_names=["internal_order_id", "shipment_status", "courier_name", "shipped_at"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))
    return ToolExecutionResult(
        metric="shipment_by_id",
        value=resolved_shipment_id,
        filters={
            "shipment_id": requested_shipment_id,
            "resolved_internal_shipment_id": resolved_shipment_id,
        },
        calculation={"shipment_count": 1},
        records=[
            {
                "internal_shipment_id": shipment.internal_shipment_id,
                "internal_order_id": shipment.internal_order_id,
                "shipment_status": shipment.shipment_status,
                "courier_name": shipment.courier_name,
                "shipped_at": shipment.shipped_at.isoformat() if shipment.shipped_at else None,
            }
        ],
        citations=citations,
    )


def _shipments_for_order_result(db: Session, *, order_id: str) -> ToolExecutionResult:
    """Return shipments linked to one internal order id or external order ref."""
    requested_order_id = str(order_id).strip()
    resolved_order_id = _resolve_order_identifier(db, requested_order_id)
    if resolved_order_id is None:
        return ToolExecutionResult(
            metric="shipments_for_order",
            value="not_found",
            filters={"order_id": requested_order_id, "resolved_internal_order_id": None},
            citations=[],
        )

    shipments = db.scalars(
        select(Shipment).where(Shipment.internal_order_id == resolved_order_id)
    ).all()
    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[shipment.internal_shipment_id for shipment in shipments],
        field_names=["internal_order_id", "shipment_status", "courier_name", "shipped_at"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))
    return ToolExecutionResult(
        metric="shipments_for_order",
        value=len(shipments),
        filters={
            "order_id": requested_order_id,
            "resolved_internal_order_id": resolved_order_id,
        },
        calculation={"shipment_count": len(shipments)},
        records=[
            {
                "internal_shipment_id": shipment.internal_shipment_id,
                "internal_order_id": shipment.internal_order_id,
                "shipment_status": shipment.shipment_status,
                "courier_name": shipment.courier_name,
                "shipped_at": shipment.shipped_at.isoformat() if shipment.shipped_at else None,
            }
            for shipment in shipments
        ],
        citations=citations,
    )


def _payment_status_breakdown_result(db: Session) -> ToolExecutionResult:
    """Count payments by normalized payment_status."""
    payments = list(crud.list_payments(db, limit=10_000))
    breakdown: dict[str, int] = {}
    for payment in payments:
        breakdown[payment.payment_status] = breakdown.get(payment.payment_status, 0) + 1
    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[payment.internal_payment_id for payment in payments],
        field_names=["payment_status"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))
    return ToolExecutionResult(
        metric="payment_status_breakdown",
        value=breakdown,
        calculation={"payment_count": len(payments)},
        records=[
            {
                "internal_payment_id": payment.internal_payment_id,
                "internal_order_id": payment.internal_order_id,
                "amount": float(payment.amount),
                "payment_status": payment.payment_status,
                "payment_method": payment.payment_method,
            }
            for payment in payments
        ],
        citations=citations,
    )


def _payments_by_status_result(db: Session, *, status: str) -> ToolExecutionResult:
    """Return payments for one normalized payment status."""
    normalized_status = str(status).lower().strip()
    payments = db.scalars(
        select(Payment).where(Payment.payment_status == normalized_status)
    ).all()
    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[payment.internal_payment_id for payment in payments],
        field_names=["payment_status", "amount"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))
    total = sum(Decimal(payment.amount) for payment in payments)
    return ToolExecutionResult(
        metric="payments_by_status",
        value=len(payments),
        currency="INR",
        filters={"status": normalized_status},
        calculation={"payment_count": len(payments), "total_amount": float(total)},
        records=[
            {
                "internal_payment_id": payment.internal_payment_id,
                "internal_order_id": payment.internal_order_id,
                "amount": float(payment.amount),
                "payment_status": payment.payment_status,
                "payment_method": payment.payment_method,
            }
            for payment in payments
        ],
        citations=citations,
    )


def _payment_method_breakdown_result(db: Session) -> ToolExecutionResult:
    """Count and sum payments by payment_method."""
    payments = list(crud.list_payments(db, limit=10_000))
    breakdown: dict[str, dict[str, int | float]] = {}
    for payment in payments:
        row = breakdown.setdefault(payment.payment_method, {"count": 0, "amount": 0.0})
        row["count"] = int(row["count"]) + 1
        row["amount"] = float(row["amount"]) + float(payment.amount)
    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[payment.internal_payment_id for payment in payments],
        field_names=["payment_method", "amount"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))
    return ToolExecutionResult(
        metric="payment_method_breakdown",
        value=breakdown,
        currency="INR",
        calculation={"payment_count": len(payments)},
        records=[
            {
                "internal_payment_id": payment.internal_payment_id,
                "internal_order_id": payment.internal_order_id,
                "amount": float(payment.amount),
                "payment_status": payment.payment_status,
                "payment_method": payment.payment_method,
            }
            for payment in payments
        ],
        citations=citations,
    )


def _orders_by_payment_method_result(db: Session, *, payment_method: str) -> ToolExecutionResult:
    """Return orders whose payment used a given normalized payment_method."""
    normalized_method = str(payment_method).lower().strip()
    orders = db.scalars(
        select(Order)
        .join(Payment, Payment.internal_order_id == Order.internal_order_id)
        .where(Payment.payment_method == normalized_method)
        .distinct()
    ).all()
    order_ids = [order.internal_order_id for order in orders]
    payments = db.scalars(
        select(Payment).where(
            Payment.internal_order_id.in_(order_ids),
            Payment.payment_method == normalized_method,
        )
    ).all()
    prov_orders = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=order_ids,
        field_names=["amount", "customer_name"],
    )
    prov_payments = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[payment.internal_payment_id for payment in payments],
        field_names=["payment_method"],
    )
    citations = merge_citations_unique(
        provenance_rows_to_citations(list(prov_orders) + list(prov_payments))
    )
    total = sum(Decimal(order.amount) for order in orders)
    return ToolExecutionResult(
        metric="orders_by_payment_method",
        value=len(orders),
        currency=orders[0].currency if orders else "INR",
        filters={"payment_method": normalized_method},
        calculation={"order_count": len(orders), "total_revenue": float(total)},
        records=[
            {
                "internal_order_id": order.internal_order_id,
                "customer_name": order.customer_name,
                "amount": float(order.amount),
                "currency": order.currency,
                "order_status": order.order_status,
            }
            for order in orders
        ],
        citations=citations,
    )


def _order_timeline_result(db: Session, *, order_id: str) -> ToolExecutionResult:
    """Return order, shipment, and payment events for one order identifier."""
    requested_order_id = str(order_id).strip()
    resolved_order_id = _resolve_order_identifier(db, requested_order_id)
    if resolved_order_id is None:
        return ToolExecutionResult(
            metric="order_timeline",
            value="not_found",
            filters={"order_id": requested_order_id, "resolved_internal_order_id": None},
            citations=[],
        )
    order = crud.get_order(db, resolved_order_id)
    if order is None:
        return ToolExecutionResult(
            metric="order_timeline",
            value="not_found",
            filters={"order_id": requested_order_id, "resolved_internal_order_id": resolved_order_id},
            citations=[],
        )
    shipments = db.scalars(select(Shipment).where(Shipment.internal_order_id == resolved_order_id)).all()
    payments = db.scalars(select(Payment).where(Payment.internal_order_id == resolved_order_id)).all()
    entity_ids = [resolved_order_id]
    entity_ids.extend(shipment.internal_shipment_id for shipment in shipments)
    entity_ids.extend(payment.internal_payment_id for payment in payments)
    prov = crud.latest_provenance_for_entities(db, internal_entity_ids=entity_ids)
    citations = merge_citations_unique(provenance_rows_to_citations(prov))
    records = [
        {
            "event_type": "order_created",
            "timestamp": order.created_at.isoformat(),
            "internal_order_id": order.internal_order_id,
            "status": order.order_status,
            "amount": float(order.amount),
            "currency": order.currency,
        }
    ]
    records.extend(
        {
            "event_type": "shipment",
            "timestamp": shipment.shipped_at.isoformat() if shipment.shipped_at else None,
            "internal_shipment_id": shipment.internal_shipment_id,
            "internal_order_id": shipment.internal_order_id,
            "status": shipment.shipment_status,
            "courier_name": shipment.courier_name,
        }
        for shipment in shipments
    )
    records.extend(
        {
            "event_type": "payment",
            "timestamp": payment.created_at.isoformat(),
            "internal_payment_id": payment.internal_payment_id,
            "internal_order_id": payment.internal_order_id,
            "status": payment.payment_status,
            "payment_method": payment.payment_method,
            "amount": float(payment.amount),
        }
        for payment in payments
    )
    return ToolExecutionResult(
        metric="order_timeline",
        value=resolved_order_id,
        filters={"order_id": requested_order_id, "resolved_internal_order_id": resolved_order_id},
        calculation={"event_count": len(records)},
        records=records,
        citations=citations,
    )


def _revenue_for_order_ids_result(db: Session, *, order_ids: list[str]) -> ToolExecutionResult:
    """Deterministic revenue aggregate for a selected order cohort."""
    requested_order_ids = list(dict.fromkeys(str(order_id).strip() for order_id in order_ids if str(order_id).strip()))
    resolved_order_ids = [
        resolved
        for requested in requested_order_ids
        if (resolved := _resolve_order_identifier(db, requested)) is not None
    ]
    resolved_order_ids = list(dict.fromkeys(resolved_order_ids))
    if not resolved_order_ids:
        return ToolExecutionResult(
            metric="revenue_for_order_ids",
            value=0,
            currency="INR",
            calculation={"order_count": 0},
            filters={"order_ids": requested_order_ids, "resolved_internal_order_ids": []},
            citations=[],
        )

    orders = db.scalars(
        select(Order).where(Order.internal_order_id.in_(resolved_order_ids))
    ).all()
    total = sum(Decimal(order.amount) for order in orders)
    found_order_ids = [order.internal_order_id for order in orders]
    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=found_order_ids,
        field_names=["amount"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))

    return ToolExecutionResult(
        metric="revenue_for_order_ids",
        value=float(total),
        currency=orders[0].currency if orders else "INR",
        calculation={"order_count": len(orders)},
        filters={
            "order_ids": requested_order_ids,
            "resolved_internal_order_ids": resolved_order_ids,
        },
        records=[
            {
                "internal_order_id": order.internal_order_id,
                "amount": float(order.amount),
                "currency": order.currency,
            }
            for order in orders
        ],
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
    requested_order_id = str(internal_order_id).strip()
    resolved_order_id = _resolve_order_identifier(db, requested_order_id)
    if resolved_order_id is None:
        return ToolExecutionResult(
            metric="order_by_id",
            value="not_found",
            filters={
                "internal_order_id": requested_order_id,
                "resolved_internal_order_id": None,
            },
            citations=[],
        )

    order = crud.get_order(db, resolved_order_id)
    if order is None:
        return ToolExecutionResult(
            metric="order_by_id",
            value="not_found",
            filters={
                "internal_order_id": requested_order_id,
                "resolved_internal_order_id": resolved_order_id,
            },
            citations=[],
        )

    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[resolved_order_id],
        field_names=["amount", "customer_name", "order_status"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))

    return ToolExecutionResult(
        metric="order_by_id",
        value=order.internal_order_id,
        filters={
            "internal_order_id": requested_order_id,
            "resolved_internal_order_id": resolved_order_id,
        },
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


def get_order_status_breakdown_data(db: Session) -> ToolExecutionResult:
    return _order_status_breakdown_result(db)


def get_orders_by_status_data(
    db: Session,
    *,
    status: str,
    min_amount: float = 0.0,
) -> ToolExecutionResult:
    return _orders_by_status_result(db, status=status, min_amount=min_amount)


def get_customer_order_summary_data(db: Session, *, customer_name: str) -> ToolExecutionResult:
    return _customer_order_summary_result(db, customer_name=customer_name)


def get_shipment_status_breakdown_data(db: Session) -> ToolExecutionResult:
    return _shipment_status_breakdown_result(db)


def get_shipments_by_status_data(db: Session, *, status: str) -> ToolExecutionResult:
    return _shipments_by_status_result(db, status=status)


def get_shipment_by_id_data(db: Session, *, shipment_id: str) -> ToolExecutionResult:
    return _shipment_by_id_result(db, shipment_id=shipment_id)


def get_shipments_for_order_data(db: Session, *, order_id: str) -> ToolExecutionResult:
    return _shipments_for_order_result(db, order_id=order_id)


def get_payment_status_breakdown_data(db: Session) -> ToolExecutionResult:
    return _payment_status_breakdown_result(db)


def get_payments_by_status_data(db: Session, *, status: str) -> ToolExecutionResult:
    return _payments_by_status_result(db, status=status)


def get_payment_method_breakdown_data(db: Session) -> ToolExecutionResult:
    return _payment_method_breakdown_result(db)


def get_orders_by_payment_method_data(
    db: Session,
    *,
    payment_method: str,
) -> ToolExecutionResult:
    return _orders_by_payment_method_result(db, payment_method=payment_method)


def get_order_timeline_data(db: Session, *, order_id: str) -> ToolExecutionResult:
    return _order_timeline_result(db, order_id=order_id)


def get_revenue_for_order_ids_data(db: Session, *, order_ids: list[str]) -> ToolExecutionResult:
    return _revenue_for_order_ids_result(db, order_ids=order_ids)


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
    requested_order_id = str(internal_order_id).strip()
    resolved_order_id = _resolve_order_identifier(db, requested_order_id)
    if resolved_order_id is None:
        return ToolExecutionResult(
            metric="order_by_id_delivered",
            value="not_found",
            filters={
                "internal_order_id": requested_order_id,
                "resolved_internal_order_id": None,
            },
            citations=[],
        )

    stmt = (
        select(Order)
        .join(Shipment, Shipment.internal_order_id == Order.internal_order_id)
        .where(
            Order.internal_order_id == resolved_order_id,
            Shipment.shipment_status == "delivered",
        )
    )
    order = db.scalars(stmt).first()
    if order is None:
        return ToolExecutionResult(
            metric="order_by_id_delivered",
            value="not_found",
            filters={
                "internal_order_id": requested_order_id,
                "resolved_internal_order_id": resolved_order_id,
            },
            citations=[],
        )

    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[resolved_order_id],
        field_names=["amount", "customer_name", "order_status"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))

    return ToolExecutionResult(
        metric="order_by_id_delivered",
        value=order.internal_order_id,
        filters={
            "internal_order_id": requested_order_id,
            "resolved_internal_order_id": resolved_order_id,
        },
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
    elif metric == "revenue_for_order_ids":
        answer = (
            f"Revenue for the selected {metric_result.calculation.get('order_count', 0)} orders is "
            f"{metric_result.currency} {metric_result.value}"
        )
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


def get_revenue_for_order_ids(db: Session, *, order_ids: list[str]) -> ChatAnswer:
    return _as_chat_answer(_revenue_for_order_ids_result(db, order_ids=order_ids))


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
