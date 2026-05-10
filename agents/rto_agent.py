"""
RTO monitoring agent (v0).

Scans normalized orders + shipments, flags high-value RTO patterns, and emits an
operational recommendation. No outbound notifications — analysis only.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from chat.tools import get_rto_orders_data
from db.schema import AgentResult, AgentRunLog


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
        logs.append(
            AgentRunLog(
                step="start",
                detail="Fetching RTO cohort via deterministic tool get_rto_orders_data.",
            )
        )

        rto_all = get_rto_orders_data(db, min_amount=0.0)
        rto_high_value = get_rto_orders_data(db, min_amount=float(self.min_amount))

        logs.append(
            AgentRunLog(
                step="evaluate",
                detail=(
                    f"Tool returned {rto_all.value} total RTO orders; "
                    f"{rto_high_value.value} are high-value (>= {self.min_amount})."
                ),
            )
        )

        if int(rto_high_value.value) == 0:
            logs.append(AgentRunLog(step="done", detail="No high-value RTO pattern detected"))
            return AgentResult(
                trigger_reason="No RTO shipments met the high-value threshold.",
                analyzed_data={
                    "rto_order_count": int(rto_all.value),
                    "high_value_rto_count": int(rto_high_value.value),
                    "citations": [c.model_dump() for c in rto_all.citations],
                },
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
            "rto_order_count": int(rto_all.value),
            "high_value_rto_count": int(rto_high_value.value),
            "high_value_rto": rto_high_value.records,
            "citations": [c.model_dump() for c in rto_high_value.citations],
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
