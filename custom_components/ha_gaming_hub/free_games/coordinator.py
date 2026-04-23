import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from ..coordinator import GamingHubCoordinator
from ..const import DEFAULT_SCAN_INTERVAL_FREE_GAMES

_LOGGER = logging.getLogger(__name__)


class FreeGamesCoordinator(GamingHubCoordinator):
    """Coordinator for the Free Games module."""

    def __init__(self, hass: HomeAssistant, session):
        super().__init__(
            hass,
            name="HA Gaming Hub - Free Games",
            update_interval=DEFAULT_SCAN_INTERVAL_FREE_GAMES,
            session=session,
        )

    async def _async_update_data(self):
        # TODO: fetch free game promotions (Epic, GamerPower)
        return {}
