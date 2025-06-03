# ruff: noqa: E402

from openg2p_fastapi_common.app import Initializer as BaseInitializer

from .config import Settings
from .warehouse_connectors import ExampleWarehouseConnector, WarehouseConnectorFactory

_config = Settings.get_config()


class Initializer(BaseInitializer):
    def initialize(self, **kwargs):
        WarehouseConnectorFactory()
        ExampleWarehouseConnector()
