You are a senior backend and data platform engineer.

Build a production-style v0 architecture for an AI-powered D2C operations assistant.

The system should connect to multiple SaaS tools, normalize their data into a universal schema, maintain provenance/citation tracking, and expose the data to AI chat tools and autonomous agents.

The goal is NOT just CRUD APIs.
The goal is:
- connector abstraction
- normalization
- provenance
- cross-system identity mapping
- AI reasoning readiness
- scalable architecture

Use Python.

Tech stack:
- FastAPI
- SQLite
- SQLAlchemy
- Pydantic
- Modular architecture
- Strong typing
- Clean code
- Beginner-readable implementation

--------------------------------------------------
PROJECT STRUCTURE
--------------------------------------------------

Create the following structure:

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
│   ├── crud.py
│   └── seed.py
│
├── services/
│   ├── normalization.py
│   ├── provenance.py
│   ├── mappings.py
│   └── sync_service.py
│
├── agents/
│   └── rto_agent.py
│
├── chat/
│   └── tools.py
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

--------------------------------------------------
SYSTEM OVERVIEW
--------------------------------------------------

The platform integrates data from:
- Shopify (orders)
- Shiprocket (shipments)
- Razorpay (payments)

Each SaaS has different schemas and IDs.

The system must:
1. Fetch raw source data
2. Normalize into a universal internal schema
3. Maintain internal canonical IDs
4. Track external mappings
5. Track provenance/lineage
6. Support AI chat queries with citations
7. Support autonomous monitoring agents

--------------------------------------------------
CONNECTOR ABSTRACTION
--------------------------------------------------

Create an abstract BaseConnector class.

Methods:
- fetch_orders()
- fetch_shipments()
- fetch_payments()

Each connector inherits from BaseConnector.

Create:
- ShopifyConnector
- ShiprocketConnector
- RazorpayConnector

Use realistic mocked sample data instead of real APIs.

IMPORTANT:
Each connector should return RAW source-specific payloads.
Do NOT normalize inside connector classes.

--------------------------------------------------
MOCK RAW DATA EXAMPLES
--------------------------------------------------

Shopify example:

{
  "id": "ORD-101",
  "customer_name": "Rahul",
  "total_price": 1200,
  "currency": "INR",
  "created_at": "2026-05-10T10:00:00"
}

Shiprocket example:

{
  "shipment_id": "SHIP-778",
  "linked_order_id": "ORD-101",
  "shipment_status": "RTO",
  "courier_name": "Delhivery"
}

Razorpay example:

{
  "payment_id": "PAY-999",
  "order_ref": "ORD-101",
  "amount": 1200,
  "payment_status": "Paid",
  "payment_method": "COD"
}

--------------------------------------------------
UNIVERSAL NORMALIZED DATABASE SCHEMA
--------------------------------------------------

Use SQLAlchemy models.

Create these normalized tables.

1. orders

Purpose:
Canonical business order entity.

Columns:
- internal_order_id (Primary Key)
- merchant_id
- customer_name
- amount
- currency
- order_status
- created_at

2. shipments

Purpose:
Normalized logistics entity.

Columns:
- internal_shipment_id (Primary Key)
- internal_order_id (Foreign Key -> orders.internal_order_id)
- shipment_status
- courier_name
- shipped_at

3. payments

Purpose:
Normalized payment entity.

Columns:
- internal_payment_id (Primary Key)
- internal_order_id (Foreign Key -> orders.internal_order_id)
- amount
- payment_status
- payment_method
- created_at

4. entity_mappings

Purpose:
Maps external SaaS IDs to internal canonical IDs.

Columns:
- id (Primary Key)
- internal_entity_id
- entity_type
- source
- external_id

Example:
INT-1 -> Shopify -> ORD-101
INT-1 -> Shiprocket -> SHIP-778
INT-1 -> Razorpay -> PAY-999

5. provenance

Purpose:
Track where every normalized value originated from.

