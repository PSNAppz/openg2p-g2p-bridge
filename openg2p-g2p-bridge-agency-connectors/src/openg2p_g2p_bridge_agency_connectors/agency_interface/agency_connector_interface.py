from openg2p_fastapi_common.service import BaseService


class AgencyConnectorInterface(BaseService):
    def allocate_agency(
        self, agencies: list[str]
    ):
        """Allocate and return a list of agencies."""
        raise NotImplementedError()
