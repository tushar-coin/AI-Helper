"""CRUD helpers used by normalization and chat tools."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import EntityMapping, Order, Payment, Provenance, Shipment


def get_order(db: Session, internal_order_id: str) -> Order | None:
    return db.get(Order, internal_order_id)


def list_orders(db: Session, *, limit: int = 500) -> Sequence[Order]:
    return db.scalars(select(Order).order_by(Order.created_at.desc()).limit(limit)).all()


def list_shipments(db: Session, *, limit: int = 500) -> Sequence[Shipment]:
    return db.scalars(select(Shipment).limit(limit)).all()


def list_payments(db: Session, *, limit: int = 500) -> Sequence[Payment]:
    return db.scalars(select(Payment).limit(limit)).all()


def upsert_order(
    db: Session,
    *,
    internal_order_id: str,
    merchant_id: str,
    customer_name: str,
    amount: Decimal,
    currency: str,
    order_status: str,
    created_at: datetime,
) -> Order:
    row = db.get(Order, internal_order_id)
    if row is None:
        row = Order(internal_order_id=internal_order_id)
        db.add(row)
    row.merchant_id = merchant_id
    row.customer_name = customer_name
    row.amount = amount
    row.currency = currency
    row.order_status = order_status
    row.created_at = created_at
    return row


def upsert_shipment(
    db: Session,
    *,
    internal_shipment_id: str,
    internal_order_id: str,
    shipment_status: str,
    courier_name: str,
    shipped_at: datetime | None,
) -> Shipment:
    row = db.get(Shipment, internal_shipment_id)
    if row is None:
        row = Shipment(internal_shipment_id=internal_shipment_id)
        db.add(row)
    row.internal_order_id = internal_order_id
    row.shipment_status = shipment_status
    row.courier_name = courier_name
    row.shipped_at = shipped_at
    return row


def upsert_payment(
    db: Session,
    *,
    internal_payment_id: str,
    internal_order_id: str,
    amount: Decimal,
    payment_status: str,
    payment_method: str,
    created_at: datetime,
) -> Payment:
    row = db.get(Payment, internal_payment_id)
    if row is None:
        row = Payment(internal_payment_id=internal_payment_id)
        db.add(row)
    row.internal_order_id = internal_order_id
    row.amount = amount
    row.payment_status = payment_status
    row.payment_method = payment_method
    row.created_at = created_at
    return row


def add_mapping_if_missing(
    db: Session,
    *,
    internal_entity_id: str,
    entity_type: str,
    source: str,
    external_id: str,
) -> bool:
    """
    Insert mapping if no row exists for (entity_type, source, external_id).
    Returns True if a new row was created.
    """
    exists = db.scalar(
        select(EntityMapping.id).where(
            EntityMapping.entity_type == entity_type,
            EntityMapping.source == source,
            EntityMapping.external_id == external_id,
        )
    )
    if exists is not None:
        return False
    db.add(
        EntityMapping(
            internal_entity_id=internal_entity_id,
            entity_type=entity_type,
            source=source,
            external_id=external_id,
        )
    )
    return True


def record_provenance(
    db: Session,
    *,
    internal_entity_id: str,
    field_name: str,
    source_system: str,
    source_field: str,
    source_row_id: str,
    synced_at: datetime,
) -> None:
    """Append a provenance row (keeps history — no upsert by field)."""
    db.add(
        Provenance(
            internal_entity_id=internal_entity_id,
            field_name=field_name,
            source_system=source_system,
            source_field=source_field,
            source_row_id=source_row_id,
            synced_at=synced_at,
        )
    )


def find_internal_id_for_external(
    db: Session,
    *,
    entity_type: str,
    external_id: str,
) -> str | None:
    """Resolve canonical internal id from any known source external id."""
    row = db.scalar(
        select(EntityMapping.internal_entity_id).where(
            EntityMapping.entity_type == entity_type,
            EntityMapping.external_id == external_id,
        )
    )
    return str(row) if row is not None else None


def latest_provenance_for_entities(
    db: Session,
    *,
    internal_entity_ids: Sequence[str],
    field_names: Sequence[str] | None = None,
) -> list[Provenance]:
    """
    Fetch provenance rows for citations.

    For each (internal_entity_id, field_name) pair, returns the most recent row by id.
    """
    if not internal_entity_ids:
        return []
    stmt = select(Provenance).where(Provenance.internal_entity_id.in_(internal_entity_ids))
    if field_names:
        stmt = stmt.where(Provenance.field_name.in_(field_names))
    stmt = stmt.order_by(Provenance.id.desc())
    rows = db.scalars(stmt).all()
    # Dedupe keeping latest per (entity, field).
    seen: set[tuple[str, str]] = set()
    out: list[Provenance] = []
    for r in rows:
        key = (r.internal_entity_id, r.field_name)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out
