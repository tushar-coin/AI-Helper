"""
RTO monitoring agent (v0).

Scans normalized orders + shipments, flags high-value RTO patterns, and emits an
operational recommendation. No outbound notifications — analysis only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Order, Shipment
from db.schema import AgentResult, AgentRunLog


@dataclass
class RtoOrderInsight:
    internal_order_id: str
    customer_name: str
    amount: str
    currency: str
    shipment_id: str
    courier_name: str


class RtoAgent:
    """
    Example autonomous policy:

    If any order with amount >= `min_amount` has shipment_status == RTO,
    recommend tightening COD in high-RTO corridors (illustrative — not legal advice).
    """

    def __init__(self, *, min_amount: Decimal = Decimal("2000")) -> None:
        self.min_amount = min_amount

    def run(self, db: Session) -> AgentResult:
        logs: list[AgentRunLog] = []
        logs.append(AgentRunLog(step="start", detail="Scanning normalized orders and shipments"))

        stmt = (
            select(Order, Shipment)
            .join(Shipment, Shipment.internal_order_id == Order.internal_order_id)
            .where(Shipment.shipment_status == "rto")
        )
        rows = db.execute(stmt).all()

        high_value: list[RtoOrderInsight] = []
        for order, ship in rows:
            if Decimal(order.amount) >= self.min_amount:
                high_value.append(
                    RtoOrderInsight(
                        internal_order_id=order.internal_order_id,
                        customer_name=order.customer_name,
                        amount=str(order.amount),
                        currency=order.currency,
                        shipment_id=ship.internal_shipment_id,
                        courier_name=ship.courier_name,
                    )
                )

        logs.append(
            AgentRunLog(
                step="evaluate",
                detail=f"Found {len(rows)} RTO shipment rows; "
                f"{len(high_value)} are high-value (>= {self.min_amount}).",
            )
        )

        if not high_value:
            logs.append(AgentRunLog(step="done", detail="No high-value RTO pattern detected"))
            return AgentResult(
                trigger_reason="No RTO shipments met the high-value threshold.",
                analyzed_data={"rto_shipment_count": len(rows), "high_value_rto_count": 0},
                recommendation="No change suggested based on current thresholds.",
                run_logs=logs,
            )

        logs.append(
            AgentRunLog(
                step="trigger",
                detail="High-value RTO detected — generating operational recommendation.",
            )
        )

        analyzed = {
            "threshold_amount": str(self.min_amount),
            "high_value_rto": [asdict(x) for x in high_value],
        }
        recommendation = (
            "Pause or tighten COD on high-ticket SKUs in lanes showing repeated RTO with the "
            "same courier profile; validate addresses on checkout and consider prepaid incentives."
        )

        logs.append(AgentRunLog(step="done", detail="Recommendation materialized (no notifications sent)"))

        return AgentResult(
            trigger_reason="At least one order >= threshold has an RTO shipment.",
            analyzed_data=analyzed,
            recommendation=recommendation,
            run_logs=logs,
        )
