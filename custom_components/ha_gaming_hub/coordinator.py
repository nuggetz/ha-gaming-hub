import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class GamingHubCoordinator(DataUpdateCoordinator):
    """Base coordinator for HA Gaming Hub modules."""

    def __init__(self, hass: HomeAssistant, name: str, update_interval: int, session):
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=update_interval),
        )
        self.session = session

    async def _async_update_data(self):
        raise NotImplementedError
