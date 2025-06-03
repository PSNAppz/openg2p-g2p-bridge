from openg2p_g2p_bridge_agency_connectors.agency_connectors import (
    AgencyConnectorFactory,
    ExampleAgencyConnector,
)


def test_factory_returns_example_connector():
    connector = AgencyConnectorFactory().get_agency_connector("EXAMPLE")
    assert isinstance(connector, ExampleAgencyConnector)


def test_example_agency_connector():
    connector = ExampleAgencyConnector()
    details = connector.allocate_agency(["EXAMPLE"])
    assert details == {"agency_code": "EXAMPLE", "name": "Example Agency"}
