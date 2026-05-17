from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chat.tool_executor import execute_tool_call
from db.database import Base
from db.schema import ToolCall
from services.sync_service import SyncService


def _synced_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=True, bind=engine)
    db = session_local()
    SyncService().run_full_sync(db)
    return db


def test_get_order_by_id_resolves_external_order_ref():
    db = _synced_session()
    try:
        result = execute_tool_call(
            db,
            ToolCall(tool_name="get_order_by_id", arguments={"internal_order_id": "ORD-101"}),
        )
    finally:
        db.close()

    assert result.metric == "order_by_id"
    assert result.value != "not_found"
    assert str(result.value).startswith("INT-ORD-")
    assert result.filters["internal_order_id"] == "ORD-101"
    assert result.filters["resolved_internal_order_id"] == result.value
    assert result.citations


def test_revenue_for_order_ids_resolves_external_order_refs():
    db = _synced_session()
    try:
        result = execute_tool_call(
            db,
            ToolCall(
                tool_name="get_revenue_for_order_ids",
                arguments={"order_ids": ["ORD-101", "ORD-103"]},
            ),
        )
    finally:
        db.close()

    assert result.metric == "revenue_for_order_ids"
    assert result.value == 5700.0
    assert result.calculation["order_count"] == 2
    assert result.filters["order_ids"] == ["ORD-101", "ORD-103"]
    assert len(result.filters["resolved_internal_order_ids"]) == 2
    assert result.citations
