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


def test_payment_method_breakdown_tool():
    db = _synced_session()
    try:
        result = execute_tool_call(db, ToolCall(tool_name="get_payment_method_breakdown"))
    finally:
        db.close()

    assert result.metric == "payment_method_breakdown"
    assert result.value["cod"]["count"] == 2
    assert result.value["upi"]["count"] == 2
    assert result.citations


def test_shipment_status_breakdown_tool():
    db = _synced_session()
    try:
        result = execute_tool_call(db, ToolCall(tool_name="get_shipment_status_breakdown"))
    finally:
        db.close()

    assert result.metric == "shipment_status_breakdown"
    assert result.value["rto"] == 2
    assert result.value["delivered"] == 1
    assert result.value["lost"] == 1
    assert result.citations


def test_order_timeline_accepts_external_order_ref():
    db = _synced_session()
    try:
        result = execute_tool_call(
            db,
            ToolCall(tool_name="get_order_timeline", arguments={"order_id": "ORD-101"}),
        )
    finally:
        db.close()

    assert result.metric == "order_timeline"
    assert str(result.value).startswith("INT-ORD-")
    assert result.calculation["event_count"] == 3
    assert {row["event_type"] for row in result.records} == {
        "order_created",
        "shipment",
        "payment",
    }
    assert result.citations


def test_shipment_by_id_accepts_external_shipment_ref():
    db = _synced_session()
    try:
        result = execute_tool_call(
            db,
            ToolCall(tool_name="get_shipment_by_id", arguments={"shipment_id": "SHIP-778"}),
        )
    finally:
        db.close()

    assert result.metric == "shipment_by_id"
    assert str(result.value).startswith("INT-SHIP-")
    assert result.records[0]["shipped_at"] == "2026-05-11T08:00:00"
    assert result.records[0]["shipment_status"] == "rto"
    assert result.records[0]["courier_name"] == "Delhivery"
    assert result.citations


def test_shipments_for_order_accepts_external_order_ref():
    db = _synced_session()
    try:
        result = execute_tool_call(
            db,
            ToolCall(tool_name="get_shipments_for_order", arguments={"order_id": "ORD-101"}),
        )
    finally:
        db.close()

    assert result.metric == "shipments_for_order"
    assert result.value == 1
    assert result.records[0]["internal_shipment_id"].startswith("INT-SHIP-")
    assert result.records[0]["shipment_status"] == "rto"
    assert result.records[0]["courier_name"] == "Delhivery"
    assert result.records[0]["shipped_at"] == "2026-05-11T08:00:00"
    assert result.citations
