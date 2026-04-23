import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

# Entities to be added in future milestones:
# - Free Games: sensor per game title (state = claim URL, attrs = end date, source)
# - Price Tracker: sensor per watchlist entry (state = current price, attrs = deals, store)
# - Presence: sensor per Steam account (state = online/offline, attrs = current game)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    pass
