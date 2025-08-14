import logging
from typing import Annotated

from fastapi import Depends
from openg2p_fastapi_common.controller import BaseController
from openg2p_g2p_bridge_models.errors.exceptions import (
    DisbursementException,
    RequestValidationException,
)
from openg2p_g2p_bridge_models.schemas import (
    DisbursementRequest,
    DisbursementResponse,
)
from openg2p_g2pconnect_common_lib.jwt_signature_validator import JWTSignatureValidator

from ..config import Settings
from ..services import DisbursementService, RequestValidation

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class DisbursementController(BaseController):
    disbursement_service: DisbursementService = DisbursementService.get_cached_component()
    request_validation: RequestValidation = RequestValidation.get_cached_component()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.router.tags += ["G2P Bridge Disbursement Envelope"]

        self.router.add_api_route(
            "/create_disbursements",
            self.create_disbursements,
            responses={200: {"model": DisbursementResponse}},
            methods=["POST"],
        )
        self.router.add_api_route(
            "/cancel_disbursements",
            self.cancel_disbursements,
            responses={200: {"model": DisbursementResponse}},
            methods=["POST"],
        )

    async def create_disbursements(
        self,
        disbursement_request: DisbursementRequest,
        is_signature_valid: Annotated[bool, Depends(JWTSignatureValidator())],
    ) -> DisbursementResponse:
        _logger.info("Creating disbursements")
        try:
            self.request_validation.validate_signature(is_signature_valid)
            self.request_validation.validate_request(disbursement_request)

            disbursement_payloads = await self.disbursement_service.create_disbursements(disbursement_request)
        except RequestValidationException as e:
            _logger.error("Error validating request")
            error_response: DisbursementResponse = (
                await self.disbursement_service.construct_disbursement_error_response(
                    disbursement_request, e.code, []
                )
            )
            return error_response
        except DisbursementException as e:
            _logger.error("Error creating disbursements")
            error_response: DisbursementResponse = (
                await self.disbursement_service.construct_disbursement_error_response(
                    disbursement_request, e.code, e.disbursement_payloads
                )
            )
            return error_response

        disbursement_response: DisbursementResponse = (
            await self.disbursement_service.construct_disbursement_success_response(
                disbursement_request, disbursement_payloads
            )
        )
        _logger.info("Disbursements created successfully")

        return disbursement_response

    async def cancel_disbursements(
        self,
        disbursement_request: DisbursementRequest,
        is_signature_valid: Annotated[bool, Depends(JWTSignatureValidator())],
    ) -> DisbursementResponse:
        _logger.info("Cancelling disbursements")
        try:
            self.request_validation.validate_signature(is_signature_valid)
            self.request_validation.validate_request(disbursement_request)

            disbursement_payloads = await self.disbursement_service.cancel_disbursements(disbursement_request)
        except RequestValidationException as e:
            _logger.error("Error validating request")
            error_response: DisbursementResponse = (
                await self.disbursement_service.construct_disbursement_error_response(
                    disbursement_request, e.code, e.disbursement_payloads
                )
            )
            return error_response
        except DisbursementException as e:
            _logger.error("Error cancelling disbursements")
            error_response: DisbursementResponse = (
                await self.disbursement_service.construct_disbursement_error_response(
                    disbursement_request, e.code, e.disbursement_payloads
                )
            )
            return error_response

        disbursement_response: DisbursementResponse = (
            await self.disbursement_service.construct_disbursement_success_response(
                disbursement_request, disbursement_payloads
            )
        )
        _logger.info("Disbursements cancelled successfully")
        return disbursement_response
