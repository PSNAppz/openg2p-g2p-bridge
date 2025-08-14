import asyncio
import logging
import random
import uuid
from datetime import datetime
from typing import List

from fastnanoid import generate
from openg2p_fastapi_common.context import dbengine
from openg2p_fastapi_common.service import BaseService
from openg2p_g2p_bridge_models.errors.codes import G2PBridgeErrorCodes
from openg2p_g2p_bridge_models.errors.exceptions import DisbursementException
from openg2p_g2p_bridge_models.models import (
    BankDisbursementBatchStatus,
    CancellationStatus,
    Disbursement,
    DisbursementBatchControl,
    DisbursementCancellationStatus,
    DisbursementEnvelope,
    DisbursementEnvelopeBatchStatus,
    MapperResolutionBatchStatus,
    ProcessStatus,
)
from openg2p_g2p_bridge_models.schemas import (
    DisbursementPayload,
    DisbursementRequest,
    DisbursementResponse,
)
from openg2p_g2pconnect_common_lib.schemas import (
    StatusEnum,
    SyncResponseHeader,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.future import select

from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class DisbursementService(BaseService):
    async def create_disbursements(
        self, disbursement_request: DisbursementRequest
    ) -> List[DisbursementPayload]:
        _logger.info("Creating Disbursements")
        session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
        async with session_maker() as session:
            try:
                await self.validate_disbursement_envelope(
                    session=session,
                    disbursement_payloads=disbursement_request.message,
                )
            except DisbursementException as e:
                _logger.error(f"Error validating disbursement envelope: {str(e)}")
                raise e
            is_error_free = await self.validate_disbursement_request(
                disbursement_payloads=disbursement_request.message
            )

            if not is_error_free:
                _logger.error("Error validating disbursement request")
                raise DisbursementException(
                    code=G2PBridgeErrorCodes.INVALID_DISBURSEMENT_PAYLOAD,
                    disbursement_payloads=disbursement_request.message,
                )
            disbursements: List[Disbursement] = await self.construct_disbursements(
                disbursement_payloads=disbursement_request.message
            )
            disbursement_batch_controls = await self.construct_disbursement_batch_controls(
                disbursements=disbursements
            )

            # Lock the envelope batch status row for update (nowait)
            disbursement_envelope_batch_status = await self.update_disbursement_envelope_batch_status(
                disbursements, session
            )
            session.add_all(disbursements)
            session.add_all(disbursement_batch_controls)
            session.add(disbursement_envelope_batch_status)

            if disbursement_envelope_batch_status.id_mapper_resolution_required:
                mapper_resolution_batch_status: MapperResolutionBatchStatus = MapperResolutionBatchStatus(
                    mapper_resolution_batch_id=disbursement_batch_controls[0].mapper_resolution_batch_id,
                    resolution_status=ProcessStatus.PENDING,
                    latest_error_code="",
                    active=True,
                )
                session.add(mapper_resolution_batch_status)
                _logger.info("ID Mapper Resolution Batch Status Created!")

            bank_disbursement_batch_status: BankDisbursementBatchStatus = BankDisbursementBatchStatus(
                bank_disbursement_batch_id=disbursement_batch_controls[0].bank_disbursement_batch_id,
                disbursement_envelope_id=disbursement_batch_controls[0].disbursement_envelope_id,
                disbursement_status=ProcessStatus.PENDING,
                latest_error_code="",
                disbursement_attempts=0,
                active=True,
            )

            session.add(bank_disbursement_batch_status)
            await session.commit()
            _logger.info("Disbursements Created Successfully!")
            return disbursement_request.message

    async def update_disbursement_envelope_batch_status(self, disbursements, session):
        _logger.info("Updating Disbursement Envelope Batch Status")
        max_retries = 5
        last_exc = None

        while max_retries:
            try:
                result = await session.execute(
                    select(DisbursementEnvelopeBatchStatus)
                    .where(
                        DisbursementEnvelopeBatchStatus.disbursement_envelope_id
                        == str(disbursements[0].disbursement_envelope_id)
                    )
                    .with_for_update(nowait=True)
                )
                disbursement_envelope_batch_status = result.scalars().first()
                break

            except OperationalError as e:
                last_exc = e
                wait = random.randint(8, 15)
                _logger.warning(
                    f"Lock attempt failed updating envelope batch status: {e}. "
                    f"{max_retries} retries left, sleeping {wait}s…"
                )
                await asyncio.sleep(wait)
                max_retries -= 1

        else:
            _logger.error("Unable to acquire lock on DisbursementEnvelopeBatchStatus after retries")
            raise last_exc

        disbursement_envelope_batch_status.number_of_disbursements_received += len(disbursements)
        disbursement_envelope_batch_status.total_disbursement_amount_received += sum(
            d.disbursement_amount for d in disbursements
        )
        _logger.info("Disbursement Envelope Batch Status Updated!")
        return disbursement_envelope_batch_status

    async def construct_disbursements(
        self, disbursement_payloads: List[DisbursementPayload]
    ) -> List[Disbursement]:
        _logger.info("Constructing Disbursements")
        disbursements: List[Disbursement] = []
        for disbursement_payload in disbursement_payloads:
            generated_id: str = generate(size=16)
            disbursement = Disbursement(
                disbursement_id=generated_id,
                disbursement_envelope_id=str(disbursement_payload.disbursement_envelope_id),
                mis_reference_number=disbursement_payload.mis_reference_number,
                beneficiary_id=disbursement_payload.beneficiary_id,
                beneficiary_name=disbursement_payload.beneficiary_name,
                disbursement_amount=disbursement_payload.disbursement_amount,
                narrative=disbursement_payload.narrative,
                active=True,
            )
            disbursement_payload.id = disbursement.id
            disbursement_payload.disbursement_id = disbursement.disbursement_id
            disbursements.append(disbursement)
        _logger.info("Disbursements Constructed!")
        return disbursements

    async def construct_disbursement_batch_controls(self, disbursements: List[Disbursement]):
        _logger.info("Constructing Disbursement Batch Controls")
        disbursement_batch_controls = []
        mapper_resolution_batch_id = str(uuid.uuid4())
        bank_disbursement_batch_id = str(uuid.uuid4())
        for disbursement in disbursements:
            disbursement_batch_control = DisbursementBatchControl(
                disbursement_id=disbursement.disbursement_id,
                disbursement_envelope_id=str(disbursement.disbursement_envelope_id),
                beneficiary_id=disbursement.beneficiary_id,
                bank_disbursement_batch_id=bank_disbursement_batch_id,
                mapper_resolution_batch_id=mapper_resolution_batch_id,
                active=True,
            )
            disbursement_batch_controls.append(disbursement_batch_control)
        _logger.info("Disbursement Batch Controls Constructed!")
        return disbursement_batch_controls

    async def validate_disbursement_request(self, disbursement_payloads: List[DisbursementPayload]):
        _logger.info("Validating Disbursement Request")
        absolutely_no_error = True

        for disbursement_payload in disbursement_payloads:
            disbursement_payload.response_error_codes = []
            if disbursement_payload.disbursement_envelope_id is None:
                disbursement_payload.response_error_codes.append(
                    G2PBridgeErrorCodes.INVALID_DISBURSEMENT_ENVELOPE_ID
                )
            if disbursement_payload.disbursement_amount <= 0:
                disbursement_payload.response_error_codes.append(
                    G2PBridgeErrorCodes.INVALID_DISBURSEMENT_AMOUNT
                )
            if disbursement_payload.beneficiary_id is None or disbursement_payload.beneficiary_id == "":
                disbursement_payload.response_error_codes.append(G2PBridgeErrorCodes.INVALID_BENEFICIARY_ID)
            if disbursement_payload.beneficiary_name is None or disbursement_payload.beneficiary_name == "":
                disbursement_payload.response_error_codes.append(G2PBridgeErrorCodes.INVALID_BENEFICIARY_NAME)
            if disbursement_payload.narrative is None or disbursement_payload.narrative == "":
                disbursement_payload.response_error_codes.append(G2PBridgeErrorCodes.INVALID_NARRATIVE)

            if len(disbursement_payload.response_error_codes) > 0:
                absolutely_no_error = False
        _logger.info("Disbursement Request Validated!")
        return absolutely_no_error

    async def validate_disbursement_envelope(self, session, disbursement_payloads: List[DisbursementPayload]):
        _logger.info("Validating Disbursement Envelope")
        disbursement_envelope_id = disbursement_payloads[0].disbursement_envelope_id
        if not all(
            disbursement_payload.disbursement_envelope_id == disbursement_envelope_id
            for disbursement_payload in disbursement_payloads
        ):
            raise DisbursementException(
                G2PBridgeErrorCodes.MULTIPLE_ENVELOPES_FOUND,
                disbursement_payloads,
            )
        disbursement_envelope = (
            (
                await session.execute(
                    select(DisbursementEnvelope).where(
                        DisbursementEnvelope.disbursement_envelope_id == str(disbursement_envelope_id)
                    )
                )
            )
            .scalars()
            .first()
        )
        if not disbursement_envelope:
            _logger.error("Disbursement Envelope Not Found!")
            raise DisbursementException(
                G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_NOT_FOUND,
                disbursement_payloads,
            )

        if disbursement_envelope.cancellation_status == CancellationStatus.Cancelled:
            _logger.error("Disbursement Envelope Already Canceled!")
            raise DisbursementException(
                G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_ALREADY_CANCELED,
                disbursement_payloads,
            )

        disbursement_envelope_batch_status = (
            (
                await session.execute(
                    select(DisbursementEnvelopeBatchStatus).where(
                        DisbursementEnvelopeBatchStatus.disbursement_envelope_id
                        == str(disbursement_envelope_id)
                    )
                )
            )
            .scalars()
            .first()
        )

        no_of_disbursements_after_this_request = (
            len(disbursement_payloads) + disbursement_envelope_batch_status.number_of_disbursements_received
        )
        total_disbursement_amount_after_this_request = (
            sum([disbursement_payload.disbursement_amount for disbursement_payload in disbursement_payloads])
            + disbursement_envelope_batch_status.total_disbursement_amount_received
        )

        if no_of_disbursements_after_this_request > disbursement_envelope.number_of_disbursements:
            _logger.error("Number of Disbursements Exceeds Declared!")
            raise DisbursementException(
                G2PBridgeErrorCodes.NO_OF_DISBURSEMENTS_EXCEEDS_DECLARED,
                disbursement_payloads,
            )

        if total_disbursement_amount_after_this_request > disbursement_envelope.total_disbursement_amount:
            raise DisbursementException(
                G2PBridgeErrorCodes.TOTAL_DISBURSEMENT_AMOUNT_EXCEEDS_DECLARED,
                disbursement_payloads,
            )
        _logger.info("Disbursement Envelope Validated!")
        return True

    async def construct_disbursement_error_response(
        self,
        disbursement_request: DisbursementRequest,
        code: G2PBridgeErrorCodes,
        disbursement_payloads: List[DisbursementPayload],
    ) -> DisbursementResponse:
        _logger.info("Constructing Disbursement Error Response")
        disbursement_response: DisbursementResponse = DisbursementResponse(
            header=SyncResponseHeader(
                message_id=disbursement_request.header.message_id,
                message_ts=datetime.now().isoformat(),
                action=disbursement_request.header.action,
                status=StatusEnum.rjct,
                status_reason_message=code.value,
            ),
            message=disbursement_payloads,
        )
        _logger.info("Disbursement Error Response Constructed!")
        return disbursement_response

    async def construct_disbursement_success_response(
        self,
        disbursement_request: DisbursementRequest,
        disbursement_payloads: List[DisbursementPayload],
    ) -> DisbursementResponse:
        _logger.info("Constructing Disbursement Success Response")
        disbursement_response: DisbursementResponse = DisbursementResponse(
            header=SyncResponseHeader(
                message_id=disbursement_request.header.message_id,
                message_ts=datetime.now().isoformat(),
                action=disbursement_request.header.action,
                status=StatusEnum.succ,
            ),
            message=disbursement_payloads,
        )
        _logger.info("Disbursement Success Response Constructed!")
        return disbursement_response

    async def cancel_disbursements(
        self, disbursement_request: DisbursementRequest
    ) -> List[DisbursementPayload]:
        _logger.info("Cancelling Disbursements")
        session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
        async with session_maker() as session:
            is_payload_valid = await self.validate_request_payload(
                disbursement_payloads=disbursement_request.message
            )

            if not is_payload_valid:
                _logger.error("Error validating disbursement request")
                raise DisbursementException(
                    code=G2PBridgeErrorCodes.INVALID_DISBURSEMENT_PAYLOAD,
                    disbursement_payloads=disbursement_request.message,
                )

            # Fetch and lock disbursements for update (nowait)
            disbursements_in_db: List[Disbursement] = await self.fetch_disbursements_from_db(
                disbursement_request, session
            )
            if not disbursements_in_db:
                _logger.error("Disbursements not found in DB")
                raise DisbursementException(
                    code=G2PBridgeErrorCodes.INVALID_DISBURSEMENT_ID,
                    disbursement_payloads=disbursement_request.message,
                )

            try:
                await self.check_for_single_envelope(disbursements_in_db, disbursement_request.message)
            except DisbursementException as e:
                _logger.error(f"Error checking for single envelope: {str(e)}")
                raise e

            try:
                await self.validate_envelope_for_disbursement_cancellation(
                    disbursements_in_db=disbursements_in_db,
                    disbursement_payloads=disbursement_request.message,
                    session=session,
                )
            except DisbursementException as e:
                _logger.error(f"Error validating envelope for disbursement cancellation: {str(e)}")
                raise e

            invalid_disbursements_exist = await self.check_for_invalid_disbursements(
                disbursement_request, disbursements_in_db
            )
            if invalid_disbursements_exist:
                raise DisbursementException(
                    code=G2PBridgeErrorCodes.INVALID_DISBURSEMENT_PAYLOAD,
                    disbursement_payloads=disbursement_request.message,
                )

            for disbursement in disbursements_in_db:
                disbursement.cancellation_status = DisbursementCancellationStatus.CANCELLED
                disbursement.cancellation_time_stamp = datetime.now()

            # Lock the envelope batch status row for update (nowait)
            disbursement_envelope_batch_status = (
                (
                    await session.execute(
                        select(DisbursementEnvelopeBatchStatus)
                        .where(
                            DisbursementEnvelopeBatchStatus.disbursement_envelope_id
                            == str(disbursements_in_db[0].disbursement_envelope_id)
                        )
                        .with_for_update(nowait=True)
                    )
                )
                .scalars()
                .first()
            )
            disbursement_envelope_batch_status.number_of_disbursements_received -= len(disbursements_in_db)
            disbursement_envelope_batch_status.total_disbursement_amount_received -= sum(
                [disbursement.disbursement_amount for disbursement in disbursements_in_db]
            )

            session.add_all(disbursements_in_db)
            session.add(disbursement_envelope_batch_status)
            await session.commit()
            _logger.info("Disbursements Cancelled Successfully!")
            return disbursement_request.message

    async def check_for_single_envelope(self, disbursements_in_db, disbursement_payloads):
        _logger.info("Checking for Single Envelope")
        disbursement_envelope_ids = {
            disbursement.disbursement_envelope_id for disbursement in disbursements_in_db
        }
        if len(disbursement_envelope_ids) > 1:
            _logger.error("Multiple Envelopes Found!")
            raise DisbursementException(
                G2PBridgeErrorCodes.MULTIPLE_ENVELOPES_FOUND,
                disbursement_payloads,
            )
        _logger.info("Single Envelope Found!")
        return True

    async def check_for_invalid_disbursements(self, disbursement_request, disbursements_in_db) -> bool:
        _logger.info("Checking for Invalid Disbursements")
        invalid_disbursements_exist = False
        for disbursement_payload in disbursement_request.message:
            if disbursement_payload.disbursement_id not in [
                disbursement.disbursement_id for disbursement in disbursements_in_db
            ]:
                invalid_disbursements_exist = True
                disbursement_payload.response_error_codes.append(
                    G2PBridgeErrorCodes.INVALID_DISBURSEMENT_ID.value
                )
            if disbursement_payload.disbursement_id in [
                disbursement.disbursement_id
                for disbursement in disbursements_in_db
                if disbursement.cancellation_status == DisbursementCancellationStatus.CANCELLED
            ]:
                invalid_disbursements_exist = True
                disbursement_payload.response_error_codes.append(
                    G2PBridgeErrorCodes.DISBURSEMENT_ALREADY_CANCELED.value
                )
        _logger.info("Invalid Disbursements Checked!")
        return invalid_disbursements_exist

    async def fetch_disbursements_from_db(self, disbursement_request, session) -> List[Disbursement]:
        _logger.info("Fetching Disbursements from DB")
        max_retries = 5
        last_exc = None

        while max_retries:
            try:
                result = await session.execute(
                    select(Disbursement)
                    .where(
                        Disbursement.disbursement_id.in_(
                            [str(p.disbursement_id) for p in disbursement_request.message]
                        )
                    )
                    .with_for_update(nowait=True)
                )
                disbursements_in_db = result.scalars().all()
                break

            except OperationalError as e:
                last_exc = e
                wait = random.randint(8, 15)
                _logger.warning(
                    f"Lock attempt failed fetching disbursements: {e}. "
                    f"{max_retries} retries left, sleeping {wait}s…"
                )
                await asyncio.sleep(wait)
                max_retries -= 1

        else:
            _logger.error("Unable to acquire lock on Disbursement rows after retries")
            raise last_exc

        _logger.info("Disbursements Fetched from DB!")
        return disbursements_in_db

    async def validate_envelope_for_disbursement_cancellation(
        self,
        disbursements_in_db,
        disbursement_payloads: List[DisbursementPayload],
        session,
    ):
        _logger.info("Validating Envelope for Disbursement Cancellation")
        max_retries = 5
        last_exc = None

        while max_retries:
            try:
                result = await session.execute(
                    select(DisbursementEnvelope)
                    .where(
                        DisbursementEnvelope.disbursement_envelope_id
                        == str(disbursements_in_db[0].disbursement_envelope_id)
                    )
                    .with_for_update(nowait=True)
                )
                disbursement_envelope = result.scalars().first()
                break

            except OperationalError as e:
                last_exc = e
                wait = random.randint(8, 15)
                _logger.warning(
                    f"Lock attempt failed on DisbursementEnvelope: {e}. "
                    f"{max_retries} retries left, sleeping {wait}s…"
                )
                await asyncio.sleep(wait)
                max_retries -= 1

        else:
            _logger.error("Unable to lock DisbursementEnvelope after retries")
            raise last_exc

        if not disbursement_envelope:
            _logger.error("Disbursement Envelope Not Found!")
            raise DisbursementException(
                G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_NOT_FOUND,
                disbursement_payloads,
            )

        if disbursement_envelope.cancellation_status == CancellationStatus.Cancelled:
            _logger.error("Disbursement Envelope Already Canceled!")
            raise DisbursementException(
                G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_ALREADY_CANCELED,
                disbursement_payloads,
            )

        if disbursement_envelope.disbursement_schedule_date <= datetime.now().date():
            _logger.error("Disbursement Envelope Schedule Date Reached!")
            raise DisbursementException(
                G2PBridgeErrorCodes.DISBURSEMENT_ENVELOPE_SCHEDULE_DATE_REACHED,
                disbursement_payloads,
            )

        # we don’t need a lock for this read
        batch_status = (
            (
                await session.execute(
                    select(DisbursementEnvelopeBatchStatus).where(
                        DisbursementEnvelopeBatchStatus.disbursement_envelope_id
                        == str(disbursements_in_db[0].disbursement_envelope_id)
                    )
                )
            )
            .scalars()
            .first()
        )

        no_of_after = batch_status.number_of_disbursements_received - len(disbursements_in_db)
        total_amt_after = batch_status.total_disbursement_amount_received - sum(
            d.disbursement_amount for d in disbursements_in_db
        )

        if no_of_after < 0:
            _logger.error("Number of Disbursements Less Than Zero!")
            raise DisbursementException(
                G2PBridgeErrorCodes.NO_OF_DISBURSEMENTS_LESS_THAN_ZERO,
                disbursement_payloads,
            )

        if total_amt_after < 0:
            _logger.error("Total Disbursement Amount Less Than Zero!")
            raise DisbursementException(
                G2PBridgeErrorCodes.TOTAL_DISBURSEMENT_AMOUNT_LESS_THAN_ZERO,
                disbursement_payloads,
            )

        _logger.info("Envelope Validated for Disbursement Cancellation!")
        return True
