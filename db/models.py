"""
Normalized operational schema.

Relationships mirror the business graph: orders have many shipments and payments.
`entity_mappings` and `provenance` support cross-system identity and AI citations.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class Order(Base):
    """Canonical commerce order (internal id is the stable key for agents and chat tools)."""

    __tablename__ = "orders"

    internal_order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(8))
    order_status: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))

    shipments: Mapped[list["Shipment"]] = relationship(
        "Shipment",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class Shipment(Base):
    """Normalized logistics row, always tied to one internal order."""

    __tablename__ = "shipments"

    internal_shipment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    internal_order_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("orders.internal_order_id", ondelete="CASCADE"),
        index=True,
    )
    shipment_status: Mapped[str] = mapped_column(String(64))
    courier_name: Mapped[str] = mapped_column(String(128))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="shipments")


class Payment(Base):
    """Normalized payment row, tied to one internal order."""

    __tablename__ = "payments"

    internal_payment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    internal_order_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("orders.internal_order_id", ondelete="CASCADE"),
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    payment_status: Mapped[str] = mapped_column(String(64))
    payment_method: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))

    order: Mapped["Order"] = relationship("Order", back_populates="payments")


class EntityMapping(Base):
    """
    Maps an external vendor id to our canonical internal entity id.

    Example rows for one logical order:
    - (INT-ORD-abc, order, shopify, ORD-101)
    - (INT-ORD-abc, order, shiprocket, ORD-101)  # same commerce id reused as link key
    - (INT-PAY-xyz, payment, razorpay, PAY-999)
    """

    __tablename__ = "entity_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    internal_entity_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(128), index=True)


class Provenance(Base):
    """
    Field-level lineage: which source field populated a normalized column.

    Used to build citation payloads for chat and auditing.
    """

    __tablename__ = "provenance"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    internal_entity_id: Mapped[str] = mapped_column(String(64), index=True)
    field_name: Mapped[str] = mapped_column(String(128))
    source_system: Mapped[str] = mapped_column(String(32))
    source_field: Mapped[str] = mapped_column(String(128))
    source_row_id: Mapped[str] = mapped_column(String(128))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
