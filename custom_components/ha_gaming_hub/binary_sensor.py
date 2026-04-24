import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODULE_PRICE_TRACKER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinators = entry_data["coordinators"]

    entities = []

    if MODULE_PRICE_TRACKER in coordinators:
        coordinator = coordinators[MODULE_PRICE_TRACKER]

        for game in coordinator.watchlist:
            entities.extend(_price_tracker_binary_sensors(coordinator, entry.entry_id, game))

        def on_game_added(game_data: dict) -> None:
            async_add_entities(
                _price_tracker_binary_sensors(coordinator, entry.entry_id, game_data)
            )

        def on_game_removed(slug: str) -> None:
            ent_reg = er.async_get(hass)
            for bs_type in ["on_sale", "historical_low"]:
                uid = f"gaming_hub_{slug}_{bs_type}"
                entity_id = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, uid)
                if entity_id:
                    ent_reg.async_remove(entity_id)

        coordinator.register_binary_sensor_callbacks(on_game_added, on_game_removed)

    async_add_entities(entities)


def _device_info(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Gaming Hub",
        manufacturer="HA Gaming Hub",
    )


def _price_tracker_binary_sensors(coordinator, entry_id: str, game: dict) -> list:
    slug = game["slug"]
    title = game["title"]
    return [
        GameOnSaleBinarySensor(coordinator, entry_id, slug, title),
        GameHistoricalLowBinarySensor(coordinator, entry_id, slug, title),
    ]


class _GameBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str, slug: str, title: str) -> None:
        super().__init__(coordinator)
        self._slug = slug
        self._attr_device_info = _device_info(entry_id)

    def _game_data(self) -> dict:
        return self.coordinator.data.get(self._slug, {})


class GameOnSaleBinarySensor(_GameBaseBinarySensor):
    _attr_icon = "mdi:sale"

    def __init__(self, coordinator, entry_id: str, slug: str, title: str) -> None:
        super().__init__(coordinator, entry_id, slug, title)
        self._attr_name = f"{title} On Sale"
        self._attr_unique_id = f"gaming_hub_{slug}_on_sale"

    @property
    def is_on(self) -> bool:
        return self._game_data().get("on_sale", False)


class GameHistoricalLowBinarySensor(_GameBaseBinarySensor):
    _attr_icon = "mdi:trophy"

    def __init__(self, coordinator, entry_id: str, slug: str, title: str) -> None:
        super().__init__(coordinator, entry_id, slug, title)
        self._attr_name = f"{title} Historical Low"
        self._attr_unique_id = f"gaming_hub_{slug}_historical_low"

    @property
    def is_on(self) -> bool:
        return self._game_data().get("historical_low", False)
