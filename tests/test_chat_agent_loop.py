from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chat import orchestrator
from db.database import Base
from db.schema import AgentAction
from services.sync_service import SyncService


def _synced_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=True, bind=engine)
    db = session_local()
    SyncService().run_full_sync(db)
    return db


def test_agent_loop_executes_two_tools(monkeypatch):
    db = _synced_session()
    calls = []

    def fake_route_next_step(_question, _tool_descriptions, previous_results):
        calls.append(len(previous_results))
        if not previous_results:
            return AgentAction(
                action="tool",
                tool_name="get_rto_orders",
                arguments={"min_amount": 2000},
            )
        if len(previous_results) == 1:
            order_ids = [
                row["internal_order_id"]
                for row in previous_results[0].records
            ]
            return AgentAction(
                action="tool",
                tool_name="get_revenue_for_order_ids",
                arguments={"order_ids": order_ids},
            )
        return AgentAction(action="final_answer")

    monkeypatch.setattr(orchestrator, "route_next_step", fake_route_next_step)
    try:
        response = orchestrator.run_grounded_query_loop(
            db,
            "show high value rto orders and their revenue impact",
        )
    finally:
        db.close()

    assert response.tool_used == ["get_rto_orders", "get_revenue_for_order_ids"]
    assert [row.action for row in response.run_logs] == ["tool", "tool", "final_answer"]
    assert response.structured_data[0].metric == "rto_orders"
    assert response.structured_data[1].metric == "revenue_for_order_ids"
    assert "Revenue for those" in response.answer
    assert response.citations


def test_agent_loop_stops_on_repeated_tool_call(monkeypatch):
    db = _synced_session()

    def fake_route_next_step(_question, _tool_descriptions, _previous_results):
        return AgentAction(action="tool", tool_name="get_total_revenue", arguments={})

    monkeypatch.setattr(orchestrator, "route_next_step", fake_route_next_step)
    try:
        response = orchestrator.run_grounded_query_loop(db, "what is total revenue?")
    finally:
        db.close()

    assert response.tool_used == ["get_total_revenue"]
    assert [row.action for row in response.run_logs] == ["tool", "final_answer"]
