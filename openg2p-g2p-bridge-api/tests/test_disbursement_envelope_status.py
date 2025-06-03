from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from openg2p_g2p_bridge_api.controllers import DisbursementEnvelopeStatusController
from openg2p_g2p_bridge_models.errors.codes import G2PBridgeErrorCodes
from openg2p_g2p_bridge_models.errors.exceptions import DisbursementStatusException
from openg2p_g2p_bridge_models.schemas import (
    DisbursementEnvelopeBatchStatusPayload,
    DisbursementEnvelopeStatusRequest,
    DisbursementEnvelopeStatusResponse,
)
from openg2p_g2pconnect_common_lib.schemas import (
    RequestHeader,
    StatusEnum,
    SyncResponseHeader,
)


@pytest.mark.asyncio
@patch(
    "openg2p_g2p_bridge_api.services.DisbursementEnvelopeStatusService.get_component"
)
@patch("openg2p_g2p_bridge_api.services.RequestValidation.get_component")
async def test_get_disbursement_envelope_status_success(
    mock_request_validation, mock_service_get_component
):
    mock_request_validation.validate_signature.return_value = None
    mock_request_validation.validate_request.return_value = None

    # Setup mock service
    mock_service_instance = AsyncMock()
    mock_service_get_component.return_value = mock_service_instance

    # Mock service methods
    mock_service_instance.get_disbursement_envelope_batch_status = AsyncMock(
        return_value=DisbursementEnvelopeBatchStatusPayload(
            disbursement_envelope_id="env123",
            number_of_disbursements_received=100,
            total_disbursement_quantity_received=5000,
            funds_available_with_bank="FUNDS_AVAILABLE",
            funds_available_latest_timestamp=datetime.now(),
            funds_available_latest_error_code=None,
            funds_available_attempts=3,
            funds_blocked_with_bank="FUNDS_BLOCK_SUCCESS",
            funds_blocked_latest_timestamp=datetime.now(),
            funds_blocked_latest_error_code=None,
            funds_blocked_attempts=2,
            funds_blocked_reference_number="ref123",
            id_mapper_resolution_required=False,
            number_of_disbursements_shipped=100,
            number_of_disbursements_reconciled=95,
            number_of_disbursements_reversed=5,
        )
    )

    expected_response = DisbursementEnvelopeStatusResponse(
        header=SyncResponseHeader(
            message_id="",
            message_ts=datetime.now().isoformat(),
            action="",
            status=StatusEnum.succ,
            status_reason_message="",
        ),
        message=DisbursementEnvelopeBatchStatusPayload(
            disbursement_envelope_id="env123",
            number_of_disbursements_received=100,
            total_disbursement_quantity_received=5000,
            funds_available_with_bank="FUNDS_AVAILABLE",
            funds_available_latest_timestamp=datetime.now(),
            funds_available_latest_error_code=None,
            funds_available_attempts=3,
            funds_blocked_with_bank="FUNDS_BLOCK_SUCCESS",
            funds_blocked_latest_timestamp=datetime.now(),
            funds_blocked_latest_error_code=None,
            funds_blocked_attempts=2,
            funds_blocked_reference_number="ref123",
            id_mapper_resolution_required=False,
            number_of_disbursements_shipped=100,
            number_of_disbursements_reconciled=95,
            number_of_disbursements_reversed=5,
        ),
    )

    mock_service_instance.construct_disbursement_envelope_status_success_response = (
        AsyncMock(return_value=expected_response)
    )

    # Instantiate controller and make request
    controller = DisbursementEnvelopeStatusController()
    request_payload = DisbursementEnvelopeStatusRequest(
        header=RequestHeader(
            message_id="123",
            message_ts=datetime.now().isoformat(),
            action="",
            sender_id="",
            sender_uri="",
            receiver_id="",
            total_count=1,
            is_msg_encrypted=False,
        ),
        message="env123",
    )

    actual_response = await controller.get_disbursement_envelope_status(
        request_payload, is_signature_valid=True
    )
    assert actual_response == expected_response


@pytest.mark.asyncio
@patch(
    "openg2p_g2p_bridge_api.services.DisbursementEnvelopeStatusService.get_component"
)
@patch("openg2p_g2p_bridge_api.services.RequestValidation.get_component")
@pytest.mark.parametrize("error_code", list(G2PBridgeErrorCodes))
async def test_get_disbursement_envelope_status_failure(
    mock_request_validation, mock_service_get_component, error_code
):
    mock_request_validation.validate_signature.return_value = None
    mock_request_validation.validate_request.return_value = None

    # Setup mock service
    mock_service_instance = AsyncMock()
    mock_service_get_component.return_value = mock_service_instance

    # Mock service methods to raise an error
    mock_service_instance.get_disbursement_envelope_batch_status.side_effect = (
        DisbursementStatusException(code=error_code, message=f"{error_code} error.")
    )

    error_response = DisbursementEnvelopeStatusResponse(
        header=SyncResponseHeader(
            message_id="",
            message_ts=datetime.now().isoformat(),
            action="",
            status=StatusEnum.rjct,
            status_reason_message=error_code,
        ),
        message=None,
    )

    mock_service_instance.construct_disbursement_envelope_status_error_response = (
        AsyncMock(return_value=error_response)
    )

    # Instantiate controller and make request
    controller = DisbursementEnvelopeStatusController()
    request_payload = DisbursementEnvelopeStatusRequest(
        header=RequestHeader(
            message_id="123",
            message_ts=datetime.now().isoformat(),
            action="",
            sender_id="",
            sender_uri="",
            receiver_id="",
            total_count=1,
            is_msg_encrypted=False,
        ),
        message="env123",
    )

    actual_response = await controller.get_disbursement_envelope_status(
        request_payload, is_signature_valid=True
    )
    assert (
        actual_response == error_response
    ), f"The response did not match the expected error response for {error_code}."
