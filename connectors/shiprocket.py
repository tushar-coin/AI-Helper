"""Shiprocket connector — mocked raw payloads."""

from __future__ import annotations

from typing import Any

from connectors.base import BaseConnector


class ShiprocketConnector(BaseConnector):
    """Logistics-focused vendor: shipments link to commerce orders via ``linked_order_id``."""

    @property
    def source_name(self) -> str:
        return "shiprocket"

    def fetch_orders(self) -> list[dict[str, Any]]:
        return []

    def fetch_shipments(self) -> list[dict[str, Any]]:
        return [
            {
                "shipment_id": "SHIP-778",
                "linked_order_id": "ORD-101",
                "shipment_status": "RTO",
                "courier_name": "Delhivery",
                "shipped_at": "2026-05-11T08:00:00",
            },
            {
                "shipment_id": "SHIP-779",
                "linked_order_id": "ORD-102",
                "shipment_status": "delivered",
                "courier_name": "Blue Dart",
                "shipped_at": "2026-05-10T16:00:00",
            },
            {
                "shipment_id": "SHIP-780",
                "linked_order_id": "ORD-103",
                "shipment_status": "RTO",
                "courier_name": "Delhivery",
                "shipped_at": "2026-05-09T11:00:00",
            },
            {
                "shipment_id": "SHIP-781",
                "linked_order_id": "ORD-104",
                "shipment_status": "lost",
                "courier_name": "XpressBees",
                "shipped_at": "2026-05-07T10:00:00",
            },
        ]

    def fetch_payments(self) -> list[dict[str, Any]]:
        return []
