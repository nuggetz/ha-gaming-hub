import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
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
        header = {
            "title_default": "$title",
            "line1_default": "$rating",
            "line2_default": "$price",
            "line3_default": "$release",
            "line4_default": "$genres",
            "icon": "mdi:gamepad-variant",
        }
        entries = []
        for g in games:
            end_dt = g.get("end_date")
            worth = g.get("worth")
            entries.append({
                "title": g.get("title", ""),
                "rating": g.get("platform", ""),
                "price": "FREE" + (f" (${worth:.2f} value)" if worth else ""),
                "release": f"Expires {end_dt.strftime('%-d %b %Y')}" if end_dt else "",
                "genres": g.get("type", ""),
                "airdate": end_dt.strftime("%Y-%m-%d") if end_dt else "unknown",
                "box_art_url": g.get("cover", ""),
                "fanart": g.get("cover", ""),
                "poster": g.get("poster", g.get("cover", "")),
                "deep_link": g.get("url", ""),
            })
        return {"data": [header] + entries}


class FreeGamesValueSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Free Games Total Value"
    _attr_unique_id = "gaming_hub_free_games_value"
    _attr_icon = "mdi:cash"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        return self.hass.config.currency

    @property
    def native_value(self) -> float:
        return self.coordinator.data.get("total_value", 0.0)
