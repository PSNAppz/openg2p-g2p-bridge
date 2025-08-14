import logging
from typing import Annotated

from fastapi import Depends
from openg2p_fastapi_common.controller import BaseController
from openg2p_g2p_bridge_models.errors.exceptions import (
    BenefitProgramConfigurationException,
    RequestValidationException,
)
from openg2p_g2p_bridge_models.schemas import (
    BenefitProgramConfigurationPayload,
    BenefitProgramConfigurationRequest,
    BenefitProgramConfigurationResponse,
)
from openg2p_g2pconnect_common_lib.jwt_signature_validator import JWTSignatureValidator

from ..config import Settings
from ..services import BenefitProgramConfigurationService, RequestValidation

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class BenefitProgramConfigurationController(BaseController):
    benefit_program_configuration_service: BenefitProgramConfigurationService = (
        BenefitProgramConfigurationService.get_cached_component()
    )
    request_validation: RequestValidation = RequestValidation.get_cached_component()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.router.tags += ["G2P Bridge Benefit Program Configuration"]

        self.router.add_api_route(
            "/create_benefit_program_configuration",
            self.create_benefit_program_configuration,
            responses={200: {"model": BenefitProgramConfigurationResponse}},
            methods=["POST"],
        )

    async def create_benefit_program_configuration(
        self,
        benefit_program_configuration_request: BenefitProgramConfigurationRequest,
        is_signature_valid: Annotated[bool, Depends(JWTSignatureValidator())],
    ) -> BenefitProgramConfigurationResponse:
        _logger.info("Creating benefit program configuration")
        try:
            self.request_validation.validate_signature(is_signature_valid)
            self.request_validation.validate_request(benefit_program_configuration_request)

            benefit_program_configuration_payload: BenefitProgramConfigurationPayload = (
                await self.benefit_program_configuration_service.create_benefit_program_configuration(
                    benefit_program_configuration_request
                )
            )
        except RequestValidationException as e:
            _logger.error("Error validating request")
            error_response = await self.benefit_program_configuration_service.construct_benefit_program_configuration_error_response(
                e.code
            )
            return error_response
        except BenefitProgramConfigurationException as e:
            _logger.error("Error creating benefit program configuration")
            error_response = await self.benefit_program_configuration_service.construct_benefit_program_configuration_error_response(
                e.code
            )
            return error_response

        benefit_program_configuration_response = await self.benefit_program_configuration_service.construct_benefit_program_configuration_success_response(
            benefit_program_configuration_request, benefit_program_configuration_payload
        )
        _logger.info("Benefit program configuration created successfully")

        return benefit_program_configuration_response
