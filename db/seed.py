"""
Database seeding.

On a fresh database, we run a full connector sync so normalized rows, mappings,
and provenance are populated from the same path as production ingestion.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Order
from services.sync_service import SyncService


def seed_if_empty(db: Session) -> bool:
    """
    If no orders exist, run a full sync. Returns True when sync ran.
    """
    order_count = db.scalar(select(func.count(Order.internal_order_id))) or 0
    if order_count > 0:
        return False
    SyncService().run_full_sync(db)
    return True
