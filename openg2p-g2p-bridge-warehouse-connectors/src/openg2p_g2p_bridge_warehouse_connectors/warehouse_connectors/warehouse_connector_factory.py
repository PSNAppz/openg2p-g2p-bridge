from openg2p_fastapi_common.service import BaseService

from ..warehouse_interface.warehouse_connector_interface import WarehouseConnectorInterface
from .example_warehouse_connector import ExampleWarehouseConnector


class WarehouseConnectorFactory(BaseService):
    def get_warehouse_connector(self, warehouse_code: str) -> WarehouseConnectorInterface:
        if warehouse_code == "EXAMPLE":
            return ExampleWarehouseConnector()
        raise NotImplementedError(f"Warehouse {warehouse_code} is not supported")
