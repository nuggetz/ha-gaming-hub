import json
import logging
from datetime import timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MODULE_FREE_GAMES,
    MODULE_PRICE_TRACKER,
    MODULE_PRESENCE,
    CONF_FREE_GAMES_MAX_ITEMS,
    DEFAULT_FREE_GAMES_MAX_ITEMS,
    MAX_STATE_ATTRS_BYTES,
)

_LOGGER = logging.getLogger(__name__)

# The recorder measures the *full* attribute dict, which includes the
# friendly_name/icon/device_class/state_class that HA appends on top of whatever
# extra_state_attributes returns. Aim below the cap rather than at it.
_ATTRS_BUDGET = MAX_STATE_ATTRS_BYTES - 512


def _attrs_size(attrs: dict) -> int:
    """Serialised size in bytes, measured the same way the recorder measures it."""
    try:
        return len(json_bytes(attrs))
    except (TypeError, ValueError):
        return len(json.dumps(attrs, default=str).encode())


def _fit_attributes(attrs: dict, list_keys: tuple[str, ...], entity_name: str) -> dict:
    """Trim list attributes until the payload fits under the recorder's limit.

    Above MAX_STATE_ATTRS_BYTES the recorder stores *no* attributes at all for the
    state, so the entities carrying a payload are exactly the ones that lose their
    history. Dropping the tail keeps the rest recoverable. Lists are pre-sorted by
    relevance (soonest expiry first), so the tail is the cheapest thing to lose.
    """
    if _attrs_size(attrs) <= _ATTRS_BUDGET:
        return attrs

    trimmed = {k: (list(v) if k in list_keys and isinstance(v, list) else v) for k, v in attrs.items()}
    lists = [k for k in list_keys if isinstance(trimmed.get(k), list)]
    dropped = 0

    while _attrs_size(trimmed) > _ATTRS_BUDGET:
        # Always shrink the longest list; never empty one out completely, since a
        # bare header row is still meaningful to the cards that read it.
        longest = max(lists, key=lambda k: len(trimmed[k]), default=None)
        if longest is None or len(trimmed[longest]) <= 1:
            break
        trimmed[longest].pop()
        dropped += 1

    _LOGGER.debug(
        "%s: attributes exceeded %d bytes, dropped %d entries to fit (now %d bytes)",
        entity_name,
        _ATTRS_BUDGET,
        dropped,
        _attrs_size(trimmed),
    )
    return trimmed


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinators = entry_data["coordinators"]
    max_items = int(entry.data.get(CONF_FREE_GAMES_MAX_ITEMS, DEFAULT_FREE_GAMES_MAX_ITEMS))

    entities = []

    if MODULE_FREE_GAMES in coordinators:
        coordinator = coordinators[MODULE_FREE_GAMES]
        entities.extend([
            FreeGamesCountSensor(coordinator, entry.entry_id, max_items),
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
        entities.append(GamingHubDealsSensor(entry.entry_id, fg_coord, pt_coord, max_items))
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
            entities.append(SessionDurationSensor(coordinator, entry.entry_id, account_key, name, platform))
            if platform == "Steam":
                entities.append(SteamHoursRecentSensor(coordinator, entry.entry_id, account_key, name))

    async_add_entities(entities)


def _device_info(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Gaming Hub",
        manufacturer="HA Gaming Hub",
    )


def _nintendo_entry(
    title: str,
    image: str,
    sale_price: str,
    normal_price: str,
    percent_off: int,
) -> dict:
    """One entry in nintendo-wishlist-card format.

    No `backgroundart`: the card renders `box_art_url` and only tests backgroundart
    for truthiness to pick a CSS background-position, never reading it as a URL.
    None of our sources provide a wide image distinct from the cover, so the field
    used to carry a duplicate of box_art_url — 28% of the payload for no
    information. Add it back only if a source ever gives real background art.
    """
    return {
        "title": title,
        "box_art_url": image,
        "sale_price": sale_price,
        "normal_price": normal_price,
        "percent_off": percent_off,
    }


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

    def __init__(self, coordinator, entry_id: str, max_items: int = DEFAULT_FREE_GAMES_MAX_ITEMS) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry_id)
        self._max_items = max_items

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("count", 0)

    @property
    def extra_state_attributes(self) -> dict:
        games = self.coordinator.data.get("current", [])[: self._max_items]
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
            poster = g.get("poster", cover)
            store = g.get("store", g.get("platform", ""))
            in_wishlist = g.get("in_steam_wishlist", False)
            wishlist_badge = "⭐ " if in_wishlist else ""
            # upcoming-media-card reads `poster` (default image_style) and falls
            # back to it when `fanart` is absent, so only send fanart when it is
            # genuinely a different image. It never reads box_art_url at all.
            media = {
                "title": g.get("title", ""),
                "rating": g.get("platform", ""),
                "price": f"{wishlist_badge}FREE" + (f" (${worth:.2f} value)" if worth else ""),
                "release": f"Expires {end_dt.strftime('%-d %b %Y')}" if end_dt else "",
                "genres": g.get("type", ""),
                "airdate": end_dt.strftime("%Y-%m-%d") if end_dt else "unknown",
                "poster": poster,
                "deep_link": g.get("url", ""),
            }
            if cover and cover != poster:
                media["fanart"] = cover
            media_entries.append(media)
            nintendo_entries.append(_nintendo_entry(
                title=g.get("title", ""),
                image=cover,
                sale_price=f"{wishlist_badge}Free · {store}" if store else f"{wishlist_badge}Free",
                normal_price=f"${worth:.2f}" if worth else "",
                percent_off=100,
            ))
        return _fit_attributes(
            {"data": [header] + media_entries, "on_sale": nintendo_entries},
            ("data", "on_sale"),
            "sensor.gaming_hub_free_games_count",
        )


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
    _attr_state_class = SensorStateClass.TOTAL
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

            on_sale_entries.append(_nintendo_entry(
                title=data.get("title", ""),
                image=thumb,
                sale_price=sale_price,
                normal_price=normal_price,
                percent_off=int(discount),
            ))

        # No fixed cap here: every entry is a game the user explicitly watchlisted.
        return _fit_attributes(
            {"on_sale": on_sale_entries},
            ("on_sale",),
            "sensor.gaming_hub_price_tracker_deals",
        )


# ---------------------------------------------------------------------------
# Unified deals sensor (free games + price tracker watchlist)
# ---------------------------------------------------------------------------

class GamingHubDealsSensor(SensorEntity):
    """Single sensor combining Epic/GamerPower free games and ITAD watchlist deals.

    State = total item count. on_sale attribute = Nintendo Wishlist Card format.
    ⭐ prefix on sale_price when the game is in the user's Steam wishlist.
    """

    _attr_has_entity_name = True
    _attr_name = "Deals"
    _attr_unique_id = "gaming_hub_deals"
    _attr_icon = "mdi:tag-multiple-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entry_id: str,
        fg_coordinator=None,
        pt_coordinator=None,
        max_items: int = DEFAULT_FREE_GAMES_MAX_ITEMS,
    ) -> None:
        self._attr_device_info = _device_info(entry_id)
        self._fg = fg_coordinator
        self._pt = pt_coordinator
        self._max_items = max_items
        self._unsubs: list = []

    async def async_added_to_hass(self) -> None:
        for coord in (self._fg, self._pt):
            if coord is not None:
                self._unsubs.append(coord.async_add_listener(self.async_write_ha_state))

    async def async_will_remove_from_hass(self) -> None:
        for unsub in self._unsubs:
            unsub()

    def _build_entries(self, limit: int | None = None) -> list[dict]:
        """Build the entry list. `limit` caps the free-games half only.

        The state stays the true total, so an automation counting deals is unaffected
        by how many of them fit in the attributes.
        """
        entries: list[dict] = []

        # Free games (Epic + GamerPower, 100% free). Capped: this list is fed by an
        # API that returns everything currently on offer, unlike the watchlist below.
        if self._fg and self._fg.data:
            free_games = self._fg.data.get("current", [])
            for g in free_games if limit is None else free_games[:limit]:
                in_wishlist = g.get("in_steam_wishlist", False)
                badge = "⭐ " if in_wishlist else ""
                store = g.get("store") or g.get("platform", "")
                worth = g.get("worth")
                cover = g.get("cover", "")
                entries.append(_nintendo_entry(
                    title=g.get("title", ""),
                    image=cover,
                    sale_price=f"{badge}Free · {store}" if store else f"{badge}Free",
                    normal_price=f"${worth:.2f}" if worth else "",
                    percent_off=100,
                ))

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
                entries.append(_nintendo_entry(
                    title=data.get("title", ""),
                    image=thumb,
                    sale_price=f"{badge}{price_str} · {best_store}",
                    normal_price=f"${retail_price:.2f}" if retail_price else "",
                    percent_off=int(discount),
                ))

        return entries

    @property
    def native_value(self) -> int:
        return len(self._build_entries())

    @property
    def extra_state_attributes(self) -> dict:
        return _fit_attributes(
            {"on_sale": self._build_entries(limit=self._max_items)},
            ("on_sale",),
            "sensor.gaming_hub_deals",
        )


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
        return _fit_attributes(
            {"on_sale": entries},
            ("on_sale",),
            "sensor.gaming_hub_wishlist_games_on_sale",
        )


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
        if platform == "Steam":
            self._attr_icon = "mdi:steam"
        elif platform == "PSN":
            self._attr_icon = "mdi:sony-playstation"
        else:
            self._attr_icon = "mdi:microsoft-xbox"
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


class SessionDurationSensor(_AccountBaseSensor):
    _attr_icon = "mdi:clock-play"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, entry_id: str, account_key: str, name: str, platform: str) -> None:
        super().__init__(coordinator, entry_id, account_key, name, platform)
        self._attr_name = f"{name} Session Duration"
        self._attr_unique_id = f"gaming_hub_{account_key}_session_duration"

    @property
    def native_value(self) -> int | None:
        session_start = self._account_data().get("session_start")
        if session_start is None:
            return None
        from datetime import datetime
        return int((datetime.now(tz=timezone.utc) - session_start).total_seconds() / 60)

    @property
    def extra_state_attributes(self) -> dict:
        data = self._account_data()
        attrs: dict = {"game": data.get("playing")}
        session_start = data.get("session_start")
        if session_start:
            attrs["started_at"] = session_start.isoformat()
        return attrs
