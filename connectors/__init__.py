"""SaaS connector package: raw source payloads only (no normalization here)."""

from connectors.base import BaseConnector
from connectors.shopify import ShopifyConnector
from connectors.shiprocket import ShiprocketConnector
from connectors.razorpay import RazorpayConnector

__all__ = [
    "BaseConnector",
    "ShopifyConnector",
    "ShiprocketConnector",
    "RazorpayConnector",
]
