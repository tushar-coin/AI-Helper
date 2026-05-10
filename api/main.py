"""
FastAPI entrypoint: operational CRUD-style reads, sync, chat tools, and agent runs.

Run from repository root:

    uvicorn api.main:app --reload

Interactive API docs (OpenAPI): **Swagger UI** at ``/docs``, **ReDoc** at ``/redoc``,
and the raw schema at ``/openapi.json`` (built in; no separate Swagger server).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from agents.rto_agent import RtoAgent
from chat import tools as chat_tools
from db import crud, seed
from db.database import SessionLocal, get_db, init_db
from db.models import Order, Payment, Shipment
from db.schema import (
    AgentResult,
    ChatAnswer,
    OrderOut,
    PaymentOut,
    ShipmentOut,
    SyncSummary,
)
from services.sync_service import SyncService


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Ensure SQLite file exists, tables are created, and demo data is loaded once."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        seed.seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="D2C Operations Assistant (v0)",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root() -> dict:
    """Browser-friendly entry: there is no HTML UI; use `/docs` for the API explorer."""
    return {
        "service": "D2C Operations Assistant (v0)",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "routes": {
            "GET /orders": "List normalized orders",
            "GET /shipments": "List shipments",
            "GET /payments": "List payments",
            "POST /sync": "Run full mocked ingestion",
            "GET /chat/revenue": "Revenue + citations",
            "GET /chat/rto": "RTO orders + citations",
            "GET /chat/order/{internal_order_id}": "One order + citations",
            "GET /chat/failed-shipments": "Failed/RTO-class shipments + citations",
            "POST /agent/run": "RTO monitoring agent",
        },
    }


@app.get("/orders", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db)) -> list[Order]:
    rows = crud.list_orders(db)
    return list(rows)


@app.get("/shipments", response_model=list[ShipmentOut])
def list_shipments(db: Session = Depends(get_db)) -> list[Shipment]:
    rows = crud.list_shipments(db)
    return list(rows)


@app.get("/payments", response_model=list[PaymentOut])
def list_payments(db: Session = Depends(get_db)) -> list[Payment]:
    rows = crud.list_payments(db)
    return list(rows)


@app.post("/sync", response_model=SyncSummary)
def run_sync(db: Session = Depends(get_db)) -> SyncSummary:
    try:
        return SyncService().run_full_sync(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/chat/revenue", response_model=ChatAnswer)
def chat_revenue(db: Session = Depends(get_db)) -> ChatAnswer:
    return chat_tools.get_total_revenue(db)


@app.get("/chat/rto", response_model=ChatAnswer)
def chat_rto(db: Session = Depends(get_db)) -> ChatAnswer:
    return chat_tools.get_rto_orders(db)


@app.get("/chat/order/{internal_order_id}", response_model=ChatAnswer)
def chat_order(internal_order_id: str, db: Session = Depends(get_db)) -> ChatAnswer:
    return chat_tools.get_order_by_id(db, internal_order_id)


@app.get("/chat/failed-shipments", response_model=ChatAnswer)
def chat_failed_shipments(db: Session = Depends(get_db)) -> ChatAnswer:
    return chat_tools.get_failed_shipments(db)


@app.post("/agent/run", response_model=AgentResult)
def run_agent(db: Session = Depends(get_db)) -> AgentResult:
    return RtoAgent().run(db)
