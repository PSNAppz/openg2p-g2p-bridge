import logging
from datetime import datetime

from openg2p_g2p_bridge_models.models import (
    CancellationStatus,
    DisbursementEnvelope,
    DisbursementEnvelopeBatchStatus,
    FundsAvailableWithBankEnum,
    FundsBlockedWithBankEnum,
)
from sqlalchemy import and_, literal, or_, select
from sqlalchemy.orm import sessionmaker

from ..app import celery_app, get_engine
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = get_engine()


@celery_app.task(name="block_funds_with_bank_beat_producer")
def block_funds_with_bank_beat_producer():
    _logger.info("Checking for envelopes to block funds with bank")
    session_maker = sessionmaker(bind=_engine, expire_on_commit=False)

    with session_maker() as session:
        # Check if the disbursement schedule date is today if the configuration is
        # not set to process future disbursement schedules
        date_condition = (
            DisbursementEnvelope.disbursement_schedule_date == datetime.now().date()
            if not _config.process_future_disbursement_schedules
            else literal(True)
        )

        envelopes = (
            session.execute(
                select(DisbursementEnvelope)
                .join(
                    DisbursementEnvelopeBatchStatus,
                    DisbursementEnvelope.disbursement_envelope_id
                    == DisbursementEnvelopeBatchStatus.disbursement_envelope_id,
                )
                .filter(
                    date_condition,
                    DisbursementEnvelope.cancellation_status
                    == CancellationStatus.Not_Cancelled.value,
                    DisbursementEnvelope.number_of_disbursements
                    == DisbursementEnvelopeBatchStatus.number_of_disbursements_received,
                    DisbursementEnvelopeBatchStatus.funds_available_with_bank
                    == FundsAvailableWithBankEnum.FUNDS_AVAILABLE.value,
                    or_(
                        and_(
                            DisbursementEnvelopeBatchStatus.funds_blocked_with_bank
                            == FundsBlockedWithBankEnum.PENDING_CHECK.value,
                            DisbursementEnvelopeBatchStatus.funds_blocked_attempts
                            < _config.funds_blocked_attempts,
                        ),
                        and_(
                            DisbursementEnvelopeBatchStatus.funds_blocked_with_bank
                            == FundsBlockedWithBankEnum.FUNDS_BLOCK_FAILURE.value,
                            DisbursementEnvelopeBatchStatus.funds_blocked_attempts
                            < _config.funds_blocked_attempts,
                        ),
                    ),
                )
                .limit(_config.no_of_tasks_to_process)
            )
            .scalars()
            .all()
        )
        _logger.info(f"Found {len(envelopes)} envelopes to block funds with bank")

        for envelope in envelopes:
            _logger.info(
                f"Blocking funds with bank for envelope: {envelope.disbursement_envelope_id}"
            )
            envelope_batch_status = (
                session.query(DisbursementEnvelopeBatchStatus)
                .filter(
                    DisbursementEnvelopeBatchStatus.disbursement_envelope_id
                    == envelope.disbursement_envelope_id
                )
                .first()
            )

            envelope_batch_status.funds_blocked_with_bank = (
                FundsBlockedWithBankEnum.CHECK_IN_PROGRESS.value
            )

            celery_app.send_task(
                "block_funds_with_bank_worker",
                args=(envelope.disbursement_envelope_id,),
                queue="g2p_bridge_celery_worker_tasks",
            )
            session.commit()

        _logger.info("Completed checking for envelopes to block funds with bank")
