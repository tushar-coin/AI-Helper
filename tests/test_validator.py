import pytest

from chat.validator import validate_grounded_answer_against_results
from db.schema import Citation, ToolExecutionResult


def test_multi_result_validator_accepts_cited_numbers_from_results():
    result = ToolExecutionResult(
        metric="total_revenue",
        value=3150.0,
        currency="INR",
        citations=[
            Citation(
                internal_entity_id="INT-ORD-1",
                source_system="shopify",
                source_field="total_price",
                source_row_id="ORD-1",
                field_name="amount",
            )
        ],
    )

    validate_grounded_answer_against_results("Total revenue is INR 3150.0.", [result])


def test_multi_result_validator_rejects_uncited_numeric_answer():
    result = ToolExecutionResult(metric="total_revenue", value=3150.0, currency="INR")

    with pytest.raises(ValueError):
        validate_grounded_answer_against_results("Total revenue is INR 3150.0.", [result])


def test_multi_result_validator_rejects_unsupported_numeric_answer():
    result = ToolExecutionResult(
        metric="total_revenue",
        value=3150.0,
        currency="INR",
        citations=[
            Citation(
                internal_entity_id="INT-ORD-1",
                source_system="shopify",
                source_field="total_price",
                source_row_id="ORD-1",
                field_name="amount",
            )
        ],
    )

    with pytest.raises(ValueError):
        validate_grounded_answer_against_results("Total revenue is INR 9999.0.", [result])
