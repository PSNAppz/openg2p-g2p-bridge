import logging

from ..agency_interface.agency_connector_interface import AgencyConnectorInterface
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ExampleAgencyConnector(AgencyConnectorInterface):
    def get_agency_resolution_details(
        self, agencies: list[str], benefit_code: str
    ):
        _logger.info(
            "Retrieving agency resolution details for %s with benefit %s",
            agencies,
            benefit_code,
        )
        # In a real connector this would look up the agency info from an external system
        return {"agency_code": agencies[0], "name": "Example Agency"}
