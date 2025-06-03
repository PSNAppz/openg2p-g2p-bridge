from openg2p_fastapi_common.models import BaseORMModelWithTimes
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column


class BenefitProgramConfiguration(BaseORMModelWithTimes):
    __tablename__ = "benefit_program_configurations"

    benefit_program_mnemonic: Mapped[str] = mapped_column(String, unique=True)
    benefit_program_name: Mapped[str] = mapped_column(String, nullable=False)
    funding_org_code: Mapped[str] = mapped_column(String, nullable=False)
    funding_org_name: Mapped[str] = mapped_column(String, nullable=False)
    sponsor_bank_code: Mapped[str] = mapped_column(String, nullable=False)
    sponsor_bank_account_number: Mapped[str] = mapped_column(String, nullable=False)
    sponsor_bank_branch_code: Mapped[str] = mapped_column(String, nullable=False)
    sponsor_bank_account_currency: Mapped[str] = mapped_column(String, nullable=False)
