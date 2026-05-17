# Citation System: RTO Orders Query Example

**Date:** 17 May 2026  
**Query:** "Show me the total revenue for RTO orders above 1000"  
**Model:** qwen2.5-coder:7b  
**Status:** ✅ Success with full provenance

---

## 📋 Full Response

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

---

## 🔍 Citation Breakdown

### Claim 1: "2 orders with an RTO shipment"

**Citation 3 proves the first RTO:**
```json
{
  "internal_entity_id": "INT-SHIP-e62fa3eb58",  // Our internal ID
  "source_system": "shiprocket",                 // Data comes from Shiprocket
  "source_field": "shipment_status",             // The field we checked
  "source_row_id": "SHIP-780",                   // Original ID: SHIP-780
  "field_name": "shipment_status"                // Field name in our schema
}
```

**Verification in raw Shiprocket data:**
```python
{
    "shipment_id": "SHIP-780",
    "linked_order_id": "ORD-103",
    "shipment_status": "RTO",  # ← This is what the citation proves
    "courier_name": "Delhivery",
    "shipped_at": "2026-05-09T11:00:00",
}
```
✅ **MATCH:** Citation correctly identifies SHIP-780 has status "RTO"

**Citation 4 proves the second RTO:**
```json
{
  "internal_entity_id": "INT-SHIP-bf0c4d5ff9",
  "source_system": "shiprocket",
  "source_field": "shipment_status",
  "source_row_id": "SHIP-778",
  "field_name": "shipment_status"
}
```

**Verification:**
```python
{
    "shipment_id": "SHIP-778",
    "linked_order_id": "ORD-101",
    "shipment_status": "RTO",  # ← Citation proves this
    "courier_name": "Delhivery",
    "shipped_at": "2026-05-11T08:00:00",
}
```
✅ **MATCH:** Citation correctly identifies SHIP-778 has status "RTO"

---

### Claim 2: "Revenue for those 2 orders is INR 5700.0"

**Citation 1 proves the first order amount:**
```json
{
  "internal_entity_id": "INT-ORD-4b71601a48",
  "source_system": "shopify",
  "source_field": "total_price",
  "source_row_id": "ORD-103",
  "field_name": "amount"
}
```

**Verification in Shopify:**
```python
{
    "id": "ORD-103",
    "customer_name": "Amit",
    "total_price": "4500.00",  # ← Citation proves this amount
    "currency": "INR",
    "order_status": "paid",
}
```
✅ **MATCH:** ORD-103 has amount 4500 INR

**Citation 2 proves the second order amount:**
```json
{
  "internal_entity_id": "INT-ORD-38221bbfb4",
  "source_system": "shopify",
  "source_field": "total_price",
  "source_row_id": "ORD-101",
  "field_name": "amount"
}
```

**Verification:**
```python
{
    "id": "ORD-101",
    "customer_name": "Rahul",
    "total_price": "1200.00",  # ← Citation proves this amount
    "currency": "INR",
    "order_status": "paid",
}
```
✅ **MATCH:** ORD-101 has amount 1200 INR

**Total:** 4500 + 1200 = **5700 INR** ✓

---

## 🏗️ How Citations Flow Through the System

### Step 1: Data Ingestion (Connectors)
```
Shopify API → ShiprocketConnector.fetch_orders()
↓
{"id": "ORD-101", "total_price": "1200"}
↓
Normalized + ID mapping created
↓
"INT-ORD-38221bbfb4" ← (Maps to ORD-101)
```

### Step 2: Provenance Tracking
```
INSERT INTO provenance:
{
  "internal_entity_id": "INT-ORD-38221bbfb4",
  "source_system": "shopify",
  "source_row_id": "ORD-101",
  "source_field": "total_price",
  "value": "1200.00",
  "synced_at": "2026-05-17T10:00:00"
}
```

### Step 3: Tool Execution
```
Tool: get_revenue_for_order_ids
Input:  ["INT-ORD-38221bbfb4", "INT-ORD-4b71601a48"]
↓
Query provenance for these internal_entity_ids
↓
Find: ORD-101 @ Shopify, ORD-103 @ Shopify
↓
Return: value=5700, citations=[4 records from provenance table]
```

### Step 4: Response to User
```json
{
  "answer": "Revenue is INR 5700",
  "citations": [
    {provenance record for ORD-101},
    {provenance record for ORD-103},
    {provenance record for SHIP-780},
    {provenance record for SHIP-778}
  ]
}
```

---

## 💡 Citation Contract

