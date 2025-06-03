from unittest.mock import MagicMock, patch

import pytest
from openg2p_g2p_bridge_bank_connectors.bank_interface import CheckFundsResponse
from openg2p_g2p_bridge_celery_workers.tasks.check_funds_with_bank_task import (
    check_funds_with_bank_worker,
)
from openg2p_g2p_bridge_models.models import (
    BenefitProgramConfiguration,
    DisbursementEnvelope,
    DisbursementEnvelopeBatchStatus,
    FundsAvailableWithBankEnum,
)


class MockSession:
    def __init__(self):
        self.committed = False
        self.disbursement_envelope = DisbursementEnvelope(
            disbursement_envelope_id="test_envelope_id",
            benefit_program_mnemonic="test_program",
            total_disbursement_quantity=1000,
        )
        self.disbursement_envelope_batch_status = DisbursementEnvelopeBatchStatus(
            disbursement_envelope_id="test_envelope_id",
            funds_available_with_bank=FundsAvailableWithBankEnum.PENDING_CHECK.value,
            funds_available_attempts=0,
        )
        self.benefit_program_configuration = BenefitProgramConfiguration(
            benefit_program_mnemonic="test_program",
            sponsor_bank_code="EXAMPLE",
            sponsor_bank_account_number="test_account_number",
            sponsor_bank_account_currency="INR",
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

    def first(self):
        if self.query_args[0] is DisbursementEnvelope:
            return self.disbursement_envelope

        elif self.query_args[0] is DisbursementEnvelopeBatchStatus:
            return self.disbursement_envelope_batch_status

        elif self.query_args[0] is BenefitProgramConfiguration:
            return self.benefit_program_configuration
        return None

    def commit(self):
        self.committed = True

    def close(self):
        pass


@pytest.fixture
def mock_session_maker():
    mock_session = MockSession()

    with patch(
        "openg2p_g2p_bridge_celery_workers.tasks.check_funds_with_bank_task.sessionmaker",
        return_value=lambda: mock_session,
    ):
        yield mock_session


@pytest.fixture
def mock_bank_connector_factory():
    mock_bank_connector = MagicMock()
    mock_bank_factory = MagicMock()
    mock_bank_factory.get_bank_connector.return_value = mock_bank_connector

    with patch(
        "openg2p_g2p_bridge_celery_workers.tasks.check_funds_with_bank_task.BankConnectorFactory.get_component",
        return_value=mock_bank_factory,
    ):
        yield mock_bank_connector


def test_check_funds_with_bank_success(mock_session_maker, mock_bank_connector_factory):
    mock_bank_connector_factory.check_funds.return_value = CheckFundsResponse(
        status=FundsAvailableWithBankEnum.FUNDS_AVAILABLE, error_code=""
    )

    check_funds_with_bank_worker("test_envelope_id")

    assert (
        mock_session_maker.disbursement_envelope_batch_status.funds_available_with_bank
        == FundsAvailableWithBankEnum.FUNDS_AVAILABLE.value
    )
    assert mock_session_maker.committed


def test_check_funds_with_bank_failure(mock_session_maker, mock_bank_connector_factory):
    mock_bank_connector_factory.check_funds.return_value = CheckFundsResponse(
        status=FundsAvailableWithBankEnum.FUNDS_NOT_AVAILABLE, error_code=""
    )

    check_funds_with_bank_worker("test_envelope_id")

    assert (
        mock_session_maker.disbursement_envelope_batch_status.funds_available_with_bank
        == FundsAvailableWithBankEnum.FUNDS_NOT_AVAILABLE.value
    )
    assert mock_session_maker.committed


def test_check_funds_with_bank_exception(
    mock_session_maker, mock_bank_connector_factory
):
    mock_bank_connector_factory.check_funds.side_effect = Exception("TEST_EXCEPTION")

    check_funds_with_bank_worker("test_envelope_id")

    assert (
        mock_session_maker.disbursement_envelope_batch_status.funds_available_with_bank
        == FundsAvailableWithBankEnum.PENDING_CHECK.value
    )
    assert (
        mock_session_maker.disbursement_envelope_batch_status.funds_available_latest_error_code
        == "TEST_EXCEPTION"
    )
    assert mock_session_maker.committed


def test_check_funds_with_bank_envelope_not_found(
    mock_session_maker, mock_bank_connector_factory
):
    mock_session_maker.disbursement_envelope = None

    check_funds_with_bank_worker("test_envelope_id")

    assert not mock_session_maker.committed


def test_check_funds_with_bank_envelope_batch_status_not_found(
    mock_session_maker, mock_bank_connector_factory
):
    mock_session_maker.disbursement_envelope_batch_status = None

    check_funds_with_bank_worker("test_envelope_id")

    assert not mock_session_maker.committed
