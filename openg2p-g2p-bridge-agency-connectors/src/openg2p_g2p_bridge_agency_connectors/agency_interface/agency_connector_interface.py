from openg2p_fastapi_common.service import BaseService


class AgencyConnectorInterface(BaseService):
    def get_agency_resolution_details(
        self, agencies: list[str], benefit_code: str
    ):
        """Return resolution details for the matching agency."""
        raise NotImplementedError()
