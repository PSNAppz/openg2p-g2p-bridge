import logging

from ..config import Settings
from ..warehouse_interface.warehouse_connector_interface import (
    WarehouseConnectorInterface,
)

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ExampleWarehouseConnector(WarehouseConnectorInterface):
    def allocate_warehouse(self, warehouses: list[str]):
        _logger.info("Allocating warehouse for %s", warehouses)
        # In a real connector this would allocate the warehouse using an external system
        return {"warehouse_code": warehouses[0], "name": "Example Warehouse"}
