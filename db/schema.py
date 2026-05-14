"""Pydantic models for API responses (decoupled from SQLAlchemy ORM objects)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    """Single provenance-backed reference for a claim."""

    model_config = ConfigDict(extra="forbid")

    internal_entity_id: str
    source_system: str
    source_field: str
    source_row_id: str
    field_name: str | None = None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    internal_order_id: str
    merchant_id: str
    customer_name: str
    amount: Decimal
    currency: str
    order_status: str
    created_at: datetime


class ShipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    internal_shipment_id: str
    internal_order_id: str
    shipment_status: str
    courier_name: str
    shipped_at: datetime | None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    internal_payment_id: str
    internal_order_id: str
    amount: Decimal
    payment_status: str
    payment_method: str
    created_at: datetime


class ChatAnswer(BaseModel):
    """Chat-style payload: natural language answer plus mandatory citations for numbers."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    tool_used: str | None = None


class SyncSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    orders_upserted: int
    shipments_upserted: int
    payments_upserted: int
    mappings_touched: int
    provenance_rows_written: int


class AgentRunLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: str
    detail: str


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_reason: str
    analyzed_data: dict
    recommendation: str
    run_logs: list[AgentRunLog]


class ToolCall(BaseModel):
    """LLM router output: one deterministic tool + validated arguments."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    """
    Structured deterministic output used for validation and summarization.

    `value` may be numeric, list, or textual depending on the tool metric.
    """

    model_config = ConfigDict(extra="forbid")

    metric: str
    value: int | float | str | dict | list
    currency: str | None = None
    calculation: dict = Field(default_factory=dict)
    filters: dict = Field(default_factory=dict)
    records: list[dict] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class ChatQueryRequest(BaseModel):
    """Generic query endpoint request body."""

    model_config = ConfigDict(extra="forbid")

    question: str


class GroundedChatResponse(BaseModel):
    """Grounded conversational response with traceable tool output."""

    model_config = ConfigDict(extra="forbid")

    question: str
    tool_used: str
    answer: str
    structured_data: ToolExecutionResult
    citations: list[Citation] = Field(default_factory=list)