Columns:
- id (Primary Key)
- internal_entity_id
- field_name
- source_system
- source_field
- source_row_id
- synced_at

Example:
amount came from Shopify.total_price
shipment_status came from Shiprocket.shipment_status

--------------------------------------------------
NORMALIZATION LAYER
--------------------------------------------------

Create services/normalization.py

Responsibilities:
- Convert raw connector payloads into normalized schema
- Generate internal canonical IDs
- Insert normalized rows
- Create entity mappings
- Create provenance entries

IMPORTANT:
Normalization logic must be separated from connectors.

--------------------------------------------------
ENTITY RESOLUTION / MAPPING LOGIC
--------------------------------------------------

The system must support linking data across SaaS tools.

Example:
Shopify order ORD-101
Shiprocket shipment SHIP-778
Razorpay payment PAY-999

All belong to:
internal_order_id = INT-1

Implement helper utilities to:
- create mappings
- resolve mappings
- fetch canonical IDs from external IDs

--------------------------------------------------
PROVENANCE / LINEAGE
--------------------------------------------------

Every normalized field should be traceable.

Example:
orders.amount
came from:
Shopify.total_price
source_row_id = ORD-101

The provenance layer should support AI citations.

--------------------------------------------------
SYNC SERVICE
--------------------------------------------------

Create services/sync_service.py

Responsibilities:
- call connectors
- normalize data
- store normalized entities
- maintain mappings
- maintain provenance

Create a /sync endpoint that runs full ingestion.

--------------------------------------------------
CHAT TOOL LAYER
--------------------------------------------------

Create chat/tools.py

Functions:
- get_total_revenue()
- get_rto_orders()
- get_order_by_id()
- get_failed_shipments()

Every numerical answer MUST include citations/provenance.

Example response:

{
  "answer": "Total revenue is ₹2000",
  "citations": [
    {
      "internal_entity_id": "INT-1",
      "source_system": "shopify",
      "source_row_id": "ORD-101"
    }
  ]
}

Do not allow uncited numerical claims.

--------------------------------------------------
AUTONOMOUS AGENT
--------------------------------------------------

Create agents/rto_agent.py

Agent behavior:
- scans normalized orders and shipments
- finds high-value RTO orders
- generates operational recommendation

Example:
"Pause COD in high-RTO regions"

The agent should output:
- trigger reason
- analyzed data
- recommendation
- run logs

Do NOT send notifications.

--------------------------------------------------
FASTAPI ENDPOINTS
--------------------------------------------------

Create:

GET /orders
GET /payments
GET /shipments

POST /sync

GET /chat/revenue
GET /chat/rto

POST /agent/run

--------------------------------------------------
DATABASE
--------------------------------------------------

Use SQLite.

Auto-create database and tables on startup.

Seed realistic sample data.

--------------------------------------------------
README REQUIREMENTS
--------------------------------------------------

Generate a strong README explaining:

1. Architecture overview
2. Connector abstraction
3. Universal schema
4. Entity mapping strategy
5. Provenance strategy
6. Chat citation system
7. Agent design
8. Scale considerations
9. Failure modes
10. What breaks at 10k merchants
11. Why SQLite was chosen for v0
12. How this evolves to PostgreSQL/event pipelines later

--------------------------------------------------
SCALABILITY NOTES
--------------------------------------------------

In README discuss:
- webhook ingestion
- async workers
- PostgreSQL migration
- partitioning
- rate limits
- connector retries
- eventual consistency
- event-driven ingestion

Do not implement distributed systems.
Only discuss realistic evolution path.

--------------------------------------------------
CODE QUALITY REQUIREMENTS
--------------------------------------------------

Requirements:
- complete implementations
- no TODO placeholders
- strongly commented
- modular architecture
- beginner-readable
- realistic naming
- proper relationships
- clean SQLAlchemy models
- type hints everywhere

Generate COMPLETE code for all files.

Do not skip implementations.

Do not oversimplify schema relationships.

Use realistic mock data and realistic normalization flow.