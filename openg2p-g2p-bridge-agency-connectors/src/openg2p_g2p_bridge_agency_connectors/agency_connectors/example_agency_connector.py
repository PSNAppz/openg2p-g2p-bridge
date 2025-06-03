import logging

from ..agency_interface.agency_connector_interface import AgencyConnectorInterface
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ExampleAgencyConnector(AgencyConnectorInterface):
    def allocate_agency(self, agencies: list[str]):
        _logger.info("Allocating agency for %s", agencies)
        # In a real connector this would allocate the agency using an external system
        return {"agency_code": agencies[0], "name": "Example Agency"}
