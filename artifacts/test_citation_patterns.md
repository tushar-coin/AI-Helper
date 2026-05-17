# Test Artifacts: Citation System Validation

This file contains test cases and expected response formats for the citation system.

---

## Test Case 1: RTO Orders Revenue Query

### Query
```
"Show me the total revenue for RTO orders above 1000"
```

### Expected Response Structure
```json
{
  "answer": "[human readable explanation]",
  "citations": [
    {
      "internal_entity_id": "[INT-*]",
      "source_system": "[shopify|razorpay|shiprocket]",
      "source_field": "[field from source]",
      "source_row_id": "[original external ID]",
      "field_name": "[normalized field name]"
    }
  ],
  "tool_used": "[tool1, tool2, ...]"
}
```

### Actual Response
```json
{
  "answer": "There are 2 orders with an RTO shipment. Revenue for those 2 orders is INR 5700.0.",
  "citations": [
    {
      "internal_entity_id": "INT-ORD-4b71601a48",
      "source_system": "shopify",
      "source_field": "total_price",
      "source_row_id": "ORD-103",
      "field_name": "amount"
    },
    {
      "internal_entity_id": "INT-ORD-38221bbfb4",
      "source_system": "shopify",
      "source_field": "total_price",
      "source_row_id": "ORD-101",
      "field_name": "amount"
    },
    {
      "internal_entity_id": "INT-SHIP-e62fa3eb58",
      "source_system": "shiprocket",
      "source_field": "shipment_status",
      "source_row_id": "SHIP-780",
      "field_name": "shipment_status"
    },
    {
      "internal_entity_id": "INT-SHIP-bf0c4d5ff9",
      "source_system": "shiprocket",
      "source_field": "shipment_status",
      "source_row_id": "SHIP-778",
      "field_name": "shipment_status"
    }
  ],
  "tool_used": "get_rto_orders, get_revenue_for_order_ids"
}
```

### Validation ✅

| Check | Status | Evidence |
|-------|--------|----------|
| Answer is human-readable | ✅ | "2 orders with RTO, revenue 5700" |
| Citations exist | ✅ | 4 citations provided |
| Revenue claims cited | ✅ | Citations 1-2 reference ORD-101, ORD-103 |
| RTO status cited | ✅ | Citations 3-4 reference SHIP-778, SHIP-780 |
| No hallucinated values | ✅ | All source_row_ids are real |
| Tool chain visible | ✅ | get_rto_orders → get_revenue_for_order_ids |

---

## Test Case 2: Single Shipment Query

### Query
```
"What is the status and courier for shipment SHIP-778?"
```

### Expected Response
```json
{
  "answer": "Shipment SHIP-778 has status 'RTO' and is being handled by courier 'Delhivery'.",
  "citations": [
    {
      "internal_entity_id": "INT-SHIP-bf0c4d5ff9",
      "source_system": "shiprocket",
      "source_field": "shipment_status",
      "source_row_id": "SHIP-778",
      "field_name": "shipment_status"
    },
    {
      "internal_entity_id": "INT-SHIP-bf0c4d5ff9",
      "source_system": "shiprocket",
      "source_field": "courier_name",
      "source_row_id": "SHIP-778",
      "field_name": "courier_name"
    }
  ],
  "tool_used": "get_shipment_by_id"
}
```

### Validation Rules
- ✅ Each fact (status, courier) must have a citation
- ✅ Citations must reference the single source (SHIP-778)
- ✅ Internal entity must be consistent (INT-SHIP-bf0c4d5ff9)

---

## Test Case 3: Multi-system Query

### Query
```
"Show me orders from Rahul that are unpaid with failed shipments"
```

### Expected Response Structure
```json
{
  "answer": "Rahul has 1 unpaid order (ORD-101, 1200 INR) with a failed shipment (SHIP-778, RTO status).",
  "citations": [
    {
      "internal_entity_id": "INT-ORD-38221bbfb4",
      "source_system": "shopify",
      "source_field": "order_status",
      "source_row_id": "ORD-101",
      "field_name": "order_status"
    },
    {
      "internal_entity_id": "INT-ORD-38221bbfb4",
      "source_system": "shopify",
      "source_field": "total_price",
      "source_row_id": "ORD-101",
      "field_name": "amount"
    },
    {
      "internal_entity_id": "INT-SHIP-bf0c4d5ff9",
      "source_system": "shiprocket",
      "source_field": "shipment_status",
      "source_row_id": "SHIP-778",
      "field_name": "shipment_status"
    }
  ],
  "tool_used": "get_customer_order_summary, get_shipments_for_order"
}
```

### Validation Rules
- ✅ Citations span multiple systems (shopify + shiprocket)
- ✅ Each claim has backing evidence
- ✅ Links between systems visible (ORD-101 → SHIP-778)

---

## Test Case 4: Aggregation Query

### Query
```
"What's the total revenue across all orders?"
```

