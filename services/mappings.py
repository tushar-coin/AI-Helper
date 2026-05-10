"""
Cross-system identity: external SaaS identifiers -> internal canonical ids.

Vendors reuse the same human-visible order code (e.g. ``ORD-101``) as the bridge key
even when the row originates from Shopify, Shiprocket, or Razorpay references.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from db import crud

# Normalized entity type strings stored in `entity_mappings.entity_type`.
ENTITY_ORDER = "order"
ENTITY_SHIPMENT = "shipment"
ENTITY_PAYMENT = "payment"


def resolve_internal_order_id(db: Session, external_order_ref: str) -> str | None:
    """
    Given a commerce order reference (e.g. Shopify ``id`` / Shiprocket ``linked_order_id``),
    return the internal order id if any mapping exists.
    """
    return crud.find_internal_id_for_external(
        db,
        entity_type=ENTITY_ORDER,
        external_id=external_order_ref,
    )


def ensure_external_maps_to_internal(
    db: Session,
    *,
    internal_entity_id: str,
    entity_type: str,
    source: str,
    external_id: str,
) -> bool:
    """Idempotent mapping insert; returns True when a new mapping row was added."""
    return crud.add_mapping_if_missing(
        db,
        internal_entity_id=internal_entity_id,
        entity_type=entity_type,
        source=source,
        external_id=external_id,
    )
