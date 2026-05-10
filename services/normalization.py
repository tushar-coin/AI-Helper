"""
Normalization layer: raw connector payloads -> universal schema + mappings + provenance.

Connectors stay dumb; this module owns all field renaming, typing, and entity resolution.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from db import crud
from services import mappings

MERCHANT_ID = os.getenv("MERCHANT_ID", "MERCH-DEMO")


def _now_sync_ts() -> datetime:
    """Wall-clock timestamp stored in DB (naive UTC for SQLite simplicity)."""
    return datetime.now(tz=UTC).replace(tzinfo=None)


def new_internal_order_id() -> str:
    return f"INT-ORD-{uuid.uuid4().hex[:10]}"


def new_internal_shipment_id() -> str:
    return f"INT-SHIP-{uuid.uuid4().hex[:10]}"


def new_internal_payment_id() -> str:
    return f"INT-PAY-{uuid.uuid4().hex[:10]}"


def _parse_dt(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if not value:
        return _now_sync_ts()
    # ISO strings from mocks: "2026-05-10T10:00:00"
    return datetime.fromisoformat(str(value))


def _shopify_order_status(raw: dict[str, Any]) -> str:
    financial = str(raw.get("financial_status") or "").lower()
    fulfillment = str(raw.get("fulfillment_status") or "").lower()
    if fulfillment == "fulfilled":
        return "fulfilled"
    if financial == "paid":
        return "paid"
    if financial == "pending":
        return "pending"
    return financial or "unknown"


def ingest_shopify_order(
    db: Session,
    raw: dict[str, Any],
    *,
    synced_at: datetime | None = None,
    merchant_id: str = MERCHANT_ID,
) -> str:
    """
    Upsert a normalized order from a Shopify-shaped payload.

    Returns the internal order id.
    """
    ts = synced_at or _now_sync_ts()
    external_id = str(raw["id"])
    source = "shopify"

    internal_id = mappings.resolve_internal_order_id(db, external_id)
    if internal_id is None:
        internal_id = new_internal_order_id()

    amount = Decimal(str(raw.get("total_price", 0)))
    currency = str(raw.get("currency") or "INR")
    customer_name = str(raw.get("customer_name") or "")
    created_at = _parse_dt(raw.get("created_at"))
    order_status = _shopify_order_status(raw)

    crud.upsert_order(
        db,
        internal_order_id=internal_id,
        merchant_id=merchant_id,
        customer_name=customer_name,
        amount=amount,
        currency=currency,
        order_status=order_status,
        created_at=created_at,
    )

    mappings.ensure_external_maps_to_internal(
        db,
        internal_entity_id=internal_id,
        entity_type=mappings.ENTITY_ORDER,
        source=source,
        external_id=external_id,
    )

    crud.record_provenance(
        db,
        internal_entity_id=internal_id,
        field_name="merchant_id",
        source_system=source,
        source_field="(sync_config)",
        source_row_id=external_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_id,
        field_name="customer_name",
        source_system=source,
        source_field="customer_name",
        source_row_id=external_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_id,
        field_name="amount",
        source_system=source,
        source_field="total_price",
        source_row_id=external_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_id,
        field_name="currency",
        source_system=source,
        source_field="currency",
        source_row_id=external_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_id,
        field_name="order_status",
        source_system=source,
        source_field="financial_status+fulfillment_status",
        source_row_id=external_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_id,
        field_name="created_at",
        source_system=source,
        source_field="created_at",
        source_row_id=external_id,
        synced_at=ts,
    )
    return internal_id


def ingest_shiprocket_shipment(
    db: Session,
    raw: dict[str, Any],
    *,
    synced_at: datetime | None = None,
) -> str:
    """Upsert shipment; resolves parent order via `linked_order_id`."""
    ts = synced_at or _now_sync_ts()
    source = "shiprocket"
    external_shipment_id = str(raw["shipment_id"])
    linked_order = str(raw["linked_order_id"])

    internal_order_id = mappings.resolve_internal_order_id(db, linked_order)
    if internal_order_id is None:
        raise ValueError(
            f"Cannot ingest shipment {external_shipment_id}: unknown order ref {linked_order}. "
            "Ingest Shopify orders first."
        )

    # Stable idempotent internal shipment key: derive from vendor id via mapping if present.
    existing_shipment_map = crud.find_internal_id_for_external(
        db,
        entity_type=mappings.ENTITY_SHIPMENT,
        external_id=external_shipment_id,
    )
    internal_shipment_id = existing_shipment_map or new_internal_shipment_id()

    status = str(raw.get("shipment_status") or "").lower()
    courier = str(raw.get("courier_name") or "")
    shipped_at = _parse_dt(raw.get("shipped_at")) if raw.get("shipped_at") else None

    crud.upsert_shipment(
        db,
        internal_shipment_id=internal_shipment_id,
        internal_order_id=internal_order_id,
        shipment_status=status,
        courier_name=courier,
        shipped_at=shipped_at,
    )

    mappings.ensure_external_maps_to_internal(
        db,
        internal_entity_id=internal_shipment_id,
        entity_type=mappings.ENTITY_SHIPMENT,
        source=source,
        external_id=external_shipment_id,
    )

    crud.record_provenance(
        db,
        internal_entity_id=internal_shipment_id,
        field_name="internal_order_id",
        source_system=source,
        source_field="linked_order_id",
        source_row_id=external_shipment_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_shipment_id,
        field_name="shipment_status",
        source_system=source,
        source_field="shipment_status",
        source_row_id=external_shipment_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_shipment_id,
        field_name="courier_name",
        source_system=source,
        source_field="courier_name",
        source_row_id=external_shipment_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_shipment_id,
        field_name="shipped_at",
        source_system=source,
        source_field="shipped_at",
        source_row_id=external_shipment_id,
        synced_at=ts,
    )
    return internal_shipment_id


def _razorpay_payment_status(raw: dict[str, Any]) -> str:
    s = str(raw.get("payment_status") or "").lower()
    if s in {"captured", "paid"}:
        return "paid"
    if s in {"authorized", "pending"}:
        return "pending"
    if s in {"failed"}:
        return "failed"
    return s or "unknown"


def ingest_razorpay_payment(
    db: Session,
    raw: dict[str, Any],
    *,
    synced_at: datetime | None = None,
) -> str:
    """Upsert payment; resolves parent order via `order_ref`."""
    ts = synced_at or _now_sync_ts()
    source = "razorpay"
    external_payment_id = str(raw["payment_id"])
    order_ref = str(raw["order_ref"])

    internal_order_id = mappings.resolve_internal_order_id(db, order_ref)
    if internal_order_id is None:
        raise ValueError(
            f"Cannot ingest payment {external_payment_id}: unknown order ref {order_ref}. "
            "Ingest Shopify orders first."
        )

    existing = crud.find_internal_id_for_external(
        db,
        entity_type=mappings.ENTITY_PAYMENT,
        external_id=external_payment_id,
    )
    internal_payment_id = existing or new_internal_payment_id()

    amount = Decimal(str(raw.get("amount", 0)))
    payment_status = _razorpay_payment_status(raw)
    payment_method = str(raw.get("payment_method") or "").lower()
    created_at = _parse_dt(raw.get("created_at"))

    crud.upsert_payment(
        db,
        internal_payment_id=internal_payment_id,
        internal_order_id=internal_order_id,
        amount=amount,
        payment_status=payment_status,
        payment_method=payment_method,
        created_at=created_at,
    )

    mappings.ensure_external_maps_to_internal(
        db,
        internal_entity_id=internal_payment_id,
        entity_type=mappings.ENTITY_PAYMENT,
        source=source,
        external_id=external_payment_id,
    )

    crud.record_provenance(
        db,
        internal_entity_id=internal_payment_id,
        field_name="internal_order_id",
        source_system=source,
        source_field="order_ref",
        source_row_id=external_payment_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_payment_id,
        field_name="amount",
        source_system=source,
        source_field="amount",
        source_row_id=external_payment_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_payment_id,
        field_name="payment_status",
        source_system=source,
        source_field="payment_status",
        source_row_id=external_payment_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_payment_id,
        field_name="payment_method",
        source_system=source,
        source_field="payment_method",
        source_row_id=external_payment_id,
        synced_at=ts,
    )
    crud.record_provenance(
        db,
        internal_entity_id=internal_payment_id,
        field_name="created_at",
        source_system=source,
        source_field="created_at",
        source_row_id=external_payment_id,
        synced_at=ts,
    )
    return internal_payment_id
