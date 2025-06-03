from typing import Optional

from openg2p_g2pconnect_common_lib.schemas import Request, SyncResponse
from pydantic import BaseModel


class BenefitProgramConfigurationPayload(BaseModel):
    benefit_program_mnemonic: Optional[str] = None
    benefit_program_name: Optional[str] = None
    funding_org_code: Optional[str] = None
    funding_org_name: Optional[str] = None
    sponsor_bank_code: Optional[str] = None
    sponsor_bank_account_number: Optional[str] = None
    sponsor_bank_branch_code: Optional[str] = None
    sponsor_bank_account_currency: Optional[str] = None


class BenefitProgramConfigurationRequest(Request):
    message: BenefitProgramConfigurationPayload


class BenefitProgramConfigurationResponse(SyncResponse):
    message: Optional[BenefitProgramConfigurationPayload] = None
