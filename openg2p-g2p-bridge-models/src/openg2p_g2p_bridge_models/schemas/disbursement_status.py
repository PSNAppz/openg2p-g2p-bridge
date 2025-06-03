import datetime
from typing import List, Optional

from openg2p_g2pconnect_common_lib.schemas import Request, SyncResponse
from pydantic import BaseModel

from ..errors.codes import G2PBridgeErrorCodes
from ..models import FundsAvailableWithBankEnum, FundsBlockedWithBankEnum


class DisbursementStatusRequest(Request):
    message: List[str]


class DisbursementReconPayload(BaseModel):
    bank_disbursement_batch_id: str
    disbursement_id: str
    disbursement_envelope_id: Optional[str] = None
    beneficiary_name_from_bank: Optional[str] = None

    remittance_reference_number: Optional[str] = None
    remittance_statement_id: Optional[str] = None
    remittance_statement_number: Optional[str] = None
    remittance_statement_sequence: Optional[str] = None
    remittance_entry_sequence: Optional[str] = None
    remittance_entry_date: Optional[datetime.datetime] = None
    remittance_value_date: Optional[datetime.datetime] = None

    reversal_found: Optional[bool] = None
    reversal_statement_id: Optional[str] = None
    reversal_statement_number: Optional[str] = None
    reversal_statement_sequence: Optional[str] = None
    reversal_entry_sequence: Optional[str] = None
    reversal_entry_date: Optional[datetime.datetime] = None
    reversal_value_date: Optional[datetime.datetime] = None
    reversal_reason: Optional[str] = None


class DisbursementErrorReconPayload(BaseModel):
    statement_id: Optional[str] = None
    statement_number: Optional[str] = None
    statement_sequence: Optional[str] = None
    entry_sequence: Optional[str] = None
    entry_date: Optional[datetime.datetime] = None
    value_date: Optional[datetime.datetime] = None
    error_reason: Optional[G2PBridgeErrorCodes] = None
    disbursement_id: str
    bank_reference_number: Optional[str] = None


class DisbursementReconRecords(BaseModel):
    disbursement_recon_payloads: Optional[List[DisbursementReconPayload]] = None
    disbursement_error_recon_payloads: Optional[
        List[DisbursementErrorReconPayload]
    ] = None


class DisbursementStatusPayload(BaseModel):
    disbursement_id: str
    disbursement_recon_records: Optional[DisbursementReconRecords] = None


class DisbursementStatusResponse(SyncResponse):
    message: Optional[List[DisbursementStatusPayload]] = None


class DisbursementEnvelopeStatusRequest(Request):
    message: str


class DisbursementEnvelopeBatchStatusPayload(BaseModel):
    disbursement_envelope_id: str
    number_of_disbursements_received: int
    total_disbursement_quantity_received: int

    funds_available_with_bank: FundsAvailableWithBankEnum
    funds_available_latest_timestamp: Optional[datetime.datetime] = None
    funds_available_latest_error_code: Optional[str] = None
    funds_available_attempts: int

    funds_blocked_with_bank: FundsBlockedWithBankEnum
    funds_blocked_latest_timestamp: Optional[datetime.datetime] = None
    funds_blocked_latest_error_code: Optional[str] = None
    funds_blocked_attempts: int
    funds_blocked_reference_number: Optional[str] = None

    id_mapper_resolution_required: Optional[bool] = None
    number_of_disbursements_shipped: int
    number_of_disbursements_reconciled: int
    number_of_disbursements_reversed: int


class DisbursementEnvelopeStatusResponse(SyncResponse):
    message: Optional[DisbursementEnvelopeBatchStatusPayload] = None
