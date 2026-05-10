You are a senior Python backend engineer.

Create a production-style v0 architecture for an AI-powered D2C operations assistant system.

The project goal:
Build a backend system that connects to multiple SaaS platforms (Shopify, Shiprocket, Razorpay), normalizes business data into a universal schema, stores provenance information, and exposes the data to AI chat agents and autonomous monitoring agents.

Use Python.

Tech stack:
- FastAPI
- SQLite
- SQLAlchemy
- Pydantic
- Modular architecture
- Clean code structure
- Type hints everywhere

Create the following project structure:

project_root/
│
├── connectors/
│   ├── base.py
│   ├── shopify.py
│   ├── shiprocket.py
│   └── razorpay.py
│
├── db/
│   ├── database.py
│   ├── models.py
│   ├── schema.py
│   └── seed.py
│
├── agents/
│   └── rto_agent.py
│
├── chat/
│   └── tools.py
│
├── services/
│   ├── normalization.py
│   ├── provenance.py
│   └── mappings.py
│
├── api/
│   └── main.py
│
├── data/
│   └── app.db
│
├── requirements.txt
├── README.md
└── .env

System requirements:

1. CONNECTOR ABSTRACTION

Create a BaseConnector abstract class with methods like:
- fetch_orders()
- fetch_shipments()
- fetch_payments()

Each connector should inherit from BaseConnector.

Create:
- ShopifyConnector
- ShiprocketConnector
- RazorpayConnector

For now use mocked sample data instead of real APIs.

Each connector should return raw source-specific JSON.

Example:
Shopify returns:
{
  "id": "ORD-101",
  "total_price": 1200
}

Shiprocket returns:
{
  "shipment_id": "SHIP-778",
  "linked_order_id": "ORD-101"
}

Razorpay returns:
{
  "payment_id": "PAY-999",
  "order_ref": "ORD-101"
}

2. UNIVERSAL NORMALIZED SCHEMA

Create normalized internal tables using SQLAlchemy:

orders
- internal_order_id
- merchant_id
- customer_name
- amount
- currency
- status
- created_at

entity_mappings
- id
- internal_order_id
- source
- external_id

provenance
- id
- internal_order_id
- field_name
- source_system
- source_field
- source_row_id

3. NORMALIZATION SERVICE

Create a normalization layer that:
- converts connector-specific payloads into universal schema
- generates internal IDs
- inserts mappings
- inserts provenance rows

4. PROVENANCE

Every normalized field should store where it came from.

Example:
amount came from Shopify.total_price
status came from Shiprocket.shipment_status

5. RTO AGENT

Create a simple autonomous agent:
agents/rto_agent.py

Behavior:
- scans normalized orders
- finds RTO orders above ₹1000
- generates recommendation:
  “Pause COD for high-RTO zones”

Do NOT send notifications.
Only generate:
- reasoning
- recommendation
- run logs

6. CHAT TOOL LAYER

Create chat/tools.py with functions:
- get_total_revenue()
- get_rto_orders()
- get_order_by_id()

Every response should include provenance/citations.

Example:
{
  "answer": "Revenue is ₹2000",
  "citations": [
    {
      "internal_order_id": "INT-1",
      "source": "shopify",
      "source_row_id": "ORD-101"
    }
  ]
}

7. FASTAPI

Create a minimal API with endpoints:
- /sync
- /orders
- /agent/run
- /chat/revenue

8. DATABASE

Use SQLite.

Auto-create tables on startup.

Seed database with sample data.

9. README

Generate a high-quality README explaining:
- architecture
- connector abstraction
- normalization
- provenance
- mappings
- agent design
- scale considerations

10. CODE QUALITY

Requirements:
- modular
- beginner-readable
- strongly commented
- scalable structure
- no unnecessary complexity

Generate COMPLETE code for all files.

Do not skip implementations.

Do not leave TODO placeholders.

Use realistic mock data and realistic normalization flow.