"""
Citation Verification Script

This script validates that all citations in a response are:
1. Properly formatted
2. Traceable to source data
3. Not hallucinated
4. Accurate
"""

import json
from typing import dict, list
from dataclasses import dataclass


@dataclass
class CitationValidationResult:
    """Result of citation validation"""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    proof: dict


def validate_citation_format(citation: dict) -> tuple[bool, list[str]]:
    """Check if citation has required fields"""
    required_fields = [
        "internal_entity_id",
        "source_system", 
        "source_field",
        "source_row_id",
        "field_name"
    ]
    
    errors = []
    for field in required_fields:
        if field not in citation:
            errors.append(f"Missing required field: {field}")
    
    # Validate field values
    if citation.get("source_system") not in ["shopify", "razorpay", "shiprocket"]:
        errors.append(f"Invalid source_system: {citation.get('source_system')}")
    
    if not citation.get("internal_entity_id", "").startswith("INT-"):
        errors.append("internal_entity_id must start with INT-")
    
    return len(errors) == 0, errors


def validate_citation_against_source(
    citation: dict,
    source_data: dict
) -> tuple[bool, list[str]]:
    """Verify citation can be traced to actual source data"""
    
    errors = []
    source_system = citation["source_system"]
    source_row_id = citation["source_row_id"]
    
    # Get data from appropriate source
    if source_system not in source_data:
        errors.append(f"Source system not found: {source_system}")
        return False, errors
    
    # Find the record
    source_records = source_data[source_system]
    record = None
    
    for rec in source_records:
        if rec.get("id") == source_row_id or rec.get("shipment_id") == source_row_id:
            record = rec
            break
    
    if record is None:
        errors.append(f"Cannot find {source_row_id} in {source_system}")
        return False, errors
    
    # Verify field exists
    source_field = citation["source_field"]
    if source_field not in record:
        errors.append(f"Field '{source_field}' not in {source_row_id}")
        return False, errors
    
    return True, errors


def validate_response_citations(
    response: dict,
    source_data: dict
) -> CitationValidationResult:
    """
    Validate all citations in a response
    
    Args:
        response: {"answer": "...", "citations": [...]}
        source_data: {"shopify": [...], "shiprocket": [...]}
    
    Returns:
        CitationValidationResult with validation status
    """
    
    all_errors = []
    all_warnings = []
    proof = {}
    
    # Check answer exists
    if "answer" not in response:
        all_errors.append("Response missing 'answer' field")
        return CitationValidationResult(False, all_errors, all_warnings, proof)
    
    # Check citations exist
    if "citations" not in response:
        all_errors.append("Response missing 'citations' field")
        return CitationValidationResult(False, all_errors, all_warnings, proof)
    
    citations = response["citations"]
    
    if not citations:
        all_warnings.append("No citations provided")
    
    # Validate each citation
    for i, citation in enumerate(citations):
        valid_format, format_errors = validate_citation_format(citation)
        if not valid_format:
            for err in format_errors:
                all_errors.append(f"Citation {i}: {err}")
        
        valid_source, source_errors = validate_citation_against_source(
            citation,
            source_data
        )
        if not valid_source:
            for err in source_errors:
                all_errors.append(f"Citation {i}: {err}")
        else:
            proof[f"citation_{i}"] = {
                "source_row_id": citation["source_row_id"],
                "source_system": citation["source_system"],
                "verified": True
            }
    
    is_valid = len(all_errors) == 0
    return CitationValidationResult(is_valid, all_errors, all_warnings, proof)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    
    # Example response from system
    response = {
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
    
    # Source data (what we know is true)
    source_data = {
        "shopify": [
            {
                "id": "ORD-101",
                "customer_name": "Rahul",
                "total_price": "1200.00",
                "order_status": "paid"
            },
            {
                "id": "ORD-103",
                "customer_name": "Amit",
                "total_price": "4500.00",
                "order_status": "paid"
            }
        ],
        "shiprocket": [
            {
                "shipment_id": "SHIP-778",
                "linked_order_id": "ORD-101",
                "shipment_status": "RTO",
                "courier_name": "Delhivery"
            },
            {
                "shipment_id": "SHIP-780",
                "linked_order_id": "ORD-103",
                "shipment_status": "RTO",
                "courier_name": "Delhivery"
            }
        ]
    }
    
    # Validate
    result = validate_response_citations(response, source_data)
    
    # Report
    print("=" * 60)
    print("CITATION VALIDATION REPORT")
    print("=" * 60)
    print(f"\n✅ VALID: {result.is_valid}")
    
    if result.errors:
        print(f"\n❌ ERRORS ({len(result.errors)}):")
        for error in result.errors:
            print(f"  - {error}")
    else:
        print("\n✅ No errors found")
    
    if result.warnings:
        print(f"\n⚠️  WARNINGS ({len(result.warnings)}):")
        for warning in result.warnings:
            print(f"  - {warning}")
    else:
        print("\n✅ No warnings")
    
    if result.proof:
        print(f"\n📋 PROOF ({len(result.proof)}):")
        for key, val in result.proof.items():
            print(f"  ✓ {key}: {val['source_row_id']} from {val['source_system']}")
    
    print("\n" + "=" * 60)
    print("ANSWER")
    print("=" * 60)
    print(response["answer"])
    print("\n" + "=" * 60)
