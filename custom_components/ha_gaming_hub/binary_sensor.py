import logging
from datetime import datetime, timedelta, timezone

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_EXPIRY_WARNING_HOURS,
    DEFAULT_EXPIRY_WARNING_HOURS,
    DOMAIN,
    MODULE_FREE_GAMES,
    MODULE_PRICE_TRACKER,
    MODULE_PRESENCE,
)

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
        expiry_hours = entry.options.get(CONF_EXPIRY_WARNING_HOURS, DEFAULT_EXPIRY_WARNING_HOURS)
        entities.append(
            FreeGameExpiringSoonBinarySensor(
                coordinators[MODULE_FREE_GAMES], entry.entry_id, expiry_hours
            )
        )

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

    if MODULE_PRESENCE in coordinators:
        coordinator = coordinators[MODULE_PRESENCE]
        entities.append(SomeoneIsGamingBinarySensor(coordinator, entry.entry_id))
        for account_key, acc in (coordinator.data or {}).get("accounts", {}).items():
            platform = acc.get("platform", "")
            name = acc.get("name") or acc.get("gamertag") or account_key
            entities.append(AccountOnlineBinarySensor(coordinator, entry.entry_id, account_key, name, platform))

    async_add_entities(entities)


def _device_info(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Gaming Hub",
        manufacturer="HA Gaming Hub",
    )


# ---------------------------------------------------------------------------
# Free Games binary sensors
# ---------------------------------------------------------------------------

class FreeGameExpiringSoonBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Free Game Expiring Soon"
    _attr_unique_id = "gaming_hub_free_game_expiring_soon"
    _attr_icon = "mdi:timer-alert"

    def __init__(self, coordinator, entry_id: str, warning_hours: int) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry_id)
        self._warning_hours = warning_hours

    def _soonest_expiring(self) -> dict | None:
        games = (self.coordinator.data or {}).get("current", [])
        now = datetime.now(tz=timezone.utc)
        threshold = timedelta(hours=self._warning_hours)
        soonest: dict | None = None
        for g in games:
            end = g.get("end_date")
            if end and (end - now) <= threshold:
                if soonest is None or end < soonest["end_date"]:
                    soonest = g
        return soonest

    @property
    def is_on(self) -> bool:
        return self._soonest_expiring() is not None

    @property
    def extra_state_attributes(self) -> dict:
        g = self._soonest_expiring()
        if not g:
            return {}
        now = datetime.now(tz=timezone.utc)
        expires_in = (g["end_date"] - now).total_seconds() / 3600
        return {
            "title": g.get("title", ""),
            "store": g.get("store") or g.get("platform", ""),
            "url": g.get("url", ""),
            "expires_in_hours": round(expires_in, 1),
        }


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


# ---------------------------------------------------------------------------
# Presence binary sensors
# ---------------------------------------------------------------------------

class AccountOnlineBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(self, coordinator, entry_id: str, account_key: str, name: str, platform: str) -> None:
        super().__init__(coordinator)
        self._account_key = account_key
        self._attr_device_info = _device_info(entry_id)
        self._attr_icon = "mdi:steam" if platform == "Steam" else "mdi:microsoft-xbox"
        self._attr_name = f"{name} Online"
        self._attr_unique_id = f"gaming_hub_{account_key}_online"

    @property
    def is_on(self) -> bool:
        accounts = (self.coordinator.data or {}).get("accounts", {})
        return accounts.get(self._account_key, {}).get("online", False)


class SomeoneIsGamingBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Someone Is Gaming"
    _attr_unique_id = "gaming_hub_someone_is_gaming"
    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_icon = "mdi:gamepad-variant"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry_id)

    @property
    def is_on(self) -> bool:
        return (self.coordinator.data or {}).get("someone_is_gaming", False)
