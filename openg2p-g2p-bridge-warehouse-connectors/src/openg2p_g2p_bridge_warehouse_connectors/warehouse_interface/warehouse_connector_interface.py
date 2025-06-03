from openg2p_fastapi_common.service import BaseService


class WarehouseConnectorInterface(BaseService):
    def get_warehouse_resolution_details(
        self, warehouses: list[str], benefit_code: str
    ):
        """Return warehouse resolution details for the given code."""
        raise NotImplementedError()
