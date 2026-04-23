import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODULE_FREE_GAMES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinators = entry_data["coordinators"]

    entities = []

    if MODULE_FREE_GAMES in coordinators:
        coordinator = coordinators[MODULE_FREE_GAMES]
        entities.extend([
            FreeGamesCountSensor(coordinator),
            FreeGamesValueSensor(coordinator),
        ])

    async_add_entities(entities)


class FreeGamesCountSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Free Games Available"
    _attr_unique_id = "gaming_hub_free_games_count"
    _attr_icon = "mdi:gamepad-variant"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("count", 0)

    @property
    def extra_state_attributes(self) -> dict:
        games = self.coordinator.data.get("current", [])
        return {
            "games": [
                {
                    "title": g.get("title"),
                    "platform": g.get("platform"),
                    "type": g.get("type"),
                    "end_date": g["end_date"].isoformat() if g.get("end_date") else None,
                    "url": g.get("url"),
                    "worth": g.get("worth"),
                }
                for g in games
            ]
        }


class FreeGamesValueSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Free Games Total Value"
    _attr_unique_id = "gaming_hub_free_games_value"
    _attr_icon = "mdi:cash"
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float:
        return self.coordinator.data.get("total_value", 0.0)
