import logging
from datetime import datetime

from openg2p_g2p_bridge_bank_connectors.bank_connectors import BankConnectorFactory
from openg2p_g2p_bridge_bank_connectors.bank_interface import (
    BankConnectorInterface,
    BlockFundsResponse,
)
from openg2p_g2p_bridge_models.models import (
    BenefitProgramConfiguration,
    DisbursementEnvelope,
    DisbursementEnvelopeBatchStatus,
    FundsBlockedWithBankEnum,
)
from sqlalchemy.orm import sessionmaker

from ..app import celery_app, get_engine
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = get_engine()


@celery_app.task(name="block_funds_with_bank_worker")
def block_funds_with_bank_worker(disbursement_envelope_id: str):
    _logger.info(f"Blocking funds with bank for envelope: {disbursement_envelope_id}")
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

        batch_status = (
            session.query(DisbursementEnvelopeBatchStatus)
            .filter(
                DisbursementEnvelopeBatchStatus.disbursement_envelope_id
                == disbursement_envelope_id
            )
            .first()
        )

        if not batch_status:
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
        bank_connector: BankConnectorInterface = (
            BankConnectorFactory.get_component().get_bank_connector(
                benefit_program_configuration.sponsor_bank_code
            )
        )

        try:
            funds_blocked: BlockFundsResponse = bank_connector.block_funds(
                benefit_program_configuration.sponsor_bank_account_number,
                benefit_program_configuration.sponsor_bank_account_currency,
                total_funds_needed,
            )

            if funds_blocked.status == FundsBlockedWithBankEnum.FUNDS_BLOCK_SUCCESS:
                batch_status.funds_blocked_with_bank = (
                    FundsBlockedWithBankEnum.FUNDS_BLOCK_SUCCESS.value
                )
                batch_status.funds_blocked_reference_number = (
                    funds_blocked.block_reference_no
                )
                batch_status.funds_blocked_latest_error_code = None
            else:
                batch_status.funds_blocked_with_bank = (
                    FundsBlockedWithBankEnum.FUNDS_BLOCK_FAILURE.value
                )
                batch_status.funds_blocked_reference_number = ""
                batch_status.funds_blocked_latest_error_code = funds_blocked.error_code

            batch_status.funds_blocked_latest_timestamp = datetime.now()

            batch_status.funds_blocked_attempts += 1

        except Exception as e:
            _logger.error(
                f"Error blocking funds with bank for envelope {disbursement_envelope_id}: {str(e)}"
            )
            batch_status.funds_blocked_with_bank = (
                FundsBlockedWithBankEnum.PENDING_CHECK.value
            )
            batch_status.funds_blocked_latest_timestamp = datetime.now()
            batch_status.funds_blocked_latest_error_code = str(e)
            batch_status.funds_blocked_attempts += 1
            batch_status.funds_blocked_reference_number = ""
            session.commit()

        session.commit()
        _logger.info(
            f"Completed blocking funds with bank for envelope: {disbursement_envelope_id}"
        )
