import datetime
from typing import List, Optional

from openg2p_g2pconnect_common_lib.schemas import Request, SyncResponse
from pydantic import BaseModel

from ..models import DisbursementFrequency


class DisbursementEnvelopePayload(BaseModel):
    id: Optional[str] = None
    disbursement_envelope_id: Optional[str] = None
    benefit_code: Optional[str] = None
    benefit_program_mnemonic: Optional[str] = None
    disbursement_frequency: Optional[DisbursementFrequency] = None
    cycle_code_mnemonic: Optional[str] = None
    number_of_beneficiaries: Optional[int] = None
    number_of_disbursements: Optional[int] = None
    total_disbursement_quantity: Optional[float] = None
    measurement_unit: Optional[str] = None
    disbursement_currency_code: Optional[str] = None
    disbursement_schedule_date: Optional[datetime.date] = None


class DisbursementEnvelopeRequest(Request):
    message: DisbursementEnvelopePayload


class DisbursementEnvelopeResponse(SyncResponse):
    message: Optional[DisbursementEnvelopePayload] = None


class DisbursementEnvelopesRequest(Request):
    """Request schema for creating multiple envelopes."""

    message: List[DisbursementEnvelopePayload]


class DisbursementEnvelopesResponse(SyncResponse):
    """Response schema containing created envelopes."""

    message: Optional[List[DisbursementEnvelopePayload]] = None
