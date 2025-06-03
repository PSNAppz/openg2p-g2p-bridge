import logging
from datetime import datetime

from openg2p_g2p_bridge_agency_connectors.agency_connectors import (
    AgencyConnectorFactory,
)
from openg2p_g2p_bridge_warehouse_connectors.warehouse_connectors import (
    WarehouseConnectorFactory,
)
from openg2p_g2p_bridge_models.models import (
    AgencyAllocationBatchStatus,
    AgencyAllocationDetails,
    WarehouseAllocationBatchStatus,
    WarehouseAllocationDetails,
    ProcessStatus,
)
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from ..app import celery_app, get_engine
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = get_engine()


@celery_app.task(name="agency_allocation_worker")
def agency_allocation_worker(allocation_batch_id: str):
    _logger.info(f"Allocating agencies for batch: {allocation_batch_id}")
    session_maker = sessionmaker(bind=_engine, expire_on_commit=False)

    with session_maker() as session:
        agencies = (
            session.execute(
                select(AgencyAllocationDetails.agency_code).filter(
                    AgencyAllocationDetails.agency_allocation_batch_id
                    == allocation_batch_id
                )
            )
            .scalars()
            .all()
        )

        if not agencies:
            _logger.error(f"No agencies found for batch {allocation_batch_id}")
            return

        connector = AgencyConnectorFactory.get_component().get_agency_connector("EXAMPLE")

        try:
            connector.allocate_agency(agencies)
            status = ProcessStatus.PROCESSED
            error_code = None
        except Exception as e:
            _logger.error(
                f"Failed to allocate agency batch {allocation_batch_id}: {e}"
            )
            status = ProcessStatus.PENDING
            error_code = str(e)

        session.query(AgencyAllocationBatchStatus).filter(
            AgencyAllocationBatchStatus.agency_allocation_batch_id == allocation_batch_id
        ).update(
            {
                AgencyAllocationBatchStatus.allocation_status: status,
                AgencyAllocationBatchStatus.allocation_time_stamp: datetime.now(),
                AgencyAllocationBatchStatus.latest_error_code: error_code,
                AgencyAllocationBatchStatus.allocation_attempts: AgencyAllocationBatchStatus.allocation_attempts
                + 1,
            }
        )
        session.commit()


@celery_app.task(name="warehouse_allocation_worker")
def warehouse_allocation_worker(allocation_batch_id: str):
    _logger.info(f"Allocating warehouses for batch: {allocation_batch_id}")
    session_maker = sessionmaker(bind=_engine, expire_on_commit=False)

    with session_maker() as session:
        warehouses = (
            session.execute(
                select(WarehouseAllocationDetails.warehouse_code).filter(
                    WarehouseAllocationDetails.warehouse_allocation_batch_id
                    == allocation_batch_id
                )
            )
            .scalars()
            .all()
        )

        if not warehouses:
            _logger.error(
                f"No warehouses found for batch {allocation_batch_id}"
            )
            return

        connector = (
            WarehouseConnectorFactory.get_component().get_warehouse_connector(
                "EXAMPLE"
            )
        )

        try:
            connector.allocate_warehouse(warehouses)
            status = ProcessStatus.PROCESSED
            error_code = None
        except Exception as e:
            _logger.error(
                f"Failed to allocate warehouse batch {allocation_batch_id}: {e}"
            )
            status = ProcessStatus.PENDING
            error_code = str(e)

        session.query(WarehouseAllocationBatchStatus).filter(
            WarehouseAllocationBatchStatus.warehouse_allocation_batch_id
            == allocation_batch_id
        ).update(
            {
                WarehouseAllocationBatchStatus.allocation_status: status,
                WarehouseAllocationBatchStatus.allocation_time_stamp: datetime.now(),
                WarehouseAllocationBatchStatus.latest_error_code: error_code,
                WarehouseAllocationBatchStatus.allocation_attempts: WarehouseAllocationBatchStatus.allocation_attempts
                + 1,
            }
        )
        session.commit()
