import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from ..coordinator import GamingHubCoordinator
from ..const import DEFAULT_SCAN_INTERVAL_PRICE_TRACKER

_LOGGER = logging.getLogger(__name__)


class PriceTrackerCoordinator(GamingHubCoordinator):
    """Coordinator for the Price Tracker module."""

    def __init__(self, hass: HomeAssistant, session, config: dict):
        super().__init__(
            hass,
            name="HA Gaming Hub - Price Tracker",
            update_interval=DEFAULT_SCAN_INTERVAL_PRICE_TRACKER,
            session=session,
        )
        self.config = config

    async def _async_update_data(self):
        # TODO: fetch game prices (CheapShark, ITAD)
        return {}
