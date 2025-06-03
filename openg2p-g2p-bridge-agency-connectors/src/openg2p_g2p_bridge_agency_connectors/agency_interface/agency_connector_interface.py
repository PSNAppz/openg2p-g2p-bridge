from openg2p_fastapi_common.service import BaseService


class AgencyConnectorInterface(BaseService):
    def allocate_agency(self, agencies: list[str]):
        """Allocate agencies using an external system."""
        raise NotImplementedError()
