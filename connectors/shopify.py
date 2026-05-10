"""Shopify connector — mocked raw payloads (no HTTP, no normalization)."""

from __future__ import annotations

from typing import Any

from connectors.base import BaseConnector


class ShopifyConnector(BaseConnector):
    """Returns Shopify-shaped order rows; shipments/payments are not native to this mock."""

    @property
    def source_name(self) -> str:
        return "shopify"

    def fetch_orders(self) -> list[dict[str, Any]]:
        # Realistic mocked payloads — field names mirror common Shopify REST shapes.
        return [
            {
                "id": "ORD-101",
                "customer_name": "Rahul",
                "total_price": 1200,
                "currency": "INR",
                "created_at": "2026-05-10T10:00:00",
                "financial_status": "paid",
                "fulfillment_status": None,
            },
            {
                "id": "ORD-102",
                "customer_name": "Priya",
                "total_price": 800,
                "currency": "INR",
                "created_at": "2026-05-09T14:30:00",
                "financial_status": "paid",
                "fulfillment_status": "fulfilled",
            },
            {
                "id": "ORD-103",
                "customer_name": "Amit",
                "total_price": 4500,
                "currency": "INR",
                "created_at": "2026-05-08T09:15:00",
                "financial_status": "pending",
                "fulfillment_status": None,
            },
            {
                "id": "ORD-104",
                "customer_name": "Neha",
                "total_price": 650,
                "currency": "INR",
                "created_at": "2026-05-07T08:00:00",
                "financial_status": "paid",
                "fulfillment_status": "fulfilled",
            },
        ]

    def fetch_shipments(self) -> list[dict[str, Any]]:
        return []

    def fetch_payments(self) -> list[dict[str, Any]]:
        return []
