import logging
from unittest.mock import MagicMock, patch

import pytest
from openg2p_g2p_bridge_bank_connectors.bank_interface import (
    PaymentResponse,
    PaymentStatus,
)
from openg2p_g2p_bridge_celery_workers.tasks.disburse_funds_from_bank import (
    disburse_funds_from_bank_worker,
)
from openg2p_g2p_bridge_models.models import (
    BankDisbursementBatchStatus,
    BenefitProgramConfiguration,
    Disbursement,
    DisbursementBatchControl,
    DisbursementEnvelope,
    DisbursementEnvelopeBatchStatus,
    MapperResolutionDetails,
    ProcessStatus,
)


class MockSession:
    def __init__(self):
        self.committed = False
        self.rollbacked = False
        self.disbursement_envelope = DisbursementEnvelope(
            disbursement_envelope_id="test_envelope_id",
            benefit_program_mnemonic="test_program",
            cycle_code_mnemonic="test_cycle",
            total_disbursement_quantity=1000,
        )
        self.disbursement_envelope_batch_status = DisbursementEnvelopeBatchStatus(
            disbursement_envelope_id="test_envelope_id",
            funds_blocked_reference_number="test_block_ref",
            number_of_disbursements_shipped=0,
        )
        self.bank_disbursement_batch_status = BankDisbursementBatchStatus(
            bank_disbursement_batch_id="test_batch_id",
            disbursement_envelope_id="test_envelope_id",
            disbursement_status=ProcessStatus.PENDING.value,
            disbursement_attempts=0,
        )
        self.benefit_program_configuration = BenefitProgramConfiguration(
            benefit_program_mnemonic="test_program",
            sponsor_bank_code="EXAMPLE",
            sponsor_bank_account_number="test_account_number",
            sponsor_bank_account_currency="INR",
        )
        self.disbursement = Disbursement(
            disbursement_id="test_disbursement_id",
            beneficiary_id="test_beneficiary",
            beneficiary_name="Test Beneficiary",
            disbursement_quantity=100,
            narrative="Test payment",
        )
        self.disbursement_batch_control = DisbursementBatchControl(
            disbursement_id="test_disbursement_id",
            bank_disbursement_batch_id="test_batch_id",
            mapper_status=ProcessStatus.PROCESSED.value,
        )
        self.mapper_resolution_details = MapperResolutionDetails(
            disbursement_id="test_disbursement_id",
            bank_account_number="test_bank_account",
            bank_code="test_bank",
            branch_code="test_branch",
            mobile_number="1234567890",
            email_address="test@example.com",
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def query(self, *args):
        self.query_args = args
        return self

    def filter(self, *args):
        self.filter_args = args
        return self

    def one(self):
        return self.first()

    def first(self):
        if self.query_args[0] is BankDisbursementBatchStatus:
            return self.bank_disbursement_batch_status
        elif self.query_args[0] is DisbursementEnvelope:
            return self.disbursement_envelope
        elif self.query_args[0] is DisbursementEnvelopeBatchStatus:
            return self.disbursement_envelope_batch_status
        elif self.query_args[0] is BenefitProgramConfiguration:
            return self.benefit_program_configuration
        elif self.query_args[0] is MapperResolutionDetails:
            return self.mapper_resolution_details
        return None

    def all(self):
        if self.query_args[0] is DisbursementBatchControl:
            return [self.disbursement_batch_control]
        elif self.query_args[0] is Disbursement:
            return [self.disbursement]
        return []

    def with_for_update(self, nowait=False):
        return self

    def populate_existing(self):
        return self

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


@pytest.fixture
def mock_session_maker():
    mock_session = MockSession()

    with patch(
        "openg2p_g2p_bridge_celery_workers.tasks.disburse_funds_from_bank.sessionmaker",
        return_value=lambda: mock_session,
    ):
        yield mock_session


@pytest.fixture
def mock_bank_connector_factory():
    mock_bank_connector = MagicMock()
    mock_bank_factory = MagicMock()
    mock_bank_factory.get_bank_connector.return_value = mock_bank_connector

    with patch(
        "openg2p_g2p_bridge_celery_workers.tasks.disburse_funds_from_bank.BankConnectorFactory.get_component",
        return_value=mock_bank_factory,
    ):
        yield mock_bank_connector


def test_disburse_funds_success(mock_session_maker, mock_bank_connector_factory):
    mock_bank_connector_factory.initiate_payment.return_value = PaymentResponse(
        status=PaymentStatus.SUCCESS,
        error_code="",
    )

    disburse_funds_from_bank_worker("test_batch_id")

    assert (
        mock_session_maker.bank_disbursement_batch_status.disbursement_status
        == ProcessStatus.PROCESSED.value
    )
    assert mock_session_maker.bank_disbursement_batch_status.latest_error_code is None
    assert (
        mock_session_maker.disbursement_envelope_batch_status.number_of_disbursements_shipped
        == 1
    )
    assert mock_session_maker.committed


def test_disburse_funds_failure(mock_session_maker, mock_bank_connector_factory):
    mock_bank_connector_factory.initiate_payment.return_value = PaymentResponse(
        status=PaymentStatus.ERROR,
        error_code="TEST_ERROR",
    )

    disburse_funds_from_bank_worker("test_batch_id")

    assert (
        mock_session_maker.bank_disbursement_batch_status.disbursement_status
        == ProcessStatus.PENDING.value
    )
    assert (
        mock_session_maker.bank_disbursement_batch_status.latest_error_code
        == "TEST_ERROR"
    )
    assert mock_session_maker.committed


def test_disburse_funds_exception(
    mock_session_maker, mock_bank_connector_factory, caplog
):
    mock_bank_connector_factory.initiate_payment.side_effect = Exception(
        "TEST_EXCEPTION"
    )

    with caplog.at_level(logging.ERROR):
        disburse_funds_from_bank_worker("test_batch_id")

    assert "TEST_EXCEPTION" in caplog.text
    assert (
        mock_session_maker.bank_disbursement_batch_status.disbursement_status
        == ProcessStatus.PENDING.value
    )
    assert (
        mock_session_maker.bank_disbursement_batch_status.latest_error_code
        == "TEST_EXCEPTION"
    )
    assert mock_session_maker.bank_disbursement_batch_status.disbursement_attempts == 5
    assert mock_session_maker.committed


def test_disburse_funds_batch_not_found(mock_session_maker):
    mock_session_maker.bank_disbursement_batch_status = None

    disburse_funds_from_bank_worker("test_batch_id")

    assert not mock_session_maker.committed


def test_disburse_funds_envelope_not_found(mock_session_maker):
    mock_session_maker.disbursement_envelope = None

    disburse_funds_from_bank_worker("test_batch_id")

    assert not mock_session_maker.committed


def test_disburse_funds_envelope_batch_status_not_found(mock_session_maker):
    mock_session_maker.disbursement_envelope_batch_status = None

    disburse_funds_from_bank_worker("test_batch_id")

    assert not mock_session_maker.committed
