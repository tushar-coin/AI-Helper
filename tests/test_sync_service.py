from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.models import EntityMapping, Order, Payment, Provenance, Shipment
from services.sync_service import SyncService


def test_full_sync_ingests_all_mock_connector_data():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)

    db = SessionLocal()
    try:
        summary = SyncService().run_full_sync(db)

        assert summary.orders_upserted == 4
        assert summary.shipments_upserted == 4
        assert summary.payments_upserted == 4
        assert summary.mappings_touched == 12
        assert summary.provenance_rows_written == 60

        assert db.scalar(select(func.count(Order.internal_order_id))) == 4
        assert db.scalar(select(func.count(Shipment.internal_shipment_id))) == 4
        assert db.scalar(select(func.count(Payment.internal_payment_id))) == 4
        assert db.scalar(select(func.count(EntityMapping.id))) == 12
        assert db.scalar(select(func.count(Provenance.id))) == 60

        rto_count = db.scalar(
            select(func.count(Shipment.internal_shipment_id)).where(
                Shipment.shipment_status == "rto"
            )
        )
        paid_payment_count = db.scalar(
            select(func.count(Payment.internal_payment_id)).where(
                Payment.payment_status == "paid"
            )
        )

        assert rto_count == 2
        assert paid_payment_count == 3
    finally:
        db.close()
