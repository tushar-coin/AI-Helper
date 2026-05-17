from connectors.razorpay import RazorpayConnector
from connectors.shiprocket import ShiprocketConnector
from connectors.shopify import ShopifyConnector


def test_shopify_connector_returns_raw_orders_only():
    connector = ShopifyConnector()

    orders = connector.fetch_orders()

    assert connector.source_name == "shopify"
    assert len(orders) == 4
    assert connector.fetch_shipments() == []
    assert connector.fetch_payments() == []
    assert orders[0] == {
        "id": "ORD-101",
        "customer_name": "Rahul",
        "total_price": 1200,
        "currency": "INR",
        "created_at": "2026-05-10T10:00:00",
        "financial_status": "paid",
        "fulfillment_status": None,
    }


def test_shiprocket_connector_returns_raw_shipments_only():
    connector = ShiprocketConnector()

    shipments = connector.fetch_shipments()

    assert connector.source_name == "shiprocket"
    assert connector.fetch_orders() == []
    assert len(shipments) == 4
    assert connector.fetch_payments() == []
    assert shipments[0]["shipment_id"] == "SHIP-778"
    assert shipments[0]["linked_order_id"] == "ORD-101"
    assert shipments[0]["shipment_status"] == "RTO"


def test_razorpay_connector_returns_raw_payments_only():
    connector = RazorpayConnector()

    payments = connector.fetch_payments()

    assert connector.source_name == "razorpay"
    assert connector.fetch_orders() == []
    assert connector.fetch_shipments() == []
    assert len(payments) == 4
    assert payments[0]["payment_id"] == "PAY-999"
    assert payments[0]["order_ref"] == "ORD-101"
    assert payments[0]["payment_status"] == "captured"
