import logging
from datetime import timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODULE_FREE_GAMES, MODULE_PRICE_TRACKER, MODULE_PRESENCE

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

        entities.append(PriceTrackerDealsSensor(coordinator, entry.entry_id))

        for game in coordinator.watchlist:
            entities.extend(_price_tracker_sensors(coordinator, entry.entry_id, game))

        def on_game_added(game_data: dict) -> None:
            async_add_entities(
                _price_tracker_sensors(coordinator, entry.entry_id, game_data)
            )

        def on_game_removed(slug: str) -> None:
            ent_reg = er.async_get(hass)
            for sensor_type in ["best_price", "best_store", "discount_pct", "score", "cost_per_hour"]:
                uid = f"gaming_hub_{slug}_{sensor_type}"
                entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, uid)
                if entity_id:
                    ent_reg.async_remove(entity_id)

        coordinator.register_sensor_callbacks(on_game_added, on_game_removed)

    fg_coord = coordinators.get(MODULE_FREE_GAMES)
    pt_coord = coordinators.get(MODULE_PRICE_TRACKER)
    if fg_coord or pt_coord:
        entities.append(GamingHubDealsSensor(entry.entry_id, fg_coord, pt_coord))
    if fg_coord:
        entities.append(FreeGamesNextExpirySensor(fg_coord, entry.entry_id))
    if pt_coord:
        entities.append(WishlistDealsSensor(pt_coord, entry.entry_id))

    if MODULE_PRESENCE in coordinators:
        coordinator = coordinators[MODULE_PRESENCE]
        for account_key, acc in (coordinator.data or {}).get("accounts", {}).items():
            platform = acc.get("platform", "")
            name = acc.get("name") or acc.get("gamertag") or account_key
            entities.append(AccountPlayingSensor(coordinator, entry.entry_id, account_key, name, platform))
            if platform == "Steam":
                entities.append(SteamHoursRecentSensor(coordinator, entry.entry_id, account_key, name))

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
        GameScoreSensor(coordinator, entry_id, slug, title),
        GameCostPerHourSensor(coordinator, entry_id, slug, title),
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
            in_wishlist = g.get("in_steam_wishlist", False)
            wishlist_badge = "⭐ " if in_wishlist else ""
            media_entries.append({
                "title": g.get("title", ""),
                "rating": g.get("platform", ""),
                "price": f"{wishlist_badge}FREE" + (f" (${worth:.2f} value)" if worth else ""),
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
                "sale_price": f"{wishlist_badge}Free · {store}" if store else f"{wishlist_badge}Free",
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
    _attr_state_class = SensorStateClass.TOTAL

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
            "in_steam_wishlist": d.get("in_steam_wishlist", False),
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


class GameScoreSensor(_GameBaseSensor):
    _attr_icon = "mdi:star-circle"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "points"

    def __init__(self, coordinator, entry_id: str, slug: str, title: str) -> None:
        super().__init__(coordinator, entry_id, slug, title)
        self._attr_name = f"{title} Score"
        self._attr_unique_id = f"gaming_hub_{slug}_score"

    @property
    def native_value(self) -> int | None:
        return self._game_data().get("score")

    @property
    def extra_state_attributes(self) -> dict:
        d = self._game_data()
        attrs = {"metacritic_url": d.get("metacritic_url", "")}
        if d.get("opencritic_score") is not None:
            attrs["opencritic_score"] = d["opencritic_score"]
            attrs["opencritic_url"] = d.get("opencritic_url", "")
        return attrs


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


class GameCostPerHourSensor(_GameBaseSensor):
    _attr_icon = "mdi:clock-dollar"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "USD/h"

    def __init__(self, coordinator, entry_id: str, slug: str, title: str) -> None:
        super().__init__(coordinator, entry_id, slug, title)
        self._attr_name = f"{title} Cost Per Hour"
        self._attr_unique_id = f"gaming_hub_{slug}_cost_per_hour"

    @property
    def native_value(self) -> float | None:
        d = self._game_data()
        price = d.get("best_price")
        hours = d.get("hours_main")
        if price is None or not hours:
            return None
        return round(price / hours, 2)

    @property
    def extra_state_attributes(self) -> dict:
        d = self._game_data()
        return {
            "hours_main": d.get("hours_main"),
            "hours_extra": d.get("hours_extra"),
            "hours_completionist": d.get("hours_completionist"),
        }


class PriceTrackerDealsSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Price Tracker Deals"
    _attr_unique_id = "gaming_hub_price_tracker_deals"
    _attr_icon = "mdi:tag-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry_id)

    @property
    def native_value(self) -> int:
        return sum(1 for v in (self.coordinator.data or {}).values() if v.get("on_sale"))

    @property
    def extra_state_attributes(self) -> dict:
        on_sale_entries = []
        for data in sorted(
            (self.coordinator.data or {}).values(),
            key=lambda d: d.get("title", ""),
        ):
            best_price = data.get("best_price")
            retail_price = data.get("retail_price")
            best_store = data.get("best_store", "")
            in_wishlist = data.get("in_steam_wishlist", False)
            discount = data.get("discount_pct", 0.0)
            thumb = data.get("thumb") or ""

            price_str = f"${best_price:.2f}" if best_price is not None else "N/A"
            sale_price = (
                f"⭐ {price_str} · {best_store}" if in_wishlist else f"{price_str} · {best_store}"
            )
            normal_price = f"${retail_price:.2f}" if retail_price else ""

            on_sale_entries.append({
                "title": data.get("title", ""),
                "box_art_url": thumb,
                "backgroundart": thumb,
                "sale_price": sale_price,
                "normal_price": normal_price,
                "percent_off": int(discount),
            })

        return {"on_sale": on_sale_entries}


# ---------------------------------------------------------------------------
# Unified deals sensor (free games + price tracker watchlist)
# ---------------------------------------------------------------------------

class GamingHubDealsSensor(SensorEntity):
    """Single sensor combining Epic/GamerPower free games and ITAD watchlist deals.

    State = total item count. on_sale attribute = Nintendo Wishlist Card format.
    ⭐ prefix on sale_price when the game is in the user's Steam wishlist.
    """

    _attr_has_entity_name = True
    _attr_name = "Gaming Hub Deals"
    _attr_unique_id = "gaming_hub_deals"
    _attr_icon = "mdi:tag-multiple-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry_id: str, fg_coordinator=None, pt_coordinator=None) -> None:
        self._attr_device_info = _device_info(entry_id)
        self._fg = fg_coordinator
        self._pt = pt_coordinator
        self._unsubs: list = []

    async def async_added_to_hass(self) -> None:
        for coord in (self._fg, self._pt):
            if coord is not None:
                self._unsubs.append(coord.async_add_listener(self.async_write_ha_state))

    async def async_will_remove_from_hass(self) -> None:
        for unsub in self._unsubs:
            unsub()

    def _build_entries(self) -> list[dict]:
        entries: list[dict] = []

        # Free games (Epic + GamerPower, 100% free)
        if self._fg and self._fg.data:
            for g in self._fg.data.get("current", []):
                in_wishlist = g.get("in_steam_wishlist", False)
                badge = "⭐ " if in_wishlist else ""
                store = g.get("store") or g.get("platform", "")
                worth = g.get("worth")
                cover = g.get("cover", "")
                entries.append({
                    "title": g.get("title", ""),
                    "box_art_url": cover,
                    "backgroundart": cover,
                    "sale_price": f"{badge}Free · {store}" if store else f"{badge}Free",
                    "normal_price": f"${worth:.2f}" if worth else "",
                    "percent_off": 100,
                })

        # Price tracker watchlist (ITAD / CheapShark)
        if self._pt and self._pt.data:
            for data in sorted(
                self._pt.data.values(),
                key=lambda d: d.get("title", ""),
            ):
                best_price = data.get("best_price")
                retail_price = data.get("retail_price")
                best_store = data.get("best_store", "")
                in_wishlist = data.get("in_steam_wishlist", False)
                discount = data.get("discount_pct", 0.0)
                thumb = data.get("thumb") or ""
                badge = "⭐ " if in_wishlist else ""
                price_str = f"${best_price:.2f}" if best_price is not None else "N/A"
                entries.append({
                    "title": data.get("title", ""),
                    "box_art_url": thumb,
                    "backgroundart": thumb,
                    "sale_price": f"{badge}{price_str} · {best_store}",
                    "normal_price": f"${retail_price:.2f}" if retail_price else "",
                    "percent_off": int(discount),
                })

        return entries

    @property
    def native_value(self) -> int:
        return len(self._build_entries())

    @property
    def extra_state_attributes(self) -> dict:
        return {"on_sale": self._build_entries()}


# ---------------------------------------------------------------------------
# Helper sensors (Milestone 4)
# ---------------------------------------------------------------------------

class FreeGamesNextExpirySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Next Free Game Expiry"
    _attr_unique_id = "gaming_hub_next_expiry"
    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry_id)

    @property
    def native_value(self):
        games = self.coordinator.data.get("current", []) if self.coordinator.data else []
        upcoming = [g["end_date"] for g in games if g.get("end_date")]
        if not upcoming:
            return None
        return min(upcoming)

    @property
    def extra_state_attributes(self) -> dict:
        games = self.coordinator.data.get("current", []) if self.coordinator.data else []
        soonest = None
        for g in games:
            if g.get("end_date"):
                if soonest is None or g["end_date"] < soonest["end_date"]:
                    soonest = g
        if not soonest:
            return {}
        return {
            "title": soonest.get("title", ""),
            "store": soonest.get("store") or soonest.get("platform", ""),
            "url": soonest.get("url", ""),
        }


class WishlistDealsSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Wishlist Games On Sale"
    _attr_unique_id = "gaming_hub_wishlist_deals"
    _attr_icon = "mdi:star-circle"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry_id)

    @property
    def native_value(self) -> int:
        return sum(
            1
            for v in (self.coordinator.data or {}).values()
            if v.get("in_steam_wishlist") and v.get("on_sale")
        )

    @property
    def extra_state_attributes(self) -> dict:
        entries = []
        for data in (self.coordinator.data or {}).values():
            if not (data.get("in_steam_wishlist") and data.get("on_sale")):
                continue
            best_price = data.get("best_price")
            retail_price = data.get("retail_price")
            best_store = data.get("best_store", "")
            entries.append({
                "title": data.get("title", ""),
                "sale_price": f"⭐ ${best_price:.2f} · {best_store}" if best_price is not None else "⭐ N/A",
                "normal_price": f"${retail_price:.2f}" if retail_price else "",
                "percent_off": int(data.get("discount_pct", 0)),
                "historical_low": data.get("historical_low", False),
            })
        return {"on_sale": entries}


