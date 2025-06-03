import logging
from datetime import datetime

from openg2p_g2p_bridge_bank_connectors.bank_connectors import (
    BankConnectorFactory,
)
from openg2p_g2p_bridge_models.models import (
    BenefitProgramConfiguration,
    DisbursementEnvelope,
    DisbursementEnvelopeBatchStatus,
    FundsAvailableWithBankEnum,
)
from sqlalchemy.orm import sessionmaker

from ..app import celery_app, get_engine
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = get_engine()


@celery_app.task(name="check_funds_with_bank_worker")
def check_funds_with_bank_worker(disbursement_envelope_id: str):
    _logger.info(f"Checking funds with bank for envelope: {disbursement_envelope_id}")
    session_maker = sessionmaker(bind=_engine, expire_on_commit=False)

    with session_maker() as session:
        envelope = (
            session.query(DisbursementEnvelope)
            .filter(
                DisbursementEnvelope.disbursement_envelope_id
                == disbursement_envelope_id
            )
            .first()
        )

        if not envelope:
            _logger.error(
                f"Disbursement Envelope not found for envelope id: {disbursement_envelope_id}"
            )
            return

        disbursement_envelope_batch_status = (
            session.query(DisbursementEnvelopeBatchStatus)
            .filter(
                DisbursementEnvelopeBatchStatus.disbursement_envelope_id
                == disbursement_envelope_id
            )
            .first()
        )

        if not disbursement_envelope_batch_status:
            _logger.error(
                f"Disbursement Envelope Batch Status not found for envelope id: {disbursement_envelope_id}"
            )
            return

        benefit_program_configuration = (
            session.query(BenefitProgramConfiguration)
            .filter(
                BenefitProgramConfiguration.benefit_program_mnemonic
                == envelope.benefit_program_mnemonic
            )
            .first()
        )

        total_funds_needed = envelope.total_disbursement_quantity
        bank_connector = BankConnectorFactory.get_component().get_bank_connector(
            benefit_program_configuration.sponsor_bank_code
        )

        try:
            funds_available = (
                bank_connector.check_funds(
                    benefit_program_configuration.sponsor_bank_account_number,
                    benefit_program_configuration.sponsor_bank_account_currency,
                    total_funds_needed,
                ).status
                == FundsAvailableWithBankEnum.FUNDS_AVAILABLE
            )

            if funds_available:
                disbursement_envelope_batch_status.funds_available_with_bank = (
                    FundsAvailableWithBankEnum.FUNDS_AVAILABLE.value
                )
            else:
                disbursement_envelope_batch_status.funds_available_with_bank = (
                    FundsAvailableWithBankEnum.FUNDS_NOT_AVAILABLE.value
                )

            disbursement_envelope_batch_status.funds_available_latest_timestamp = (
                datetime.now()
            )
            disbursement_envelope_batch_status.funds_available_latest_error_code = None
            disbursement_envelope_batch_status.funds_available_attempts += 1

        except Exception as e:
            _logger.error(
                f"Error checking funds with bank for envelope {disbursement_envelope_id}: {e}"
            )
            disbursement_envelope_batch_status.funds_available_with_bank = (
                FundsAvailableWithBankEnum.PENDING_CHECK.value
            )
            disbursement_envelope_batch_status.funds_available_latest_timestamp = (
                datetime.now()
            )
            disbursement_envelope_batch_status.funds_available_latest_error_code = str(
                e
            )
            disbursement_envelope_batch_status.funds_available_attempts += 1
        _logger.info(
            f"Checked funds with bank for envelope: {disbursement_envelope_id}"
        )
        session.commit()
