# ruff: noqa: E402

from .config import Settings

_config = Settings.get_config()

from celery import Celery
from openg2p_fastapi_common.app import Initializer as BaseInitializer
from openg2p_fastapi_common.exception import BaseExceptionHandler
from openg2p_g2p_bridge_bank_connectors.app import (
    Initializer as BankConnectorInitializer,
)
from openg2p_g2pconnect_mapper_lib.app import Initializer as MapperInitializer
from sqlalchemy import create_engine


class Initializer(BaseInitializer):
    def initialize(self, **kwargs):
        super().init_logger()
        super().init_app()
        BaseExceptionHandler()

        BankConnectorInitializer()
        MapperInitializer()


def get_engine():
    if _config.db_datasource:
        db_engine = create_engine(_config.db_datasource)
        return db_engine


celery_app = Celery(
    "g2p_bridge_celery_beat_producer",
    broker=_config.celery_broker_url,
    backend=_config.celery_backend_url,
    include=["openg2p_g2p_bridge_celery_beat_producers.tasks"],
)

celery_app.conf.beat_schedule = {
    "mapper_resolution_beat_producer": {
        "task": "mapper_resolution_beat_producer",
        "schedule": _config.mapper_resolve_frequency,
    },
    "agency_allocation_beat_producer": {
        "task": "agency_allocation_beat_producer",
        "schedule": _config.mapper_resolve_frequency,
    },
    "warehouse_allocation_beat_producer": {
        "task": "warehouse_allocation_beat_producer",
        "schedule": _config.mapper_resolve_frequency,
    },
    "check_funds_with_bank_beat_producer": {
        "task": "check_funds_with_bank_beat_producer",
        "schedule": _config.funds_available_check_frequency,
    },
    "block_funds_with_bank_beat_producer": {
        "task": "block_funds_with_bank_beat_producer",
        "schedule": _config.funds_blocked_frequency,
    },
    "disburse_funds_from_bank_beat_producer": {
        "task": "disburse_funds_from_bank_beat_producer",
        "schedule": _config.funds_disbursement_frequency,
    },
    "mt940_processor_beat_producer": {
        "task": "mt940_processor_beat_producer",
        "schedule": _config.mt940_processor_frequency,
    },
}
celery_app.conf.timezone = "UTC"
