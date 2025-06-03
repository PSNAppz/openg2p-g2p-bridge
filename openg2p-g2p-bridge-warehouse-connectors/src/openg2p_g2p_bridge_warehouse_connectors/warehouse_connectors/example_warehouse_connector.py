import logging

from ..config import Settings
from ..warehouse_interface.warehouse_connector_interface import (
    WarehouseConnectorInterface,
)

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ExampleWarehouseConnector(WarehouseConnectorInterface):
    def allocate_warehouse(self, warehouses: list[str]):
        """Allocate and return a list of warehouses."""
        _logger.info(
            "Retrieving warehouse resolution details for %s",
            warehouses,
        )
        # In a real connector this would look up the warehouse info from an external system
        return {"warehouse_code": warehouses[0], "name": "Example Warehouse"}
