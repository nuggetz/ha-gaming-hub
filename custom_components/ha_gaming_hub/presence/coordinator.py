import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from ..coordinator import GamingHubCoordinator
from ..const import DEFAULT_SCAN_INTERVAL_PRESENCE

_LOGGER = logging.getLogger(__name__)


class PresenceCoordinator(GamingHubCoordinator):
    """Coordinator for the Presence module."""

    def __init__(self, hass: HomeAssistant, session, config: dict):
        super().__init__(
            hass,
            name="HA Gaming Hub - Presence",
            update_interval=DEFAULT_SCAN_INTERVAL_PRESENCE,
            session=session,
        )
        self.config = config

    async def _async_update_data(self):
        # TODO: fetch Steam and Xbox online presence
        return {}
