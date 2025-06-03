from datetime import datetime
from enum import Enum

from openg2p_fastapi_common.models import BaseORMModelWithTimes
from sqlalchemy import Boolean, Date, DateTime, Integer, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column


class FundsAvailableWithBankEnum(Enum):
    PENDING_CHECK = "PENDING_CHECK"
    CHECK_IN_PROGRESS = "CHECK_IN_PROGRESS"
    FUNDS_AVAILABLE = "FUNDS_AVAILABLE"
    FUNDS_NOT_AVAILABLE = "FUNDS_NOT_AVAILABLE"
    ERROR = "ERROR"


class FundsBlockedWithBankEnum(Enum):
    PENDING_CHECK = "PENDING_CHECK"
    CHECK_IN_PROGRESS = "CHECK_IN_PROGRESS"
    FUNDS_BLOCK_SUCCESS = "FUNDS_BLOCK_SUCCESS"
    FUNDS_BLOCK_FAILURE = "FUNDS_BLOCK_FAILURE"
    ERROR = "ERROR"


class DisbursementFrequency(Enum):
    Daily = "Daily"
    Weekly = "Weekly"
    Fortnightly = "Fortnightly"
    Monthly = "Monthly"
    BiMonthly = "BiMonthly"
    Quarterly = "Quarterly"
    SemiAnnually = "SemiAnnually"
    Annually = "Annually"
    OnDemand = "OnDemand"


class CancellationStatus(Enum):
    Not_Cancelled = "Not_Cancelled"
    Cancelled = "Cancelled"


class BenefitType(Enum):
    CASH = "CASH"
    COMMODITY = "COMMODITY"
    COMBINATION = "COMBINATION"


class DistributionModeForCash(Enum):
    PHYSICAL = "Physical"
    DIGITAL = "Digital"


class DisbursementEnvelope(BaseORMModelWithTimes):
    __tablename__ = "disbursement_envelopes"
    disbursement_envelope_id: Mapped[str] = mapped_column(String, unique=True)
    benefit_code: Mapped[str] = mapped_column(String)
    benefit_program_mnemonic: Mapped[str] = mapped_column(String)
    disbursement_frequency: Mapped[DisbursementFrequency] = mapped_column(
        SqlEnum(DisbursementFrequency)
    )
    cycle_code_mnemonic: Mapped[str] = mapped_column(String)
    number_of_beneficiaries: Mapped[int] = mapped_column(Integer)
    number_of_disbursements: Mapped[int] = mapped_column(Integer)
    total_disbursement_quantity: Mapped[float] = mapped_column(Integer)
    measurement_unit: Mapped[str] = mapped_column(String)
    benefit_type: Mapped[BenefitType] = mapped_column(SqlEnum(BenefitType))
    distribution_mode_for_cash: Mapped[DistributionModeForCash] = mapped_column(SqlEnum(DistributionModeForCash), nullable=True)
    disbursement_currency_code: Mapped[str] = mapped_column(String)
    disbursement_schedule_date: Mapped[datetime.date] = mapped_column(Date())
    receipt_time_stamp: Mapped[datetime] = mapped_column(
        DateTime(), default=datetime.now()
    )
    cancellation_status: Mapped[CancellationStatus] = mapped_column(
        String, default=CancellationStatus.Not_Cancelled
    )
    cancellation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(), nullable=True, default=None
    )


class DisbursementEnvelopeBatchStatus(BaseORMModelWithTimes):
    __tablename__ = "disbursement_envelope_batch_statuses"
    disbursement_envelope_id: Mapped[str] = mapped_column(String, unique=True)
    number_of_disbursements_received: Mapped[int] = mapped_column(Integer)
    total_disbursement_quantity_received: Mapped[int] = mapped_column(Integer)
    funds_available_with_bank: Mapped[FundsAvailableWithBankEnum] = mapped_column(
        String
    )
    funds_available_latest_timestamp: Mapped[datetime] = mapped_column(
        DateTime(), default=None, nullable=True
    )
    funds_available_latest_error_code: Mapped[str] = mapped_column(
        String, nullable=True
    )
    funds_available_attempts: Mapped[int] = mapped_column(Integer, default=0)

    funds_blocked_with_bank: Mapped[FundsBlockedWithBankEnum] = mapped_column(String)
    funds_blocked_latest_timestamp: Mapped[datetime] = mapped_column(
        DateTime(), default=None, nullable=True
    )
    funds_blocked_latest_error_code: Mapped[str] = mapped_column(String, nullable=True)
    funds_blocked_attempts: Mapped[int] = mapped_column(Integer, default=0)
    funds_blocked_reference_number: Mapped[str] = mapped_column(String, nullable=True)

    id_mapper_resolution_required: Mapped[bool] = mapped_column(Boolean, default=True)

    number_of_disbursements_shipped: Mapped[int] = mapped_column(Integer, default=0)
    number_of_disbursements_reconciled: Mapped[int] = mapped_column(Integer, default=0)
    number_of_disbursements_reversed: Mapped[int] = mapped_column(Integer, default=0)
