import logging
from datetime import datetime

from openg2p_fastapi_common.context import dbengine
from openg2p_fastapi_common.service import BaseService
from openg2p_g2p_bridge_models.errors.codes import G2PBridgeErrorCodes
from openg2p_g2p_bridge_models.errors.exceptions import DisbursementStatusException
from openg2p_g2p_bridge_models.models import (
    DisbursementEnvelopeBatchStatus,
)
from openg2p_g2p_bridge_models.schemas import (
    DisbursementEnvelopeBatchStatusPayload,
    DisbursementEnvelopeStatusRequest,
    DisbursementEnvelopeStatusResponse,
    DisbursementStatusRequest,
)
from openg2p_g2pconnect_common_lib.schemas import (
    StatusEnum,
    SyncResponseHeader,
)
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.future import select

from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class DisbursementEnvelopeStatusService(BaseService):
    async def get_disbursement_envelope_batch_status(
        self, disbursement_envelope_status_request: DisbursementEnvelopeStatusRequest
    ) -> DisbursementEnvelopeBatchStatusPayload:
        session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
        async with session_maker() as session:
            try:
                _logger.info(
                    f"Retrieving disbursement envelope status for {disbursement_envelope_status_request.message}"
                )
                disbursement_envelope_batch_status = (
                    (
                        await session.execute(
                            select(DisbursementEnvelopeBatchStatus).where(
                                DisbursementEnvelopeBatchStatus.disbursement_envelope_id
                                == disbursement_envelope_status_request.message
                            )
                        )
                    )
                    .scalars()
                    .first()
                )

                if disbursement_envelope_batch_status is None:
                    raise DisbursementStatusException(
                        message="Disbursement envelope not found",
                        code=G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_NOT_FOUND,
                    )
                disbursement_envelope_batch_status_payload = DisbursementEnvelopeBatchStatusPayload(
                    disbursement_envelope_id=disbursement_envelope_batch_status.disbursement_envelope_id,
                    number_of_disbursements_received=disbursement_envelope_batch_status.number_of_disbursements_received,
                    total_disbursement_quantity_received=disbursement_envelope_batch_status.total_disbursement_quantity_received,
                    funds_available_with_bank=disbursement_envelope_batch_status.funds_available_with_bank,
                    funds_available_latest_timestamp=disbursement_envelope_batch_status.funds_available_latest_timestamp,
                    funds_available_latest_error_code=disbursement_envelope_batch_status.funds_available_latest_error_code,
                    funds_available_attempts=disbursement_envelope_batch_status.funds_available_attempts,
                    funds_blocked_with_bank=disbursement_envelope_batch_status.funds_blocked_with_bank,
                    funds_blocked_latest_timestamp=disbursement_envelope_batch_status.funds_blocked_latest_timestamp,
                    funds_blocked_latest_error_code=disbursement_envelope_batch_status.funds_blocked_latest_error_code,
                    funds_blocked_attempts=disbursement_envelope_batch_status.funds_blocked_attempts,
                    funds_blocked_reference_number=disbursement_envelope_batch_status.funds_blocked_reference_number,
                    number_of_disbursements_shipped=disbursement_envelope_batch_status.number_of_disbursements_shipped,
                    number_of_disbursements_reconciled=disbursement_envelope_batch_status.number_of_disbursements_reconciled,
                    number_of_disbursements_reversed=disbursement_envelope_batch_status.number_of_disbursements_reversed,
                )
                return disbursement_envelope_batch_status_payload
            except DisbursementStatusException as e:
                _logger.error("Error retrieving disbursement envelope status")
                raise e

    async def construct_disbursement_envelope_status_error_response(
        self,
        disbursement_status_request: DisbursementStatusRequest,
        code: str,
    ) -> DisbursementEnvelopeStatusResponse:
        response = DisbursementEnvelopeStatusResponse(
            header=SyncResponseHeader(
                message_id=disbursement_status_request.header.message_id,
                message_ts=datetime.now().isoformat(),
                action=disbursement_status_request.header.action,
                status=StatusEnum.rjct,
                status_reason_message=code,
            ),
            message=None,
        )

        return response

    async def construct_disbursement_envelope_status_success_response(
        self,
        disbursement_status_request: DisbursementStatusRequest,
        disbursement_envelope_batch_status_payload: DisbursementEnvelopeBatchStatusPayload,
    ) -> DisbursementEnvelopeStatusResponse:
        response = DisbursementEnvelopeStatusResponse(
            header=SyncResponseHeader(
                message_id=disbursement_status_request.header.message_id,
                message_ts=datetime.now().isoformat(),
                action=disbursement_status_request.header.action,
                status=StatusEnum.succ,
            ),
            message=disbursement_envelope_batch_status_payload,
        )
        return response
