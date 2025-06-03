from openg2p_fastapi_common.service import BaseService


class WarehouseConnectorInterface(BaseService):
    def allocate_warehouse(
        self, warehouses: list[str]
    ):
        """Allocate and return a list of warehouses."""
        raise NotImplementedError()
