import logging
from datetime import datetime, timedelta, timezone

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODULE_FREE_GAMES, MODULE_PRICE_TRACKER

_LOGGER = logging.getLogger(__name__)

_FALLBACK_DURATION = timedelta(days=7)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinators = entry_data["coordinators"]

    entities = []

    if MODULE_FREE_GAMES in coordinators:
        entities.append(FreeGamesCalendar(coordinators[MODULE_FREE_GAMES], entry.entry_id))

    if MODULE_PRICE_TRACKER in coordinators:
        entities.append(DealsCalendar(coordinators[MODULE_PRICE_TRACKER], entry.entry_id))

    async_add_entities(entities)


def _device_info(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Gaming Hub",
        manufacturer="HA Gaming Hub",
    )


def _game_to_event(game: dict) -> CalendarEvent | None:
    start = game.get("start_date")
    end = game.get("end_date")

    if start is None:
        start = datetime.now(tz=timezone.utc)

    if end is None:
        _LOGGER.debug("No end_date for '%s', using 7-day fallback", game.get("title"))
        end = start + _FALLBACK_DURATION

    return CalendarEvent(
        summary=game.get("title", "Unknown Game"),
        start=start,
        end=end,
        description=f"{game.get('platform', '')} — {game.get('url', '')}",
    )


class FreeGamesCalendar(CoordinatorEntity, CalendarEntity):
    _attr_has_entity_name = True
    _attr_name = "Free Games"
    _attr_unique_id = "gaming_hub_free_games_calendar"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry_id)

    @property
    def event(self) -> CalendarEvent | None:
        now = datetime.now(tz=timezone.utc)
        current = self.coordinator.data.get("current", [])

        with_end = [g for g in current if g.get("end_date") is not None]
        if with_end:
            soonest = min(with_end, key=lambda g: g["end_date"])
            return _game_to_event(soonest)

        if current:
            return _game_to_event(current[0])

        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        all_games = (
            self.coordinator.data.get("current", [])
            + self.coordinator.data.get("upcoming", [])
        )

        events = []
        for game in all_games:
            event = _game_to_event(game)
            if event is None:
                continue
            if event.end >= start_date and event.start <= end_date:
                events.append(event)

        return events


def _deal_to_event(slug: str, data: dict) -> CalendarEvent | None:
    end = data.get("deal_end_date")
    if not end:
        return None
    now = datetime.now(tz=timezone.utc)
    start = min(now, end)
    price = data.get("best_price")
    store = data.get("best_store", "")
    discount = data.get("discount_pct", 0)
    price_str = f"${price:.2f}" if price is not None else "N/A"
    summary = f"{data.get('title', slug)} — {price_str} (-{int(discount)}%) on {store}"
    lines = [f"Store: {store}", f"Price: {price_str}", f"Discount: {int(discount)}%"]
    if data.get("historical_low"):
        lines.append("All-time low!")
    return CalendarEvent(
        summary=summary,
        start=start,
        end=end,
        description="\n".join(lines),
    )


class DealsCalendar(CoordinatorEntity, CalendarEntity):
    _attr_has_entity_name = True
    _attr_name = "Deals"
    _attr_unique_id = "gaming_hub_deals_calendar"
    _attr_icon = "mdi:tag-multiple"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry_id)

    def _deals_with_expiry(self) -> list[tuple[str, dict]]:
        return [
            (slug, data)
            for slug, data in (self.coordinator.data or {}).items()
            if data.get("deal_end_date") is not None
        ]

    @property
    def event(self) -> CalendarEvent | None:
        deals = self._deals_with_expiry()
        if not deals:
            return None
        slug, data = min(deals, key=lambda x: x[1]["deal_end_date"])
        return _deal_to_event(slug, data)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        events = []
        for slug, data in self._deals_with_expiry():
            event = _deal_to_event(slug, data)
            if event is None:
                continue
            if event.end >= start_date and event.start <= end_date:
                events.append(event)
        return events