### Expected Response
```json
{
  "answer": "Total revenue across all orders is INR 50,000.",
  "citations": [
    {
      "internal_entity_id": "INT-ORD-38221bbfb4",
      "source_system": "shopify",
      "source_field": "total_price",
      "source_row_id": "ORD-101",
      "field_name": "amount"
    },
    {
      "internal_entity_id": "INT-ORD-4b71601a48",
      "source_system": "shopify",
      "source_field": "total_price",
      "source_row_id": "ORD-103",
      "field_name": "amount"
    }
  ],
  "tool_used": "get_total_revenue"
}
```

### Validation Rules
- ✅ Aggregated number (50000) has citations to component parts
- ✅ Founder can verify: 1200 + 4500 + ... = 50000

---

## Citation System Validation Checklist

### For Every Response

- [ ] **Answer clarity**: Is the answer human-readable?
- [ ] **Citation completeness**: Does every number have a citation?
- [ ] **Citation accuracy**: Do citations match actual source data?
- [ ] **No hallucinations**: Are all source_row_ids real external IDs?
- [ ] **System traceability**: Can you follow the chain shopify→normalized→answer?
- [ ] **Tool visibility**: Is tool_used field populated?

### For Multi-System Queries

- [ ] **Cross-system links**: Are relationships between systems clear?
- [ ] **Consistent IDs**: Do INT-* IDs map correctly to external IDs?
- [ ] **Field alignment**: Do source_field names match actual API fields?

### For Founders

- [ ] **Verifiable**: Can they click through to source data?
- [ ] **Auditable**: Can they trace the data pipeline?
- [ ] **Trustworthy**: Would they act on this?

---

## Common Citation Patterns

### Pattern 1: Simple Lookup
```json
{
  "answer": "ORD-101 has status PAID",
  "citations": [
    {"source_row_id": "ORD-101", "source_field": "order_status"}
  ]
}
```

### Pattern 2: Aggregation
```json
{
  "answer": "Total revenue is 5700",
  "citations": [
    {"source_row_id": "ORD-101", "source_field": "total_price", "value": "1200"},
    {"source_row_id": "ORD-103", "source_field": "total_price", "value": "4500"}
  ]
}
```

### Pattern 3: Filtering
```json
{
  "answer": "2 RTO shipments linked to paid orders",
  "citations": [
    {"source_row_id": "SHIP-778", "source_field": "shipment_status", "value": "RTO"},
    {"source_row_id": "SHIP-780", "source_field": "shipment_status", "value": "RTO"},
    {"source_row_id": "ORD-101", "source_field": "order_status", "value": "PAID"},
    {"source_row_id": "ORD-103", "source_field": "order_status", "value": "PAID"}
  ]
}
```

### Pattern 4: Cross-System
```json
{
  "answer": "Rahul's order (ORD-101) paid via COD, shipment (SHIP-778) is RTO",
  "citations": [
    {"source_system": "shopify", "source_row_id": "ORD-101", "source_field": "customer_name"},
    {"source_system": "razorpay", "source_row_id": "PAY-X", "source_field": "payment_method"},
    {"source_system": "shiprocket", "source_row_id": "SHIP-778", "source_field": "shipment_status"}
  ]
}
```

---

## Error Cases (Should NOT Happen)

### ❌ Error 1: Uncited Number
```json
{
  "answer": "You have 5 orders",
  "citations": []
}
```
**Problem:** Answer has a number but no citations → **FAIL**

### ❌ Error 2: Hallucinated IDs
```json
{
  "answer": "ORD-999 has revenue 10000",
  "citations": [
    {"source_row_id": "ORD-999"}
  ]
}
```
**Problem:** ORD-999 doesn't exist in Shopify → **FAIL**

### ❌ Error 3: Wrong System
```json
{
  "answer": "Shipment SHIP-101 status is RTO",
  "citations": [
    {"source_system": "shopify", "source_row_id": "SHIP-101"}
  ]
}
```
**Problem:** Shipments are in Shiprocket, not Shopify → **FAIL**

### ❌ Error 4: Stale Data
```json
{
  "answer": "ORD-101 has status PENDING",
  "citations": [
    {"synced_at": "2026-05-01T00:00:00"}
  ]
}
```
**Problem:** Citation is 16 days old, order may have changed → **WARN**

---

## How Founders Test Citations

### Manual Verification Script
```python
# Founder receives response
response = {
    "answer": "Revenue is 5700",
    "citations": [...]
}

# Founder verifies each citation
for citation in response["citations"]:
    if citation["source_system"] == "shopify":
        order = shopify.get_order(citation["source_row_id"])
        assert order[citation["source_field"]] == citation["value"]
        
    elif citation["source_system"] == "shiprocket":
        shipment = shiprocket.get_shipment(citation["source_row_id"])
        assert shipment[citation["source_field"]] == citation["value"]

print("✅ All citations verified")
```

---

## Summary

**Each citation is a proof:** Source data exists and the AI didn't hallucinate.

**Citation format:** `internal_id → source_system → external_id → field → value`

**Founder benefit:** "If the AI can prove it with citations, I trust it."
