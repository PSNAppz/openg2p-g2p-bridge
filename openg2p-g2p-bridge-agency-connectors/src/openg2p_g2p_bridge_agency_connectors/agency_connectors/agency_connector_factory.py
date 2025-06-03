from openg2p_fastapi_common.service import BaseService

from ..agency_interface.agency_connector_interface import AgencyConnectorInterface
from .example_agency_connector import ExampleAgencyConnector


class AgencyConnectorFactory(BaseService):
    def get_agency_connector(self, agency_code: str) -> AgencyConnectorInterface:
        if agency_code == "EXAMPLE":
            return ExampleAgencyConnector()
        raise NotImplementedError(f"Agency {agency_code} is not supported")
