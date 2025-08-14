from datetime import datetime, timezone

from openg2p_fastapi_common.models import BaseORMModelWithTimes
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from ..errors.codes import G2PBridgeErrorCodes
from .common_enums import ProcessStatus


class AccountStatement(BaseORMModelWithTimes):
    __tablename__ = "account_statements"
    statement_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    statement_date: Mapped[datetime] = mapped_column(DateTime)
    account_number: Mapped[str] = mapped_column(String, nullable=True)
    reference_number: Mapped[str] = mapped_column(String, nullable=True)
    statement_number: Mapped[str] = mapped_column(String, nullable=True)
    sequence_number: Mapped[str] = mapped_column(String, nullable=True)
    statement_upload_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(tz=timezone.utc).replace(tzinfo=None)
    )
    statement_process_status: Mapped[ProcessStatus] = mapped_column(
        SqlEnum(ProcessStatus), default=ProcessStatus.PENDING
    )
    statement_process_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)
    statement_process_error_code: Mapped[str] = mapped_column(String, nullable=True, default=None)
    statement_process_attempts: Mapped[int] = mapped_column(Integer, default=0)


class AccountStatementLob(BaseORMModelWithTimes):
    __tablename__ = "account_statement_lobs"
    statement_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    statement_lob: Mapped[str] = mapped_column(Text)


class DisbursementRecon(BaseORMModelWithTimes):
    __tablename__ = "disbursement_recons"
    bank_disbursement_batch_id: Mapped[str] = mapped_column(String, index=True)
    disbursement_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    disbursement_envelope_id: Mapped[str] = mapped_column(String, nullable=True)
    beneficiary_name_from_bank: Mapped[str] = mapped_column(String, nullable=True)

    remittance_reference_number: Mapped[str] = mapped_column(String, nullable=True, unique=True)
    remittance_statement_id: Mapped[str] = mapped_column(String, nullable=True)
    remittance_statement_number: Mapped[str] = mapped_column(String, nullable=True)
    remittance_statement_sequence: Mapped[str] = mapped_column(String, nullable=True)
    remittance_entry_sequence: Mapped[str] = mapped_column(String, nullable=True)
    remittance_entry_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    remittance_value_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    reversal_found: Mapped[bool] = mapped_column(Boolean, default=False)
    reversal_statement_id: Mapped[str] = mapped_column(String, nullable=True)
    reversal_statement_number: Mapped[str] = mapped_column(String, nullable=True)
    reversal_statement_sequence: Mapped[str] = mapped_column(String, nullable=True)
    reversal_entry_sequence: Mapped[str] = mapped_column(String, nullable=True)
    reversal_entry_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reversal_value_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reversal_reason: Mapped[str] = mapped_column(String, nullable=True)


class DisbursementErrorRecon(BaseORMModelWithTimes):
    __tablename__ = "disbursement_error_recons"

    statement_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    statement_number: Mapped[str] = mapped_column(String, nullable=True)
    statement_sequence: Mapped[str] = mapped_column(String, nullable=True)
    entry_sequence: Mapped[str] = mapped_column(String, nullable=True)
    entry_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    value_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    error_reason: Mapped[G2PBridgeErrorCodes] = mapped_column(SqlEnum(G2PBridgeErrorCodes), nullable=True)
    disbursement_id: Mapped[str] = mapped_column(String, index=True)
    bank_reference_number: Mapped[str] = mapped_column(String, nullable=True)
