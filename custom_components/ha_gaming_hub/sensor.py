import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODULE_FREE_GAMES, MODULE_PRICE_TRACKER

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
            FreeGamesCountSensor(coordinator, entry.entry_id),
            FreeGamesValueSensor(coordinator, entry.entry_id),
        ])

    if MODULE_PRICE_TRACKER in coordinators:
        coordinator = coordinators[MODULE_PRICE_TRACKER]

        for game in coordinator.watchlist:
            entities.extend(_price_tracker_sensors(coordinator, entry.entry_id, game))

        def on_game_added(game_data: dict) -> None:
            async_add_entities(
                _price_tracker_sensors(coordinator, entry.entry_id, game_data)
            )

        def on_game_removed(slug: str) -> None:
            ent_reg = er.async_get(hass)
            for sensor_type in ["best_price", "best_store", "discount_pct"]:
                uid = f"gaming_hub_{slug}_{sensor_type}"
                entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, uid)
                if entity_id:
                    ent_reg.async_remove(entity_id)

        coordinator.register_sensor_callbacks(on_game_added, on_game_removed)

    async_add_entities(entities)


def _device_info(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Gaming Hub",
        manufacturer="HA Gaming Hub",
    )


def _price_tracker_sensors(coordinator, entry_id: str, game: dict) -> list:
    slug = game["slug"]
    title = game["title"]
    return [
        GameBestPriceSensor(coordinator, entry_id, slug, title),
        GameBestStoreSensor(coordinator, entry_id, slug, title),
        GameDiscountSensor(coordinator, entry_id, slug, title),
    ]


# ---------------------------------------------------------------------------
# Free Games sensors
# ---------------------------------------------------------------------------

class FreeGamesCountSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Free Games Count"
    _attr_unique_id = "gaming_hub_free_games_count"
    _attr_icon = "mdi:gamepad-variant"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry_id)

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
        media_entries = []
        nintendo_entries = []
        for g in games:
            end_dt = g.get("end_date")
            worth = g.get("worth")
            cover = g.get("cover", "")
            store = g.get("store", g.get("platform", ""))
            media_entries.append({
                "title": g.get("title", ""),
                "rating": g.get("platform", ""),
                "price": "FREE" + (f" (${worth:.2f} value)" if worth else ""),
                "release": f"Expires {end_dt.strftime('%-d %b %Y')}" if end_dt else "",
                "genres": g.get("type", ""),
                "airdate": end_dt.strftime("%Y-%m-%d") if end_dt else "unknown",
                "box_art_url": cover,
                "fanart": cover,
                "poster": g.get("poster", cover),
                "deep_link": g.get("url", ""),
            })
            nintendo_entries.append({
                "title": g.get("title", ""),
                "box_art_url": cover,
                "backgroundart": cover,
                "sale_price": f"Free · {store}" if store else "Free",
                "normal_price": f"${worth:.2f}" if worth else "",
                "percent_off": 100,
            })
        return {
            "data": [header] + media_entries,
            "on_sale": nintendo_entries,
        }


class FreeGamesValueSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Free Games Value"
    _attr_unique_id = "gaming_hub_free_games_value"
    _attr_icon = "mdi:cash"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry_id)

    @property
    def native_value(self) -> float:
        return self.coordinator.data.get("total_value", 0.0)


# ---------------------------------------------------------------------------
# Price Tracker sensors
# ---------------------------------------------------------------------------

class _GameBaseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str, slug: str, title: str) -> None:
        super().__init__(coordinator)
        self._slug = slug
        self._attr_device_info = _device_info(entry_id)

    def _game_data(self) -> dict:
        return self.coordinator.data.get(self._slug, {})


class GameBestPriceSensor(_GameBaseSensor):
    _attr_icon = "mdi:tag"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "USD"

    def __init__(self, coordinator, entry_id: str, slug: str, title: str) -> None:
        super().__init__(coordinator, entry_id, slug, title)
        self._attr_name = f"{title} Best Price"
        self._attr_unique_id = f"gaming_hub_{slug}_best_price"

    @property
    def native_value(self) -> float | None:
        return self._game_data().get("best_price")

    @property
    def extra_state_attributes(self) -> dict:
        d = self._game_data()
        return {
            "cheapest_ever_price": d.get("cheapest_ever_price"),
            "cheapest_ever_date": d.get("cheapest_ever_date"),
        }


class GameBestStoreSensor(_GameBaseSensor):
    _attr_icon = "mdi:store"

    def __init__(self, coordinator, entry_id: str, slug: str, title: str) -> None:
        super().__init__(coordinator, entry_id, slug, title)
        self._attr_name = f"{title} Best Store"
        self._attr_unique_id = f"gaming_hub_{slug}_best_store"

    @property
    def native_value(self) -> str | None:
        return self._game_data().get("best_store")


class GameDiscountSensor(_GameBaseSensor):
    _attr_icon = "mdi:percent"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, entry_id: str, slug: str, title: str) -> None:
        super().__init__(coordinator, entry_id, slug, title)
        self._attr_name = f"{title} Discount"
        self._attr_unique_id = f"gaming_hub_{slug}_discount_pct"

    @property
    def native_value(self) -> float:
        return self._game_data().get("discount_pct", 0.0)