| Aspect | Requirement | This Example |
|--------|-------------|--------------|
| **Every number has a source** | ✅ Required | 5700 = ORD-101 + ORD-103 |
| **Source is traceable** | ✅ Required | Can go to Shopify → ORD-101 |
| **Source is verifiable** | ✅ Required | Actual Shopify record exists |
| **No hallucinated values** | ✅ Required | No made-up order IDs |
| **Links across systems** | ✅ Required | Shopify ORD + Shiprocket SHIP |

---

## 🛡️ What This Prevents

### ❌ Without Citations

```json
{
  "answer": "You have 2 RTO orders worth 5700 rupees"
}
```

**Problems:**
- Founder: "Which orders?"
- Founder: "How do I verify?"
- Founder: "Is this hallucinated?"
- Founder: "I don't trust this"

### ✅ With Citations

```json
{
  "answer": "You have 2 RTO orders worth 5700 rupees",
  "citations": [
    {"source_row_id": "ORD-101", "source_system": "shopify"},
    {"source_row_id": "ORD-103", "source_system": "shopify"},
    {"source_row_id": "SHIP-780", "source_system": "shiprocket"},
    {"source_row_id": "SHIP-778", "source_system": "shiprocket"}
  ]
}
```

**Benefits:**
- ✅ Founder can click ORD-101 in Shopify dashboard
- ✅ Founder can verify SHIP-780 status in Shiprocket
- ✅ Founder can audit the AI's logic
- ✅ Founder trusts the system

---

## 🔄 Tool Chain That Produced This

### Step 1: Get RTO Orders
```
Tool: get_rto_orders
Arguments: {}
Returns: 2 orders with RTO shipments
  - INT-ORD-38221bbfb4 (ORD-101, Rahul, 1200 INR)
  - INT-ORD-4b71601a48 (ORD-103, Amit, 4500 INR)
Citations: Links to SHIP-778 and SHIP-780 RTO status
```

### Step 2: Get Revenue for Those Orders
```
Tool: get_revenue_for_order_ids
Arguments: {"order_ids": ["INT-ORD-38221bbfb4", "INT-ORD-4b71601a48"]}
Returns: 5700 INR total
Citations: Links to ORD-101 and ORD-103 amounts from Shopify
```

### Step 3: Format Answer
```
Combine results → "2 orders with RTO, Revenue 5700"
Merge citations → 4 total citations
Output response
```

---

## 📊 Citation Metadata

| Field | Purpose | Example |
|-------|---------|---------|
| `internal_entity_id` | Our normalized ID | `INT-ORD-38221bbfb4` |
| `source_system` | Where data originated | `shopify` |
| `source_row_id` | External/source ID | `ORD-101` |
| `source_field` | Field name in source | `total_price` |
| `field_name` | Field name in our schema | `amount` |

---

## ✅ Validation Checklist

- [x] Every claim in answer has at least 1 citation
- [x] Every citation points to a real row in source system
- [x] No invented or hallucinated order/shipment IDs
- [x] Citation links are bidirectional (can trace forward & back)
- [x] System captures metadata for audit trail
- [x] Founder can verify each citation independently

---

## 🚀 How Founders Use This

**Scenario 1: Verify a Claim**
```
Founder sees: "Revenue for RTO orders is 5700"
Founder clicks citation → Opens Shopify ORD-101
Founder sees: total_price = 1200
Founder clicks citation → Opens Shopify ORD-103
Founder sees: total_price = 4500
Founder internally calculates: 1200 + 4500 = 5700 ✓
Founder: "This AI is trustworthy"
```

**Scenario 2: Audit Trail**
```
Founder: "Where did this 5700 number come from?"
System: "Citations show ORD-101 + ORD-103 from Shopify"
Founder: "When was this data synced?"
System: "2026-05-17T10:00:00 (from provenance)"
Founder: "Has this changed since then?"
System: "Check changelog for ORD-101 → No changes"
```

**Scenario 3: Debug Bad Answer**
```
Founder: "Why is SHIP-780 counted as RTO?"
System: "Citation shows SHIP-780 status=RTO in Shiprocket"
Founder: "But I marked it as delivered yesterday!"
System: "Our sync ran before your update. Citation is stale."
Founder: "OK, re-sync please"
System: [refresh] → Provides new answer
```

---

## 🎯 Key Takeaway

**Citation System Ensures:**
- ✅ AI never lies (everything is traceable)
- ✅ Founders can verify answers
- ✅ Audit trails exist for compliance
- ✅ Debugging is possible
- ✅ Trust is built on evidence, not faith

Every number = Evidence + Source + Proof.
