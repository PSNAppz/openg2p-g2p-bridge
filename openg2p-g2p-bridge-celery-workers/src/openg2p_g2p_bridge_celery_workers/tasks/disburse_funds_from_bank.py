import logging
import random
import time
from datetime import datetime

from openg2p_g2p_bridge_bank_connectors.bank_connectors import BankConnectorFactory
from openg2p_g2p_bridge_bank_connectors.bank_interface.bank_connector_interface import (
    BankConnectorInterface,
    DisbursementPaymentPayload,
    PaymentStatus,
)
from openg2p_g2p_bridge_models.models import (
    BankDisbursementBatchStatus,
    BenefitProgramConfiguration,
    Disbursement,
    DisbursementBatchControl,
    DisbursementEnvelope,
    DisbursementEnvelopeBatchStatus,
    MapperResolutionDetails,
    ProcessStatus,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from ..app import celery_app, get_engine
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = get_engine()


@celery_app.task(name="disburse_funds_from_bank_worker")
def disburse_funds_from_bank_worker(bank_disbursement_batch_id: str):
    _logger.info(f"Disbursing funds with bank for batch: {bank_disbursement_batch_id}")
    session_maker = sessionmaker(bind=_engine, expire_on_commit=False)

    with session_maker() as session:
        disbursement_batch_status = (
            session.query(BankDisbursementBatchStatus)
            .filter(BankDisbursementBatchStatus.bank_disbursement_batch_id == bank_disbursement_batch_id)
            .first()
        )

        if not disbursement_batch_status:
            _logger.error(f"Bank Disbursement Batch Status not found for batch: {bank_disbursement_batch_id}")
            return

        disbursement_envelope_id = disbursement_batch_status.disbursement_envelope_id
        envelope = (
            session.query(DisbursementEnvelope)
            .filter(DisbursementEnvelope.disbursement_envelope_id == disbursement_envelope_id)
            .first()
        )

        if not envelope:
            _logger.error(f"Disbursement Envelope not found for envelope: {disbursement_envelope_id}")
            return

        envelope_batch_status = (
            session.query(DisbursementEnvelopeBatchStatus)
            .filter(DisbursementEnvelopeBatchStatus.disbursement_envelope_id == disbursement_envelope_id)
            .populate_existing()
            .first()
        )

        if not envelope_batch_status:
            _logger.error(
                f"Disbursement Envelope Batch Status not found for envelope: {disbursement_envelope_id}"
            )
            return

        disbursement_batch_controls = (
            session.query(DisbursementBatchControl)
            .filter(
                DisbursementBatchControl.bank_disbursement_batch_id == bank_disbursement_batch_id,
                DisbursementBatchControl.mapper_status.in_([ProcessStatus.PROCESSED.value]),
            )
            .all()
        )

        disbursement_ids = [control.disbursement_id for control in disbursement_batch_controls]
        disbursements = (
            session.query(Disbursement).filter(Disbursement.disbursement_id.in_(disbursement_ids)).all()
        )

        benefit_program_configuration = (
            session.query(BenefitProgramConfiguration)
            .filter(BenefitProgramConfiguration.benefit_program_mnemonic == envelope.benefit_program_mnemonic)
            .first()
        )

        payment_payloads = []

        for disbursement in disbursements:
            mapper_details = (
                session.query(MapperResolutionDetails)
                .filter(MapperResolutionDetails.disbursement_id == disbursement.disbursement_id)
                .first()
            )

            payment_payloads.append(
                DisbursementPaymentPayload(
                    disbursement_id=disbursement.disbursement_id,
                    remitting_account=benefit_program_configuration.sponsor_bank_account_number,
                    remitting_account_currency=benefit_program_configuration.sponsor_bank_account_currency,
                    payment_amount=disbursement.disbursement_amount,
                    funds_blocked_reference_number=envelope_batch_status.funds_blocked_reference_number,
                    beneficiary_account=mapper_details.bank_account_number if mapper_details else None,
                    beneficiary_account_currency=benefit_program_configuration.sponsor_bank_account_currency,
                    beneficiary_bank_code=mapper_details.bank_code if mapper_details else None,
                    beneficiary_branch_code=mapper_details.branch_code if mapper_details else None,
                    payment_date=str(datetime.date(datetime.now())),
                    beneficiary_id=disbursement.beneficiary_id,
                    beneficiary_name=disbursement.beneficiary_name,
                    beneficiary_account_type=mapper_details.mapper_resolved_fa_type,
                    beneficiary_phone_no=mapper_details.mobile_number if mapper_details else None,
                    beneficiary_mobile_wallet_provider=(
                        mapper_details.mobile_wallet_provider if mapper_details else None
                    ),
                    beneficiary_email_wallet_provider=(
                        mapper_details.email_wallet_provider if mapper_details else None
                    ),
                    beneficiary_email=mapper_details.email_address if mapper_details else None,
                    disbursement_narrative=disbursement.narrative,
                    benefit_program_mnemonic=envelope.benefit_program_mnemonic,
                    cycle_code_mnemonic=envelope.cycle_code_mnemonic,
                )
            )
        # End of for loop

        bank_connector: BankConnectorInterface = BankConnectorFactory.get_component().get_bank_connector(
            benefit_program_configuration.sponsor_bank_code
        )

        envelope_id = disbursement_batch_status.disbursement_envelope_id
        envelope = (
            session.query(DisbursementEnvelope)
            .filter(DisbursementEnvelope.disbursement_envelope_id == envelope_id)
            .first()
        )
        if not envelope:
            _logger.error(f"No DisbursementEnvelope {envelope_id}")
            return

        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                _logger.info(f"Locking envelope {envelope_id}, attempt {attempt} / {max_retries}")
                disbursement_envelope_batch_status = (
                    session.query(DisbursementEnvelopeBatchStatus)
                    .filter(DisbursementEnvelopeBatchStatus.disbursement_envelope_id == envelope_id)
                    .with_for_update(nowait=True)
                    .populate_existing()
                    .one()
                )
                _logger.info(f"Lock acquired for envelope {envelope_id}")
                _logger.info(f"Total number of disbursements: {len(payment_payloads)}")
                # fire the payment
                payment_response = bank_connector.initiate_payment(payment_payloads)
                _logger.info(
                    f"Payment response for envelope {envelope_id} on attempt {attempt}: {payment_response.status}"
                )

                # update envelope status
                if payment_response.status == PaymentStatus.SUCCESS:
                    disbursement_batch_status.disbursement_status = ProcessStatus.PROCESSED.value
                    disbursement_batch_status.latest_error_code = None
                    disbursement_envelope_batch_status.number_of_disbursements_shipped += len(
                        payment_payloads
                    )
                else:
                    disbursement_batch_status.disbursement_status = ProcessStatus.PENDING.value
                    disbursement_batch_status.latest_error_code = payment_response.error_code

                disbursement_batch_status.disbursement_timestamp = datetime.now()
                disbursement_batch_status.disbursement_attempts += 1

                session.commit()
                break

            except OperationalError as oe:
                session.rollback()
                _logger.warning(f"Attempt {attempt} to lock envelope {envelope_id} failed: {oe}")
                if attempt < max_retries:
                    time.sleep(random.uniform(8, 15))
                else:
                    _logger.error(f"Could not lock after {max_retries} tries, marking pending")
                    disbursement_batch_status.disbursement_status = ProcessStatus.PENDING.value
                    disbursement_batch_status.latest_error_code = "LockTimeout"
                    disbursement_batch_status.disbursement_timestamp = datetime.now()
                    disbursement_batch_status.disbursement_attempts += 1
                    session.commit()

            except Exception as e:
                session.rollback()
                _logger.error(f"Unexpected error during disbursement for envelope {envelope_id}: {e}")
                disbursement_batch_status.disbursement_status = ProcessStatus.PENDING.value
                disbursement_batch_status.latest_error_code = str(e)
                disbursement_batch_status.disbursement_timestamp = datetime.now()
                disbursement_batch_status.disbursement_attempts += 1
                session.commit()

        _logger.info(f"Disbursement task for batch {bank_disbursement_batch_id} completed")
