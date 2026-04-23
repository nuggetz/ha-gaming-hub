import logging
from datetime import datetime, timedelta, timezone

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN, MODULE_FREE_GAMES

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
        entities.append(FreeGamesCalendar(coordinators[MODULE_FREE_GAMES]))

    async_add_entities(entities)


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
    _attr_name = "Free Games"
    _attr_unique_id = "gaming_hub_free_games_calendar"

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
