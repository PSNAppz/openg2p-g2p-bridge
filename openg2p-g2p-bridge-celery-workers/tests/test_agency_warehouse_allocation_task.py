import pytest
from unittest.mock import MagicMock, patch

from openg2p_g2p_bridge_celery_workers.tasks.agency_warehouse_allocation_task import (
    agency_allocation_worker,
    warehouse_allocation_worker,
)
from openg2p_g2p_bridge_models.models import (
    AgencyAllocationBatchStatus,
    AgencyAllocationDetails,
    WarehouseAllocationBatchStatus,
    WarehouseAllocationDetails,
    ProcessStatus,
)


class MockSession:
    def __init__(self):
        self.committed = False
        self.updates = []
        self.agency_details = [
            AgencyAllocationDetails(
                agency_allocation_batch_id="batch_id",
                agency_code="AG001",
            )
        ]
        self.warehouse_details = [
            WarehouseAllocationDetails(
                warehouse_allocation_batch_id="batch_id",
                warehouse_code="WH001",
            )
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def execute(self, *args, **kwargs):
        if args and "warehouse_allocation_details" in str(args[0]):
            self._warehouses = True
        return self

    def scalars(self):
        return self

    def all(self):
        if hasattr(self, "_warehouses"):
            return [d.warehouse_code for d in self.warehouse_details]
        return [d.agency_code for d in self.agency_details]

    def query(self, *args):
        self.query_args = args
        return self

    def filter(self, *args):
        self.filter_args = args
        for arg in args:
            if "warehouse_allocation" in str(arg):
                self._warehouses = True
        return self

    def update(self, data):
        self.updates.append(data)
        return True

    def commit(self):
        self.committed = True


@pytest.fixture
def mock_session_maker():
    mock_session = MockSession()
    with patch(
        "openg2p_g2p_bridge_celery_workers.tasks.agency_warehouse_allocation_task.sessionmaker",
        return_value=lambda: mock_session,
    ):
        yield mock_session


@pytest.fixture
def mock_agency_connector():
    connector = MagicMock()
    factory = MagicMock()
    factory.get_agency_connector.return_value = connector
    with patch(
        "openg2p_g2p_bridge_celery_workers.tasks.agency_warehouse_allocation_task.AgencyConnectorFactory.get_component",
        return_value=factory,
    ):
        yield connector


@pytest.fixture
def mock_warehouse_connector():
    connector = MagicMock()
    factory = MagicMock()
    factory.get_warehouse_connector.return_value = connector
    with patch(
        "openg2p_g2p_bridge_celery_workers.tasks.agency_warehouse_allocation_task.WarehouseConnectorFactory.get_component",
        return_value=factory,
    ):
        yield connector


def test_agency_allocation_worker_success(mock_session_maker, mock_agency_connector):
    agency_allocation_worker("batch_id")
    assert mock_session_maker.updates[0][AgencyAllocationBatchStatus.allocation_status] == ProcessStatus.PROCESSED
    assert mock_session_maker.committed
    mock_agency_connector.allocate_agency.assert_called_once_with(["AG001"])


def test_agency_allocation_worker_failure(mock_session_maker, mock_agency_connector):
    mock_agency_connector.allocate_agency.side_effect = Exception("FAIL")
    agency_allocation_worker("batch_id")
    assert mock_session_maker.updates[0][AgencyAllocationBatchStatus.allocation_status] == ProcessStatus.PENDING
    assert mock_session_maker.updates[0][AgencyAllocationBatchStatus.latest_error_code] == "FAIL"
    assert mock_session_maker.committed


def test_warehouse_allocation_worker_success(mock_session_maker, mock_warehouse_connector):
    warehouse_allocation_worker("batch_id")
    assert mock_session_maker.updates[0][WarehouseAllocationBatchStatus.allocation_status] == ProcessStatus.PROCESSED
    assert mock_session_maker.committed
    mock_warehouse_connector.allocate_warehouse.assert_called_once_with(["WH001"])


def test_warehouse_allocation_worker_failure(mock_session_maker, mock_warehouse_connector):
    mock_warehouse_connector.allocate_warehouse.side_effect = Exception("FAIL")
    warehouse_allocation_worker("batch_id")
    assert mock_session_maker.updates[0][WarehouseAllocationBatchStatus.allocation_status] == ProcessStatus.PENDING
    assert mock_session_maker.updates[0][WarehouseAllocationBatchStatus.latest_error_code] == "FAIL"
    assert mock_session_maker.committed
