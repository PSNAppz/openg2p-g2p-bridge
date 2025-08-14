from datetime import datetime, timezone
from enum import Enum

from openg2p_fastapi_common.models import BaseORMModelWithTimes
from sqlalchemy import UUID, DateTime, Float, Integer, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from .common_enums import ProcessStatus


class DisbursementCancellationStatus(Enum):
    NOT_CANCELLED = "NOT_CANCELLED"
    CANCELLED = "CANCELLED"


class MapperResolvedFaType(Enum):
    BANK_ACCOUNT = "BANK_ACCOUNT"
    MOBILE_WALLET = "MOBILE_WALLET"
    EMAIL_WALLET = "EMAIL_WALLET"


class Disbursement(BaseORMModelWithTimes):
    __tablename__ = "disbursements"
    disbursement_id: Mapped[str] = mapped_column(String, unique=True)
    mis_reference_number: Mapped[str] = mapped_column(String, nullable=True, default=None)
    disbursement_envelope_id: Mapped[str] = mapped_column(String, index=True)
    beneficiary_id: Mapped[str] = mapped_column(String)
    beneficiary_name: Mapped[str] = mapped_column(String)
    disbursement_amount: Mapped[float] = mapped_column(Float)
    narrative: Mapped[str] = mapped_column(String)
    receipt_time_stamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(tz=timezone.utc).replace(tzinfo=None)
    )
    cancellation_status: Mapped[DisbursementCancellationStatus] = mapped_column(
        SqlEnum(DisbursementCancellationStatus),
        default=DisbursementCancellationStatus.NOT_CANCELLED,
    )
    cancellation_time_stamp: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)


class DisbursementBatchControl(BaseORMModelWithTimes):
    __tablename__ = "disbursement_batch_control"

    disbursement_id: Mapped[str] = mapped_column(String, unique=True)
    disbursement_envelope_id: Mapped[str] = mapped_column(String, index=True)
    beneficiary_id: Mapped[str] = mapped_column(String)
    bank_disbursement_batch_id = mapped_column(UUID, nullable=True, default=None, index=True)
    mapper_resolution_batch_id = mapped_column(UUID, nullable=True, default=None, index=True)
    mapper_status: Mapped[ProcessStatus] = mapped_column(
        SqlEnum(ProcessStatus), default=ProcessStatus.PENDING
    )
    latest_error_code: Mapped[str] = mapped_column(String, nullable=True, default=None)


class MapperResolutionBatchStatus(BaseORMModelWithTimes):
    __tablename__ = "mapper_resolution_batch_statuses"

    mapper_resolution_batch_id = mapped_column(UUID, nullable=True, default=None, index=True, unique=True)
    resolution_status: Mapped[ProcessStatus] = mapped_column(
        SqlEnum(ProcessStatus), default=ProcessStatus.PENDING
    )
    resolution_time_stamp: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)
    latest_error_code: Mapped[str] = mapped_column(String, nullable=True, default=None)
    resolution_attempts: Mapped[int] = mapped_column(Integer, nullable=True, default=0)


class MapperResolutionDetails(BaseORMModelWithTimes):
    __tablename__ = "mapper_resolution_details"

    mapper_resolution_batch_id = mapped_column(UUID, nullable=True, default=None, index=True)
    disbursement_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    beneficiary_id: Mapped[str] = mapped_column(String, index=True)
    mapper_resolved_fa: Mapped[str] = mapped_column(String, nullable=True, default=None)
    mapper_resolved_name: Mapped[str] = mapped_column(String, nullable=True, default=None)
    mapper_resolved_fa_type: Mapped[MapperResolvedFaType] = mapped_column(
        SqlEnum(MapperResolvedFaType), nullable=True, default=None
    )
    bank_account_number: Mapped[str] = mapped_column(String, nullable=True, default=None)
    bank_code: Mapped[str] = mapped_column(String, nullable=True, default=None)
    branch_code: Mapped[str] = mapped_column(String, nullable=True, default=None)
    mobile_number: Mapped[str] = mapped_column(String, nullable=True, default=None)
    mobile_wallet_provider: Mapped[str] = mapped_column(String, nullable=True, default=None)
    email_address: Mapped[str] = mapped_column(String, nullable=True, default=None)
    email_wallet_provider: Mapped[str] = mapped_column(String, nullable=True, default=None)


class BankDisbursementBatchStatus(BaseORMModelWithTimes):
    __tablename__ = "bank_disbursement_batch_statuses"

    bank_disbursement_batch_id: Mapped[UUID] = mapped_column(
        UUID, nullable=True, default=None, index=True, unique=True
    )
    disbursement_envelope_id: Mapped[str] = mapped_column(String, index=True)
    disbursement_status: Mapped[ProcessStatus] = mapped_column(
        SqlEnum(ProcessStatus), default=ProcessStatus.PENDING
    )
    disbursement_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)
    latest_error_code: Mapped[str] = mapped_column(String, nullable=True, default=None)
    disbursement_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
