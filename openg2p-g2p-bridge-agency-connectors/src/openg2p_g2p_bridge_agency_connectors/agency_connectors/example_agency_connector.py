import logging

from ..agency_interface.agency_connector_interface import AgencyConnectorInterface
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ExampleAgencyConnector(AgencyConnectorInterface):
    def allocate_agency(
        self, agencies: list[str]
    ):
        """Allocate and return a list of agencies."""
        _logger.info(
            "Retrieving agency resolution details for %s",
            agencies,
        )
        # In a real connector this would look up the agency info from an external system
        return {"agency_code": agencies[0], "name": "Example Agency"}
