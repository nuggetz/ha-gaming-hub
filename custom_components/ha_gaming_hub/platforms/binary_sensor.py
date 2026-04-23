import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

# Entities to be added in future milestones:
# - Free Games: binary_sensor "new free games available" (on when there are unclaimed promotions)
# - Price Tracker: binary_sensor per watchlist entry (on when price drops below threshold)
# - Presence: binary_sensor per Xbox account (on = online)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    pass
