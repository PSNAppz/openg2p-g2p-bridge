from openg2p_g2p_bridge_warehouse_connectors.warehouse_connectors import (
    WarehouseConnectorFactory,
    ExampleWarehouseConnector,
)


def test_factory_returns_example_connector():
    connector = WarehouseConnectorFactory().get_warehouse_connector("EXAMPLE")
    assert isinstance(connector, ExampleWarehouseConnector)


def test_example_warehouse_connector():
    connector = ExampleWarehouseConnector()
    details = connector.get_warehouse_resolution_details(["EXAMPLE"], "BEN001")
    assert details == {"warehouse_code": "EXAMPLE", "name": "Example Warehouse"}
