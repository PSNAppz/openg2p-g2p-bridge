import logging
from typing import Annotated

from fastapi import Depends
from openg2p_fastapi_common.controller import BaseController
from openg2p_g2p_bridge_models.errors.exceptions import (
    DisbursementStatusException,
    RequestValidationException,
)
from openg2p_g2p_bridge_models.schemas import (
    DisbursementEnvelopeBatchStatusPayload,
    DisbursementEnvelopeStatusRequest,
    DisbursementEnvelopeStatusResponse,
)
from openg2p_g2pconnect_common_lib.jwt_signature_validator import JWTSignatureValidator

from ..config import Settings
from ..services import DisbursementEnvelopeStatusService, RequestValidation

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class DisbursementEnvelopeStatusController(BaseController):
    disbursement_envelope_status_service: DisbursementEnvelopeStatusService = (
        DisbursementEnvelopeStatusService.get_cached_component()
    )
    request_validation: RequestValidation = RequestValidation.get_cached_component()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.router.tags += ["G2P Bridge Disbursement Envelope Status"]

        self.router.add_api_route(
            "/get_disbursement_envelope_status",
            self.get_disbursement_envelope_status,
            responses={200: {"model": DisbursementEnvelopeStatusResponse}},
            methods=["POST"],
        )

    async def get_disbursement_envelope_status(
        self,
        disbursement_envelope_status_request: DisbursementEnvelopeStatusRequest,
        is_signature_valid: Annotated[bool, Depends(JWTSignatureValidator())],
    ) -> DisbursementEnvelopeStatusResponse:
        _logger.info("Getting disbursement envelope batch status payload")
        try:
            self.request_validation.validate_signature(is_signature_valid)
            self.request_validation.validate_request(disbursement_envelope_status_request)
            disbursement_envelope_batch_status_payload: DisbursementEnvelopeBatchStatusPayload = (
                await self.disbursement_envelope_status_service.get_disbursement_envelope_batch_status(
                    disbursement_envelope_status_request
                )
            )
            disbursement_status_response = await self.disbursement_envelope_status_service.construct_disbursement_envelope_status_success_response(
                disbursement_envelope_status_request,
                disbursement_envelope_batch_status_payload,
            )
            return disbursement_status_response

        except RequestValidationException as e:
            _logger.error("Error validating request")
            error_response = await self.disbursement_envelope_status_service.construct_disbursement_envelope_status_error_response(
                disbursement_envelope_status_request,
                e.code,
            )
            return error_response

        except DisbursementStatusException as e:
            _logger.error(f"Error in getting disbursement envelope status: {e}")
            error_response = await self.disbursement_envelope_status_service.construct_disbursement_envelope_status_error_response(
                disbursement_envelope_status_request,
                e.code,
            )
            return error_response
