"""Razorpay connector — mocked raw payloads."""

from __future__ import annotations

from typing import Any

from connectors.base import BaseConnector


class RazorpayConnector(BaseConnector):
    """Payment gateway: payments reference commerce orders via ``order_ref``."""

    @property
    def source_name(self) -> str:
        return "razorpay"

    def fetch_orders(self) -> list[dict[str, Any]]:
        return []

    def fetch_shipments(self) -> list[dict[str, Any]]:
        return []

    def fetch_payments(self) -> list[dict[str, Any]]:
        return [
            {
                "payment_id": "PAY-999",
                "order_ref": "ORD-101",
                "amount": 1200,
                "payment_status": "captured",
                "payment_method": "cod",
                "created_at": "2026-05-10T10:05:00",
            },
            {
                "payment_id": "PAY-1000",
                "order_ref": "ORD-102",
                "amount": 800,
                "payment_status": "captured",
                "payment_method": "upi",
                "created_at": "2026-05-09T14:35:00",
            },
            {
                "payment_id": "PAY-1001",
                "order_ref": "ORD-103",
                "amount": 4500,
                "payment_status": "authorized",
                "payment_method": "cod",
                "created_at": "2026-05-08T09:20:00",
            },
            {
                "payment_id": "PAY-1002",
                "order_ref": "ORD-104",
                "amount": 650,
                "payment_status": "captured",
                "payment_method": "upi",
                "created_at": "2026-05-07T08:05:00",
            },
        ]
