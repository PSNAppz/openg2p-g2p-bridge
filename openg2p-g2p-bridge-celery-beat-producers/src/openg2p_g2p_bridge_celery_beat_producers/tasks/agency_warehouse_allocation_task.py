import logging

from openg2p_g2p_bridge_models.models import (
    AgencyAllocationBatchStatus,
    WarehouseAllocationBatchStatus,
    ProcessStatus,
)
from sqlalchemy import and_, select
from sqlalchemy.orm import sessionmaker

from ..app import celery_app, get_engine
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = get_engine()


@celery_app.task(name="agency_allocation_beat_producer")
def agency_allocation_beat_producer():
    _logger.info("Running agency_allocation_beat_producer")
    session_maker = sessionmaker(bind=_engine, expire_on_commit=False)
    with session_maker() as session:
        batch_statuses = (
            session.execute(
                select(AgencyAllocationBatchStatus)
                .filter(
                    and_(
                        AgencyAllocationBatchStatus.allocation_status
                        == ProcessStatus.PENDING,
                        AgencyAllocationBatchStatus.allocation_attempts
                        < _config.mapper_resolve_attempts,
                    )
                )
                .limit(_config.no_of_tasks_to_process)
            )
            .scalars()
            .all()
        )
        for status in batch_statuses:
            _logger.info(
                f"Sending agency_allocation_worker task for batch_id: {status.agency_allocation_batch_id}"
            )
            status.allocation_status = ProcessStatus.PROCESSING
            celery_app.send_task(
                "agency_allocation_worker",
                args=[status.agency_allocation_batch_id],
                queue="g2p_bridge_celery_worker_tasks",
            )
            session.commit()
    _logger.info("Finished agency_allocation_beat_producer")


@celery_app.task(name="warehouse_allocation_beat_producer")
def warehouse_allocation_beat_producer():
    _logger.info("Running warehouse_allocation_beat_producer")
    session_maker = sessionmaker(bind=_engine, expire_on_commit=False)
    with session_maker() as session:
        batch_statuses = (
            session.execute(
                select(WarehouseAllocationBatchStatus)
                .filter(
                    and_(
                        WarehouseAllocationBatchStatus.allocation_status
                        == ProcessStatus.PENDING,
                        WarehouseAllocationBatchStatus.allocation_attempts
                        < _config.mapper_resolve_attempts,
                    )
                )
                .limit(_config.no_of_tasks_to_process)
            )
            .scalars()
            .all()
        )
        for status in batch_statuses:
            _logger.info(
                f"Sending warehouse_allocation_worker task for batch_id: {status.warehouse_allocation_batch_id}"
            )
            status.allocation_status = ProcessStatus.PROCESSING
            celery_app.send_task(
                "warehouse_allocation_worker",
                args=[status.warehouse_allocation_batch_id],
                queue="g2p_bridge_celery_worker_tasks",
            )
            session.commit()
    _logger.info("Finished warehouse_allocation_beat_producer")