# ---------------------------------------------------------------------------
# Presence sensors
# ---------------------------------------------------------------------------

class _AccountBaseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str, account_key: str, name: str, platform: str) -> None:
        super().__init__(coordinator)
        self._account_key = account_key
        self._attr_device_info = _device_info(entry_id)
        self._platform = platform

    def _account_data(self) -> dict:
        return (self.coordinator.data or {}).get("accounts", {}).get(self._account_key, {})


class AccountPlayingSensor(_AccountBaseSensor):

    def __init__(self, coordinator, entry_id: str, account_key: str, name: str, platform: str) -> None:
        super().__init__(coordinator, entry_id, account_key, name, platform)
        icon = "mdi:steam" if platform == "Steam" else "mdi:microsoft-xbox"
        self._attr_icon = icon
        self._attr_name = f"{name} Playing"
        self._attr_unique_id = f"gaming_hub_{account_key}_playing"

    @property
    def native_value(self) -> str | None:
        return self._account_data().get("playing")


class SteamHoursRecentSensor(_AccountBaseSensor):
    _attr_icon = "mdi:clock-outline"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "h"

    def __init__(self, coordinator, entry_id: str, account_key: str, name: str) -> None:
        super().__init__(coordinator, entry_id, account_key, name, "Steam")
        self._attr_name = f"{name} Hours (2 weeks)"
        self._attr_unique_id = f"gaming_hub_{account_key}_hours_recent"

    @property
    def native_value(self) -> float | None:
        return self._account_data().get("hours_recent")
