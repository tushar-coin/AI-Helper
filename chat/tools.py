"""
Chat tool layer.

**Rule:** any numeric answer must include citations derived from `provenance` rows
so downstream LLMs cannot present uncited figures.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db import crud
from db.models import Order, Shipment
from db.schema import ChatAnswer
from services.provenance import merge_citations_unique, provenance_rows_to_citations


def get_total_revenue(db: Session) -> ChatAnswer:
    """Sum normalized order amounts (not payments), citing each order's `amount` lineage."""
    orders = crud.list_orders(db, limit=10_000)
    if not orders:
        return ChatAnswer(
            answer="Total revenue cannot be computed from orders because there are no normalized order rows yet.",
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
    return ChatAnswer(
        answer=f"Total revenue from normalized orders is {currency} {total}",
        citations=citations,
    )


def get_rto_orders(db: Session) -> ChatAnswer:
    """Orders that currently have at least one RTO shipment."""
    stmt = (
        select(Order)
        .join(Shipment, Shipment.internal_order_id == Order.internal_order_id)
        .where(Shipment.shipment_status == "rto")
        .distinct()
    )
    orders = db.scalars(stmt).all()
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

    return ChatAnswer(
        answer=f"There are {count} orders with an RTO shipment in the normalized dataset.",
        citations=citations,
    )


def get_order_by_id(db: Session, internal_order_id: str) -> ChatAnswer:
    """Fetch one order; cite amount and identity fields."""
    order = crud.get_order(db, internal_order_id)
    if order is None:
        return ChatAnswer(
            answer=f"No order found for internal_order_id={internal_order_id!r}.",
            citations=[],
        )

    prov = crud.latest_provenance_for_entities(
        db,
        internal_entity_ids=[internal_order_id],
        field_names=["amount", "customer_name", "order_status"],
    )
    citations = merge_citations_unique(provenance_rows_to_citations(prov))

    return ChatAnswer(
        answer=(
            f"Order {order.internal_order_id}: customer={order.customer_name!s}, "
            f"amount={order.currency} {order.amount}, status={order.order_status}"
        ),
        citations=citations,
    )


def _is_failed_shipment_status(status: str) -> bool:
    s = status.lower()
    return s in {"rto", "lost", "failed", "undelivered"}


def get_failed_shipments(db: Session) -> ChatAnswer:
    """Shipments in terminal failure-like states (RTO, lost, failed, undelivered)."""
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

    return ChatAnswer(
        answer=f"There are {count} failed or RTO-class shipments.",
        citations=citations,
    )


def assert_numeric_claims_are_cited(answer: ChatAnswer) -> None:
    """
    Guardrail for developers: chat answers that mention digits should carry citations.

    Not used in runtime hot path; available for tests or CI hooks.
    """
    if any(ch.isdigit() for ch in answer.answer) and not answer.citations:
        raise ValueError("Numeric chat answers must include at least one citation.")
