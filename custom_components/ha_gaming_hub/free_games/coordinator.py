import asyncio
import logging
import re
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from ..coordinator import GamingHubCoordinator
from ..const import DEFAULT_SCAN_INTERVAL_FREE_GAMES
from .epic import EpicClient
from .gamerpower import GamerPowerClient

_LOGGER = logging.getLogger(__name__)


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def _merge_games(epic_games: list[dict], gamerpower_games: list[dict]) -> list[dict]:
    """Merge both sources; Epic takes priority on duplicate titles."""
    seen: dict[str, dict] = {}
    for game in epic_games:
        key = _normalize_title(game["title"])
        seen[key] = game
    for game in gamerpower_games:
        key = _normalize_title(game["title"])
        if key not in seen:
            seen[key] = game
    return list(seen.values())


class FreeGamesCoordinator(GamingHubCoordinator):
    """Coordinator for the Free Games module."""

    def __init__(self, hass: HomeAssistant, session, scan_interval: int = DEFAULT_SCAN_INTERVAL_FREE_GAMES):
        super().__init__(
            hass,
            name="HA Gaming Hub - Free Games",
            update_interval=scan_interval,
            session=session,
        )
        self.epic_client = EpicClient(session)
        self.gamerpower_client = GamerPowerClient(session)

    async def _async_update_data(self) -> dict:
        results = await asyncio.gather(
            self.epic_client.get_free_games(),
            self.gamerpower_client.get_free_games(),
            return_exceptions=True,
        )

        epic_games: list[dict] = []
        gamerpower_games: list[dict] = []

        if isinstance(results[0], Exception):
            _LOGGER.warning("Epic client error: %s", results[0])
        else:
            epic_games = results[0]

        if isinstance(results[1], Exception):
            _LOGGER.warning("GamerPower client error: %s", results[1])
        else:
            gamerpower_games = results[1]

        all_games = _merge_games(epic_games, gamerpower_games)

        now = datetime.now(tz=timezone.utc)

        current = []
        upcoming = []
        for game in all_games:
            if game.get("status") == "upcoming":
                upcoming.append(game)
            elif game.get("end_date") is None or game["end_date"] > now:
                current.append(game)

        total_value = sum(
            g["worth"] for g in current if g.get("worth") is not None
        )

        return {
            "current": current,
            "upcoming": upcoming,
            "count": len(current),
            "total_value": round(total_value, 2),
        }
