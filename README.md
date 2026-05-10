# AI-Helper — D2C Operations Assistant (v0)

Helps operators reason over Shopify, Shiprocket, and Razorpay data with **normalization**, **entity mapping**, and **provenance-backed** answers suitable for LLM chat tools.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional; defaults work for local SQLite
uvicorn api.main:app --reload
```

- API docs: `http://127.0.0.1:8000/docs` (default uvicorn port)
- SQLite file: `data/app.db` (created on startup; seeded once when empty)

## Architecture overview

The service is a **modular FastAPI** app with four layers:

1. **Connectors** return **raw vendor-shaped JSON** (mocked in v0).
2. **Normalization** converts raw payloads into **canonical tables** (`orders`, `shipments`, `payments`).
3. **Mappings** link **external IDs** (e.g. `ORD-101`, `SHIP-778`) to **internal IDs** (`INT-ORD-…`).
4. **Provenance** records **field-level lineage** (e.g. `orders.amount` ← `shopify.total_price`).

Downstream **chat tools** aggregate facts but attach **citations** from provenance so numeric claims stay auditable. The **RTO agent** reads normalized rows only and emits operational guidance (no notifications).

## Connector abstraction

`connectors/base.py` defines `BaseConnector` with `fetch_orders`, `fetch_shipments`, and `fetch_payments`. Each vendor implements all three; vendors without a dataset return empty lists.

**Rule:** connectors never normalize. They only yield **source-native** structures so normalization rules stay centralized and testable.

## Universal schema

SQLAlchemy models in `db/models.py` implement the normalized graph:

- **orders** — canonical commerce order (internal PK, merchant, customer, amount, currency, status, timestamps).
- **shipments** — logistics rows referencing `orders.internal_order_id`.
- **payments** — payment rows referencing the same internal order key.
- **entity_mappings** — many external IDs → one internal entity per type.
- **provenance** — which source field populated each normalized column.

## Entity mapping strategy

Inbound rows use different identifiers (`id`, `shipment_id`, `payment_id`) but often share a **human order code** (here: `ORD-101`). During sync:

1. Shopify orders create **`entity_mappings` rows** (`entity_type=order`, `source=shopify`, `external_id=ORD-101`).
2. Shiprocket resolves `linked_order_id` against **`entity_type=order`** mappings to find `internal_order_id`.
3. Razorpay resolves `order_ref` the same way before inserting `payments`.

Shipments and payments also receive their own mapping rows (`entity_type=shipment|payment`) for idempotent re-sync.

## Provenance strategy

Each normalized field write appends provenance rows capturing:

- `internal_entity_id` (order/shipment/payment internal key)
- `field_name` (normalized column)
- `source_system` / `source_field` / `source_row_id` (vendor coordinates)
- `synced_at`

This enables **AI citations**: chat endpoints return `answer` plus `citations[]` pointing back to concrete source cells.

## Chat citation system

`chat/tools.py` implements:

- `get_total_revenue`
- `get_rto_orders`
- `get_order_by_id`
- `get_failed_shipments`

Numeric aggregates pull **latest provenance** for contributing entities so responses avoid “uncited numbers.” If no rows exist yet, revenue answers are phrased **without invented totals**.

HTTP wrappers: `GET /chat/revenue`, `GET /chat/rto`, `GET /chat/order/{id}`, `GET /chat/failed-shipments`.

## Agent design

`agents/rto_agent.py` scans joined orders + shipments for **RTO** patterns above a **minimum order amount**, then returns structured JSON:

- trigger reason
- analyzed cohort
- recommendation text
- stepwise run logs

**No outbound notifications** — analysis only, suitable for cron or workflow triggers later.

## Scale considerations (v0 vs production)

v0 optimizes for **clarity** and **single-node demos**:

- SQLite + synchronous FastAPI handlers
- Full connector refresh via `POST /sync`
- Provenance append model (audit-friendly; compaction is a later concern)

## Failure modes

- **Ordering**: shipments/payments **must** run after orders; otherwise resolution raises a clear error.
- **Re-sync**: repeated syncs **upsert** core rows and **append** provenance (historical growth).
- **Ambiguous external IDs**: if two merchants shared storefront codes, you would scope mappings by `merchant_id` (future hardening).

## What breaks at ~10k merchants

SQLite and single-threaded ingestion will bottleneck on:

- write contention on `provenance` / `entity_mappings`
- full-table scans for analytics-style queries
- lack of **tenant partitioning** and **connector rate-limit backoff** at fleet scale

## Why SQLite for v0

- zero ops, file-based, perfect for **portable demos** and **integration tests**
- SQLAlchemy models port cleanly to PostgreSQL later

## Evolution path (PostgreSQL + events)

Reasonable upgrades:

- **PostgreSQL** for concurrent writers, indexes, and JSONB raw archives
- **Webhook ingestion** + **idempotent event IDs** instead of polling
- **Async workers** (Celery/RQ/Arq) for connector calls with **retries** and **rate limits**
- **Event-driven pipelines** (Kafka/Rabbit/SQS) for `order.updated`-style fan-out
- **Per-merchant partitions** (schema or table routing) and **read replicas** for BI

This repository **does not** implement distributed orchestration — it sketches the **seams** (connectors, normalization, sync, citations) where those components attach.

## HTTP endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/orders` | List normalized orders |
| GET | `/shipments` | List shipments |
| GET | `/payments` | List payments |
| POST | `/sync` | Run full mocked ingestion |
| GET | `/chat/revenue` | Revenue + citations |
| GET | `/chat/rto` | RTO order count + citations |
| GET | `/chat/order/{internal_order_id}` | Order detail + citations |
| GET | `/chat/failed-shipments` | Failed/RTO-class shipments + citations |
| POST | `/agent/run` | RTO monitoring agent |

## Project layout

```
connectors/     # Raw SaaS payloads
db/             # Engine, models, CRUD, seed
services/       # Normalization, sync, mapping/provenance helpers
chat/           # LLM-facing tools
agents/         # Autonomous monitors (v0: RTO)
api/main.py     # FastAPI app
data/app.db     # SQLite (generated)
```

## License / usage

Internal prototype scaffolding — adapt licensing as needed for your organization.
