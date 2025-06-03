import logging

from ..warehouse_interface.warehouse_connector_interface import WarehouseConnectorInterface
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ExampleWarehouseConnector(WarehouseConnectorInterface):
    def get_warehouse_resolution_details(
        self, warehouses: list[str], benefit_code: str
    ):
        _logger.info(
            "Retrieving warehouse resolution details for %s with benefit %s",
            warehouses,
            benefit_code,
        )
        # In a real connector this would look up the warehouse info from an external system
        return {"warehouse_code": warehouses[0], "name": "Example Warehouse"}
