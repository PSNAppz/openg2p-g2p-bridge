import logging
import uuid
from datetime import datetime
from typing import List

from openg2p_fastapi_common.context import dbengine
from openg2p_fastapi_common.service import BaseService
from openg2p_g2p_bridge_models.errors.codes import G2PBridgeErrorCodes
from openg2p_g2p_bridge_models.errors.exceptions import DisbursementEnvelopeException
from openg2p_g2p_bridge_models.models import (
    BenefitProgramConfiguration,
    CancellationStatus,
    DisbursementEnvelope,
    DisbursementEnvelopeBatchStatus,
    DisbursementFrequency,
    FundsAvailableWithBankEnum,
    FundsBlockedWithBankEnum,
)
from openg2p_g2p_bridge_models.schemas import (
    DisbursementEnvelopePayload,
    DisbursementEnvelopeRequest,
    DisbursementEnvelopeResponse,
    DisbursementEnvelopesRequest,
    DisbursementEnvelopesResponse,
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


class DisbursementEnvelopeService(BaseService):
    async def create_disbursement_envelope(
        self, disbursement_envelope_request: DisbursementEnvelopeRequest
    ) -> DisbursementEnvelopePayload:
        _logger.info("Creating disbursement envelope")
        session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
        async with session_maker() as session:
            try:
                await self.validate_envelope_request(disbursement_envelope_request)
            except DisbursementEnvelopeException as e:
                raise e

            disbursement_envelope: DisbursementEnvelope = (
                await self.construct_disbursement_envelope(
                    disbursement_envelope_payload=disbursement_envelope_request.message
                )
            )

            try:
                disbursement_envelope_batch_status: DisbursementEnvelopeBatchStatus = (
                    await self.construct_disbursement_envelope_batch_status(
                        disbursement_envelope, session
                    )
                )
            except Exception as e:
                _logger.error("Error creating disbursement envelope")
                await session.rollback()
                raise e

            session.add(disbursement_envelope)
            session.add(disbursement_envelope_batch_status)

            await session.commit()

            disbursement_envelope_payload: DisbursementEnvelopePayload = (
                disbursement_envelope_request.message
            )
            disbursement_envelope_payload.disbursement_envelope_id = (
                disbursement_envelope.disbursement_envelope_id
            )
            _logger.info("Disbursement envelope created successfully")
            return disbursement_envelope_payload

    async def create_disbursement_envelopes(
        self, disbursement_envelopes_request: DisbursementEnvelopesRequest
    ) -> List[DisbursementEnvelopePayload]:
        """Create multiple envelopes in one transaction."""

        _logger.info("Creating disbursement envelopes")
        session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
        async with session_maker() as session:
            created_payloads: List[DisbursementEnvelopePayload] = []
            for payload in disbursement_envelopes_request.message:
                # Validate each payload individually
                temp_request = DisbursementEnvelopeRequest(
                    header=disbursement_envelopes_request.header, message=payload
                )
                await self.validate_envelope_request(temp_request)

                envelope = await self.construct_disbursement_envelope(payload)
                batch_status = await self.construct_disbursement_envelope_batch_status(
                    envelope, session
                )
                session.add(envelope)
                session.add(batch_status)
                created_payloads.append(payload)

            await session.commit()
            _logger.info("Disbursement envelopes created successfully")
            return created_payloads

    async def cancel_disbursement_envelope(
        self, disbursement_envelope_request: DisbursementEnvelopeRequest
    ) -> DisbursementEnvelopePayload:
        _logger.info("Cancelling disbursement envelope")
        session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
        async with session_maker() as session:
            disbursement_envelope_payload: DisbursementEnvelopePayload = (
                disbursement_envelope_request.message
            )
            disbursement_envelope_id: str = (
                disbursement_envelope_payload.disbursement_envelope_id
            )

            disbursement_envelope: DisbursementEnvelope = (
                await session.execute(
                    select(DisbursementEnvelope).where(
                        DisbursementEnvelope.disbursement_envelope_id
                        == disbursement_envelope_id
                    )
                )
            ).scalar()

            if disbursement_envelope is None:
                _logger.error(
                    f"Disbursement envelope with ID {disbursement_envelope_id} not found"
                )
                raise DisbursementEnvelopeException(
                    G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_NOT_FOUND
                )

            if (
                disbursement_envelope.cancellation_status
                == CancellationStatus.Cancelled.value
            ):
                _logger.error(
                    f"Disbursement envelope with ID {disbursement_envelope_id} already cancelled"
                )
                raise DisbursementEnvelopeException(
                    G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_ALREADY_CANCELED
                )

            disbursement_envelope.cancellation_status = (
                CancellationStatus.Cancelled.value
            )
            disbursement_envelope.cancellation_timestamp = datetime.now()

            await session.commit()
            _logger.info("Disbursement envelope cancelled successfully")
            return disbursement_envelope_payload

    async def construct_disbursement_envelope_success_response(
        self,
        disbursement_envelope_request: DisbursementEnvelopeRequest,
        disbursement_envelope_payload: DisbursementEnvelopePayload,
    ) -> DisbursementEnvelopeResponse:
        _logger.info("Constructing disbursement envelope success response")
        disbursement_envelope_response: DisbursementEnvelopeResponse = (
            DisbursementEnvelopeResponse(
                header=SyncResponseHeader(
                    message_id=disbursement_envelope_request.header.message_id,
                    message_ts=datetime.now().isoformat(),
                    action=disbursement_envelope_request.header.action,
                    status=StatusEnum.succ,
                ),
                message=disbursement_envelope_payload,
            )
        )
        _logger.info("Disbursement envelope success response constructed")
        return disbursement_envelope_response

    async def construct_disbursement_envelopes_success_response(
        self,
        disbursement_envelope_request: DisbursementEnvelopesRequest,
        payloads: List[DisbursementEnvelopePayload],
    ) -> DisbursementEnvelopesResponse:
        """Construct success response for bulk creation."""

        _logger.info("Constructing bulk disbursement envelope success response")
        response = DisbursementEnvelopesResponse(
            header=SyncResponseHeader(
                message_id=disbursement_envelope_request.header.message_id,
                message_ts=datetime.now().isoformat(),
                action=disbursement_envelope_request.header.action,
                status=StatusEnum.succ,
            ),
            message=payloads,
        )
        _logger.info("Bulk disbursement envelope success response constructed")
        return response

    async def construct_disbursement_envelope_error_response(
        self,
        disbursement_envelope_request: DisbursementEnvelopeRequest,
        error_code: G2PBridgeErrorCodes,
    ) -> DisbursementEnvelopeResponse:
        _logger.error("Constructing disbursement envelope error response")
        disbursement_envelope_response: DisbursementEnvelopeResponse = (
            DisbursementEnvelopeResponse(
                header=SyncResponseHeader(
                    message_id=disbursement_envelope_request.header.message_id,
                    message_ts=datetime.now().isoformat(),
                    action=disbursement_envelope_request.header.action,
                    status=StatusEnum.rjct,
                    status_reason_message=error_code.value,
                ),
                message={},
            )
        )
        _logger.error("Disbursement envelope error response constructed")
        return disbursement_envelope_response

    async def construct_disbursement_envelopes_error_response(
        self,
        disbursement_envelope_request: DisbursementEnvelopesRequest,
        error_code: G2PBridgeErrorCodes,
    ) -> DisbursementEnvelopesResponse:
        """Construct error response for bulk envelope creation."""

        _logger.error("Constructing bulk disbursement envelope error response")
        response = DisbursementEnvelopesResponse(
            header=SyncResponseHeader(
                message_id=disbursement_envelope_request.header.message_id,
                message_ts=datetime.now().isoformat(),
                action=disbursement_envelope_request.header.action,
                status=StatusEnum.rjct,
                status_reason_message=error_code.value,
            ),
            message=[],
        )
        _logger.error("Bulk disbursement envelope error response constructed")
        return response

    # noinspection PyMethodMayBeStatic
    async def validate_envelope_request(
        self, disbursement_envelope_request: DisbursementEnvelopeRequest
    ) -> bool:
        _logger.info("Validating disbursement envelope request")
        disbursement_envelope_payload: DisbursementEnvelopePayload = (
            disbursement_envelope_request.message
        )
        if (
            disbursement_envelope_payload.benefit_code is None
            or disbursement_envelope_payload.benefit_code == ""
        ):
            _logger.error("Invalid benefit code")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_BENEFIT_CODE
            )
        if (
            disbursement_envelope_payload.benefit_program_mnemonic is None
            or disbursement_envelope_payload.benefit_program_mnemonic == ""
        ):
            _logger.error("Invalid benefit program mnemonic")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_PROGRAM_MNEMONIC
            )
        if (
            disbursement_envelope_payload.disbursement_frequency
            not in DisbursementFrequency
        ):
            _logger.error("Invalid disbursement frequency")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_DISBURSEMENT_FREQUENCY
            )
        if (
            disbursement_envelope_payload.cycle_code_mnemonic is None
            or disbursement_envelope_payload.cycle_code_mnemonic == ""
        ):
            _logger.error("Invalid cycle code mnemonic")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_CYCLE_CODE_MNEMONIC
            )
        if (
            disbursement_envelope_payload.number_of_beneficiaries is None
            or disbursement_envelope_payload.number_of_beneficiaries < 1
        ):
            _logger.error("Invalid number of beneficiaries")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_NO_OF_BENEFICIARIES
            )
        if (
            disbursement_envelope_payload.number_of_disbursements is None
            or disbursement_envelope_payload.number_of_disbursements < 1
        ):
            _logger.error("Invalid number of disbursements")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_NO_OF_DISBURSEMENTS
            )
        if (
            disbursement_envelope_payload.total_disbursement_quantity is None
            or disbursement_envelope_payload.total_disbursement_quantity < 0
        ):
            _logger.error("Invalid total disbursement quantity")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_TOTAL_DISBURSEMENT_QUANTITY
            )
        if (
            disbursement_envelope_payload.measurement_unit is None
            or disbursement_envelope_payload.measurement_unit == ""
        ):
            _logger.error("Invalid measurement unit")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_BENEFIT_CODE 
            )
        if (
            disbursement_envelope_payload.disbursement_schedule_date is None
            or disbursement_envelope_payload.disbursement_schedule_date
            < datetime.date(datetime.now())  # TODO: Add a delta of x days
        ):
            _logger.error("Invalid disbursement schedule date")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_DISBURSEMENT_SCHEDULE_DATE
            )
        _logger.info("Disbursement envelope request validated successfully")
        return True

    # noinspection PyMethodMayBeStatic
    async def construct_disbursement_envelope(
        self, disbursement_envelope_payload: DisbursementEnvelopePayload
    ) -> DisbursementEnvelope:
        _logger.info("Constructing disbursement envelope")
        disbursement_envelope: DisbursementEnvelope = DisbursementEnvelope(
            disbursement_envelope_id=str(uuid.uuid4()),
            benefit_code=disbursement_envelope_payload.benefit_code,
            benefit_program_mnemonic=disbursement_envelope_payload.benefit_program_mnemonic,
            disbursement_frequency=disbursement_envelope_payload.disbursement_frequency,
            cycle_code_mnemonic=disbursement_envelope_payload.cycle_code_mnemonic,
            number_of_beneficiaries=disbursement_envelope_payload.number_of_beneficiaries,
            number_of_disbursements=disbursement_envelope_payload.number_of_disbursements,
            total_disbursement_quantity=disbursement_envelope_payload.total_disbursement_quantity,
            measurement_unit=disbursement_envelope_payload.measurement_unit,
            disbursement_currency_code=disbursement_envelope_payload.disbursement_currency_code,
            disbursement_schedule_date=disbursement_envelope_payload.disbursement_schedule_date,
            receipt_time_stamp=datetime.now(),
            cancellation_status=CancellationStatus.Not_Cancelled.value,
            active=True,
        )
        disbursement_envelope_payload.id = disbursement_envelope.id
        disbursement_envelope_payload.disbursement_envelope_id = (
            disbursement_envelope.disbursement_envelope_id
        )
        _logger.info("Disbursement envelope constructed successfully")
        return disbursement_envelope

    # noinspection PyMethodMayBeStatic
    async def construct_disbursement_envelope_batch_status(
        self, disbursement_envelope: DisbursementEnvelope, session
    ) -> DisbursementEnvelopeBatchStatus:
        _logger.info("Constructing disbursement envelope batch status")
        benefit_program_configuration: BenefitProgramConfiguration = (
            (
                await session.execute(
                    select(BenefitProgramConfiguration).where(
                        BenefitProgramConfiguration.benefit_program_mnemonic
                        == disbursement_envelope.benefit_program_mnemonic
                    )
                )
            )
            .scalars()
            .first()
        )
        if benefit_program_configuration is None:
            _logger.error("Benefit program configuration not found")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_PROGRAM_MNEMONIC
            )

        disbursement_envelope_batch_status: DisbursementEnvelopeBatchStatus = DisbursementEnvelopeBatchStatus(
            disbursement_envelope_id=disbursement_envelope.disbursement_envelope_id,
            number_of_disbursements_received=0,
            total_disbursement_quantity_received=0,
            funds_available_with_bank=FundsAvailableWithBankEnum.PENDING_CHECK.value,
            funds_available_latest_timestamp=datetime.now(),
            funds_available_latest_error_code="",
            funds_available_attempts=0,
            funds_blocked_with_bank=FundsBlockedWithBankEnum.PENDING_CHECK.value,
            funds_blocked_latest_timestamp=datetime.now(),
            funds_blocked_attempts=0,
            funds_blocked_latest_error_code="",
            active=True,
        )
        _logger.info("Disbursement envelope batch status constructed successfully")
        return disbursement_envelope_batch_status

    async def validate_envelope_amend_request(
        self, disbursement_envelope_request: DisbursementEnvelopeRequest
    ) -> bool:
        _logger.info("Validating disbursement envelope amend request")
        disbursement_envelope_payload: DisbursementEnvelopePayload = (
            disbursement_envelope_request.message
        )
        if (
            disbursement_envelope_payload.disbursement_envelope_id is None
            or disbursement_envelope_payload.disbursement_envelope_id == ""
        ):
            _logger.error("Invalid disbursement envelope ID")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_DISBURSEMENT_ENVELOPE_ID
            )
        if (
            disbursement_envelope_payload.number_of_beneficiaries is None
            or disbursement_envelope_payload.number_of_beneficiaries < 1
        ):
            _logger.error("Invalid number of beneficiaries")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_NO_OF_BENEFICIARIES
            )
        if (
            disbursement_envelope_payload.number_of_disbursements is None
            or disbursement_envelope_payload.number_of_disbursements < 1
        ):
            _logger.error("Invalid number of disbursements")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_NO_OF_DISBURSEMENTS
            )
        if (
            disbursement_envelope_payload.total_disbursement_quantity is None
            or disbursement_envelope_payload.total_disbursement_quantity < 0
        ):
            _logger.error("Invalid total disbursement quantity")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_TOTAL_DISBURSEMENT_QUANTITY
            )
        if (
            disbursement_envelope_payload.measurement_unit is None
            or disbursement_envelope_payload.measurement_unit == ""
        ):
            _logger.error("Invalid measurement unit")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_BENEFIT_CODE  # Consider a new error code
            )
        if (
            disbursement_envelope_payload.disbursement_schedule_date is None
            or disbursement_envelope_payload.disbursement_schedule_date
            < datetime.date(datetime.now())
        ):
            _logger.error("Invalid disbursement schedule date")
            raise DisbursementEnvelopeException(
                G2PBridgeErrorCodes.INVALID_DISBURSEMENT_SCHEDULE_DATE
            )
        return True

    async def update_disbursement_envelope(
        self, disbursement_envelope_payload: DisbursementEnvelopePayload, session
    ) -> DisbursementEnvelopePayload:
        _logger.info("Updating disbursement envelope")
        disbursement_envelope: DisbursementEnvelope = (
            await session.execute(
                select(DisbursementEnvelope).where(
                    DisbursementEnvelope.id == disbursement_envelope_payload.id
                )
            )
        ).scalar()

        disbursement_envelope.number_of_beneficiaries = (
            disbursement_envelope_payload.number_of_beneficiaries
        )
        disbursement_envelope.number_of_disbursements = (
            disbursement_envelope_payload.number_of_disbursements
        )
        disbursement_envelope.total_disbursement_quantity = (
            disbursement_envelope_payload.total_disbursement_quantity
        )
        disbursement_envelope.measurement_unit = (
            disbursement_envelope_payload.measurement_unit
        )
        disbursement_envelope.disbursement_schedule_date = (
            disbursement_envelope_payload.disbursement_schedule_date
        )

        await session.commit()
        _logger.info("Disbursement envelope updated successfully")
        return disbursement_envelope_payload

    async def amend_disbursement_envelope(
        self, disbursement_envelope_request: DisbursementEnvelopeRequest
    ) -> DisbursementEnvelopePayload:
        _logger.info("Amending disbursement envelope")
        session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
        async with session_maker() as session:
            try:
                await self.validate_envelope_amend_request(
                    disbursement_envelope_request
                )
            except DisbursementEnvelopeException as e:
                raise e

            disbursement_envelope_payload: DisbursementEnvelopePayload = (
                disbursement_envelope_request.message
            )
            disbursement_envelope_id: str = (
                disbursement_envelope_payload.disbursement_envelope_id
            )

            result = await session.execute(
                select(DisbursementEnvelope)
                .where(
                    DisbursementEnvelope.disbursement_envelope_id
                    == disbursement_envelope_id
                )
                .with_for_update()
            )
            disbursement_envelope: DisbursementEnvelope = result.scalar_one_or_none()

            if disbursement_envelope is None:
                _logger.error(
                    f"Disbursement envelope with ID {disbursement_envelope_id} not found"
                )
                raise DisbursementEnvelopeException(
                    G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_NOT_FOUND
                )

            if (
                disbursement_envelope.cancellation_status
                == CancellationStatus.Cancelled.value
            ):
                _logger.error(
                    f"Disbursement envelope with ID {disbursement_envelope_id} already cancelled"
                )
                raise DisbursementEnvelopeException(
                    G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_ALREADY_CANCELED
                )

            if disbursement_envelope.disbursement_schedule_date <= datetime.date(
                datetime.now()
            ):
                _logger.error(
                    f"Disbursement envelope with ID {disbursement_envelope_id} date is already passed"
                )
                raise DisbursementEnvelopeException(
                    G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_DATE_PASSED
                )

            disbursement_envelope_payload.disbursement_envelope_id = (
                disbursement_envelope_id
            )
            disbursement_envelope_payload.id = disbursement_envelope.id

            disbursement_envelope_payload = await self.update_disbursement_envelope(
                disbursement_envelope_payload, session
            )

            await session.commit()
            _logger.info("Disbursement envelope amended successfully")
            return disbursement_envelope_payload
