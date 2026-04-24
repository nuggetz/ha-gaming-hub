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

_STEAM_APP_URL_RE = re.compile(r"store\.steampowered\.com/app/(\d+)", re.IGNORECASE)
_NOISE_RE = re.compile(r"\b(giveaway|give away|free game|free dlc)\b", re.IGNORECASE)


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def _clean_title(title: str) -> str:
    """Strip noise words added by giveaway platforms before wishlist matching."""
    return _normalize_title(_NOISE_RE.sub("", title))


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

    def __init__(
        self,
        hass: HomeAssistant,
        session,
        scan_interval: int = DEFAULT_SCAN_INTERVAL_FREE_GAMES,
        steam_wishlist_id: str | None = None,
    ):
        super().__init__(
            hass,
            name="HA Gaming Hub - Free Games",
            update_interval=scan_interval,
            session=session,
        )
        self.epic_client = EpicClient(session)
        self.gamerpower_client = GamerPowerClient(session)
        self._steam_wishlist_id = steam_wishlist_id

    async def _async_fetch_wishlist(self) -> tuple[set[str], set[str]]:
        """Return (appid_set, normalized_title_set) from the Steam wishlist."""
        if not self._steam_wishlist_id:
            return set(), set()
        url = f"https://store.steampowered.com/wishlist/profiles/{self._steam_wishlist_id}/wishlistdata/"
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Steam wishlist returned HTTP %s", resp.status)
                    return set(), set()
                data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.warning("Steam wishlist fetch failed: %s", err)
            return set(), set()
        if not isinstance(data, dict):
            return set(), set()
        appids = set(data.keys())
        titles = {_normalize_title(v["name"]) for v in data.values() if isinstance(v, dict) and v.get("name")}
        return appids, titles

    async def _async_update_data(self) -> dict:
        results, (wishlist_appids, wishlist_titles) = await asyncio.gather(
            asyncio.gather(
                self.epic_client.get_free_games(),
                self.gamerpower_client.get_free_games(),
                return_exceptions=True,
            ),
            self._async_fetch_wishlist(),
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

        def _in_wishlist(game: dict) -> bool:
            if not wishlist_appids and not wishlist_titles:
                return False
            m = _STEAM_APP_URL_RE.search(game.get("url") or "")
            if m and m.group(1) in wishlist_appids:
                return True
            return _clean_title(game.get("title", "")) in wishlist_titles

        current = []
        upcoming = []
        for game in all_games:
            game["in_steam_wishlist"] = _in_wishlist(game)
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
