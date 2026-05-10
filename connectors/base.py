"""
Abstract connector interface.

Each concrete connector returns **raw**, source-specific dict payloads.
Normalization happens in `services.normalization`, never inside connectors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Contract for fetching operational data from a SaaS source."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Stable identifier for provenance (e.g. ``\"shopify\"``)."""

    @abstractmethod
    def fetch_orders(self) -> list[dict[str, Any]]:
        """Return raw order documents as returned by (or shaped like) the vendor API."""

    @abstractmethod
    def fetch_shipments(self) -> list[dict[str, Any]]:
        """Return raw shipment documents (may be empty if the vendor has no logistics API)."""

    @abstractmethod
    def fetch_payments(self) -> list[dict[str, Any]]:
        """Return raw payment documents (may be empty for some vendors)."""
