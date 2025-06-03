import logging
from datetime import datetime

from openg2p_fastapi_common.context import dbengine
from openg2p_fastapi_common.service import BaseService
from openg2p_g2p_bridge_models.errors.codes import G2PBridgeErrorCodes
from openg2p_g2p_bridge_models.errors.exceptions import (
    BenefitProgramConfigurationException,
)
from openg2p_g2p_bridge_models.models import BenefitProgramConfiguration
from openg2p_g2p_bridge_models.schemas import (
    BenefitProgramConfigurationPayload,
    BenefitProgramConfigurationRequest,
    BenefitProgramConfigurationResponse,
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


class BenefitProgramConfigurationService(BaseService):
    async def create_benefit_program_configuration(
        self, benefit_program_configuration_request: BenefitProgramConfigurationRequest
    ) -> BenefitProgramConfigurationPayload:
        _logger.info("Creating Benefit Program Configuration")
        session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
        async with session_maker() as session:
            try:
                await self.validate_benefit_program_configuration_request(
                    session, benefit_program_configuration_request
                )
            except BenefitProgramConfigurationException as e:
                raise e

            benefit_program_configuration: BenefitProgramConfiguration = await self.construct_benefit_program_configuration(
                benefit_program_configuration_payload=benefit_program_configuration_request.message
            )
            _logger.info(f"BENF:{benefit_program_configuration}")
            session.add(benefit_program_configuration)
            await session.commit()
            _logger.info("Disbursements Created Successfully!")
            return benefit_program_configuration_request.message

    async def validate_benefit_program_configuration_request(
        self,
        session,
        benefit_program_configuration_request: BenefitProgramConfigurationRequest,
    ) -> bool:
        _logger.info("Validating disbursement envelope request")
        benefit_program_configuration_payload: BenefitProgramConfigurationPayload = (
            benefit_program_configuration_request.message
        )
        benefit_program_configuration: BenefitProgramConfiguration = (
            await session.execute(
                select(BenefitProgramConfiguration).where(
                    BenefitProgramConfiguration.benefit_program_mnemonic
                    == benefit_program_configuration_payload.benefit_program_mnemonic
                )
            )
        )
        benefit_program_configuration = benefit_program_configuration.scalars().first()

        _logger.info(f"Benefit Program Configuration: {benefit_program_configuration}")

        if benefit_program_configuration:
            raise BenefitProgramConfigurationException(
                message="Benefit Program Configuration already exists",
                code=G2PBridgeErrorCodes.BENEFIT_PROGRAM_CONFIGURATION_ALREADY_EXISTS,
            )

    # noinspection PyMethodMayBeStatic
    async def construct_benefit_program_configuration(
        self, benefit_program_configuration_payload: BenefitProgramConfigurationPayload
    ) -> BenefitProgramConfiguration:
        _logger.info("Constructing benefit program configuration")

        benefit_program_configuration = BenefitProgramConfiguration(
            benefit_program_mnemonic=benefit_program_configuration_payload.benefit_program_mnemonic,
            benefit_program_name=benefit_program_configuration_payload.benefit_program_name,
            funding_org_code=benefit_program_configuration_payload.funding_org_code,
            funding_org_name=benefit_program_configuration_payload.funding_org_name,
            sponsor_bank_code=benefit_program_configuration_payload.sponsor_bank_code,
            sponsor_bank_account_number=benefit_program_configuration_payload.sponsor_bank_account_number,
            sponsor_bank_branch_code=benefit_program_configuration_payload.sponsor_bank_branch_code,
            sponsor_bank_account_currency=benefit_program_configuration_payload.sponsor_bank_account_currency,
            active=True,
        )
        _logger.info(
            f"Benefit Program Configuration Constructed{benefit_program_configuration}"
        )
        return benefit_program_configuration

    async def construct_benefit_program_configuration_success_response(
        self,
        benefit_program_configuration_request: BenefitProgramConfigurationRequest,
        benefit_program_configuration_payload: BenefitProgramConfigurationPayload,
    ) -> BenefitProgramConfigurationResponse:
        _logger.info("Constructing Benefit Program Configuration Response")
        benefit_progra_configuration_response: BenefitProgramConfigurationResponse = (
            BenefitProgramConfigurationResponse(
                header=SyncResponseHeader(
                    message_id=benefit_program_configuration_request.header.message_id,
                    message_ts=datetime.now().isoformat(),
                    action=benefit_program_configuration_request.header.action,
                    status=StatusEnum.succ,
                ),
                message=benefit_program_configuration_payload,
            )
        )
        _logger.info("Benefit Program Configuration Success Response Constructed!")
        return benefit_progra_configuration_response

    async def construct_benefit_program_configuration_error_response(
        self, code: G2PBridgeErrorCodes
    ) -> BenefitProgramConfigurationResponse:
        _logger.error("Constructing account statement error response")
        return BenefitProgramConfigurationResponse(
            header=SyncResponseHeader(
                message_id="",
                message_ts=datetime.now().isoformat(),
                action="",
                status=StatusEnum.rjct,
                status_reason_message=code,
            ),
            message=None,
        )
