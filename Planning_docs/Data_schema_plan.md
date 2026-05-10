# Plan 10-May

## As implemented (v0 codebase)

**Persistence:** SQLite (`data/app.db` by default; `DATABASE_URL` can override). Tables are created on app startup via SQLAlchemy `Base.metadata.create_all`.
### Why was sqlite used ?
- To deflate the time needed to have an actual running poc than i can plan future build planning to update it to postgress in future.
### Normalized tables (SQLAlchemy — `db/models.py`)

| Table | PK | Purpose |
|-------|-----|---------|
| `orders` | `internal_order_id` (string, max 64) | Canonical order per merchant |
| `shipments` | `internal_shipment_id` | Logistics row; FK → `orders.internal_order_id` (CASCADE on delete) |
| `payments` | `internal_payment_id` | Payment row; FK → `orders.internal_order_id` (CASCADE on delete) |
| `entity_mappings` | `id` (integer autoincrement) | External SaaS id → internal entity id |
| `provenance` | `id` (integer autoincrement) | Field-level lineage for citations |

**`orders` columns:** `merchant_id`, `customer_name`, `amount` (`Numeric(18,2)`), `currency`, `order_status`, `created_at` (naive `DateTime`). Indexed: `merchant_id`.

**`shipments` columns:** `internal_order_id`, `shipment_status`, `courier_name`, `shipped_at` (nullable). Indexed: `internal_order_id`.

**`payments` columns:** `internal_order_id`, `amount`, `payment_status`, `payment_method`, `created_at`. Indexed: `internal_order_id`.

**`entity_mappings` columns:** `internal_entity_id`, `entity_type`, `source`, `external_id`. Indexed on all four logical keys for lookups.

**`provenance` columns:** `internal_entity_id`, `field_name`, `source_system`, `source_field`, `source_row_id`, `synced_at`. Indexed: `internal_entity_id`.

**ORM relationships:** `Order.shipments` / `Order.payments` (one-to-many); `Shipment.order` / `Payment.order` (many-to-one). Shipments and payments use `cascade="all, delete-orphan"` from the order side.

### Identity conventions (runtime)

- Internal order ids: `INT-ORD-{10 hex chars}` (uuid fragment).
- Internal shipment ids: `INT-SHIP-{10 hex chars}`.
- Internal payment ids: `INT-PAY-{10 hex chars}`.

**`entity_mappings.entity_type` values used in code:** `order`, `shipment`, `payment` (see `services/mappings.py`).

**`entity_mappings.source` values:** e.g. `shopify`, `shiprocket`, `razorpay` (connector `source_name`).

### API / JSON shapes (Pydantic — `db/schema.py`)

These are response models only; they do not add database tables.

- **`Citation`:** `internal_entity_id`, `source_system`, `source_field`, `source_row_id`, optional `field_name`.
- **`OrderOut` / `ShipmentOut` / `PaymentOut`:** mirror the normalized row fields (decimals and datetimes as JSON-serializable types).
- **`ChatAnswer`:** `answer` (str), `citations` (list of `Citation`).
- **`SyncSummary`:** counts for orders, shipments, payments upserted; `mappings_touched`; `provenance_rows_written`.
- **`AgentResult`:** `trigger_reason`, `analyzed_data` (dict), `recommendation`, `run_logs` (`AgentRunLog`: `step`, `detail`).

### Not in v0

- No separate raw-ingest / staging tables (connectors return in-memory dicts; normalization writes straight to the tables above).
- No multi-tenant schema isolation beyond `merchant_id` on `orders`.

