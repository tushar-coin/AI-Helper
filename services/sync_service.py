"""
Sync orchestration: pull raw rows from all connectors, normalize, persist.

Order of operations matters: Shopify orders first, then logistics and payments
that reference storefront order codes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from connectors.razorpay import RazorpayConnector
from connectors.shiprocket import ShiprocketConnector
from connectors.shopify import ShopifyConnector
from db.models import EntityMapping, Provenance
from db.schema import SyncSummary
from services import normalization


class SyncService:
    """Coordinates connector reads and the normalization pipeline."""

    def __init__(self) -> None:
        self.shopify = ShopifyConnector()
        self.shiprocket = ShiprocketConnector()
        self.razorpay = RazorpayConnector()

    def run_full_sync(self, db: Session) -> SyncSummary:
        synced_at = datetime.now(tz=UTC).replace(tzinfo=None)

        map_before = db.scalar(select(func.count(EntityMapping.id))) or 0
        prov_before = db.scalar(select(func.count(Provenance.id))) or 0

        orders_count = 0
        for raw in self.shopify.fetch_orders():
            normalization.ingest_shopify_order(db, raw, synced_at=synced_at)
            orders_count += 1

        shipments_count = 0
        for raw in self.shiprocket.fetch_shipments():
            normalization.ingest_shiprocket_shipment(db, raw, synced_at=synced_at)
            shipments_count += 1

        payments_count = 0
        for raw in self.razorpay.fetch_payments():
            normalization.ingest_razorpay_payment(db, raw, synced_at=synced_at)
            payments_count += 1

        db.commit()

        map_after = db.scalar(select(func.count(EntityMapping.id))) or 0
        prov_after = db.scalar(select(func.count(Provenance.id))) or 0

        return SyncSummary(
            orders_upserted=orders_count,
            shipments_upserted=shipments_count,
            payments_upserted=payments_count,
            mappings_touched=max(0, map_after - map_before),
            provenance_rows_written=max(0, prov_after - prov_before),
        )
