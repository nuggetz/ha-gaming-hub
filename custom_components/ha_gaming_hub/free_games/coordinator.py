import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import UpdateFailed

from ..coordinator import GamingHubCoordinator
from ..const import DEFAULT_SCAN_INTERVAL_FREE_GAMES, STEAM_API_URL

from .epic import EpicClient
from .gamerpower import GamerPowerClient

_LOGGER = logging.getLogger(__name__)

_STEAM_APP_URL_RE = re.compile(r"store\.steampowered\.com/app/(\d+)", re.IGNORECASE)
_NOISE_RE = re.compile(r"\b(giveaway|give away|free game|free dlc)\b", re.IGNORECASE)
# Platform names appended by giveaway sites (e.g. "8AM Steam", "Game (Epic Games)")
_PLATFORM_SUFFIX_RE = re.compile(
    r"\s*[\(\[]?\s*(steam|epic\s*games?|gog|itch\.?io|indiegala|stove|humble|ubisoft)\s*[\)\]]?\s*$",
    re.IGNORECASE,
)
# Integration name prefix on steam_wishlist friendly_name ("Steam 8AM", "Steam Wishlist - X")
_STEAM_PREFIX_RE = re.compile(r"(?i)^steam(?:\s+wishlist)?\s*[-:–]?\s*")


def _normalize_title(title: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", "", title.lower())
    return re.sub(r"\s+", " ", s).strip()


def _clean_title(title: str) -> str:
    """Strip noise/platform suffixes added by giveaway platforms before wishlist matching."""
    t = _NOISE_RE.sub("", title)
    t = _PLATFORM_SUFFIX_RE.sub("", t)
    return _normalize_title(t)


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
        steam_api_key: str | None = None,
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
        self._steam_api_key = steam_api_key
        self._wishlist_appids: set[str] = set()
        self._wishlist_titles: set[str] = set()
        self._wishlist_unsub: Callable | None = None

    def _subscribe_steam_wishlist_sensor(self) -> None:
        """Subscribe to state changes of the steam_wishlist sensor.

        Fired once when the sensor populates after HA startup; triggers a
        coordinator refresh so stars appear without waiting for the next
        scheduled poll (default 30 min).
        """
        if self._wishlist_unsub is not None or not self._steam_wishlist_id:
            return

        entity_id = f"sensor.steam_wishlist_{self._steam_wishlist_id}"

        @callback
        def _on_sensor_updated(event) -> None:
            new_state = event.data.get("new_state")
            if new_state and (new_state.attributes.get("data") or new_state.attributes.get("games")):
                if self._wishlist_unsub:
                    self._wishlist_unsub()
                    self._wishlist_unsub = None
                self.hass.async_create_task(self.async_refresh())

        self._wishlist_unsub = async_track_state_change_event(
            self.hass, entity_id, _on_sensor_updated
        )

    async def _async_fetch_wishlist(self) -> tuple[set[str], set[str]]:
        """Return (appid_set, normalized_title_set) from the Steam wishlist."""
        if not self._steam_wishlist_id:
            return set(), set()

        # Primary: read from steam_wishlist HA integration (sensor.steam_wishlist_<id>)
        ha_state = self.hass.states.get(f"sensor.steam_wishlist_{self._steam_wishlist_id}")
        if ha_state is not None:
            # Read appids + titles from the main sensor's data/on_sale attribute
            raw = ha_state.attributes.get("data") or ha_state.attributes.get("on_sale") or ha_state.attributes.get("games") or []
            sensor_appids: set[str] = set()
            sensor_titles: set[str] = set()
            for g in raw:
                sid = g.get("steam_id") or g.get("appid")
                if sid:
                    sensor_appids.add(str(sid))
                name = g.get("title") or g.get("name", "")
                if name:
                    sensor_titles.add(_clean_title(name))

            # Also scan binary_sensor.steam_wishlist_* entities for the full wishlist
            from homeassistant.helpers import entity_registry as er
            ent_reg = er.async_get(self.hass)
            for entity in ent_reg.entities.values():
                if entity.platform == "steam_wishlist" and entity.domain == "binary_sensor":
                    bs_state = self.hass.states.get(entity.entity_id)
                    if bs_state:
                        sid = bs_state.attributes.get("steam_id") or bs_state.attributes.get("appid")
                        if sid:
                            sensor_appids.add(str(sid))
                        # Use entity_id slug as title — already lowercase, no special chars,
                        # and never has the "Steam Wishlist" prefix that friendly_name may carry
                        slug = entity.entity_id.removeprefix("binary_sensor.steam_wishlist_")
                        if slug and slug != entity.entity_id:
                            sensor_titles.add(slug.replace("_", " ").strip())
                        # Also try friendly_name after stripping the integration prefix
                        fname = bs_state.attributes.get("friendly_name", "")
                        fname = _STEAM_PREFIX_RE.sub("", fname).strip()
                        if fname:
                            sensor_titles.add(_clean_title(fname))

            if sensor_appids or sensor_titles:
                self._wishlist_appids = sensor_appids
                self._wishlist_titles = sensor_titles
                return sensor_appids, sensor_titles

            self._subscribe_steam_wishlist_sensor()

        # Return cached wishlist from a previous successful fetch if available
        if self._wishlist_appids or self._wishlist_titles:
            return self._wishlist_appids, self._wishlist_titles

        # Fallback: official Steam API (needs key, works regardless of profile privacy)
        appids: set[str] = set()
        titles: set[str] = set()

        if self._steam_api_key:
            try:
                url = f"{STEAM_API_URL}/IWishlistService/GetWishlist/v1/"
                params = {"key": self._steam_api_key, "steamid": self._steam_wishlist_id}
                async with self.session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        items = data.get("response", {}).get("items", [])
                        appids = {str(item["appid"]) for item in items if "appid" in item}
            except Exception as err:
                _LOGGER.warning("Steam API wishlist fetch failed: %s", err)

        # Fallback: web endpoint (gives names for title-based matching; blocked for private profiles)
        try:
            url = f"https://store.steampowered.com/wishlist/profiles/{self._steam_wishlist_id}/wishlistdata/"
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    # Steam returns {"success": 2} on error — skip non-game keys
                    if isinstance(data, dict) and "success" not in data and data:
                        if not appids:
                            appids = set(data.keys())
                        titles = {
                            _normalize_title(v["name"])
                            for v in data.values()
                            if isinstance(v, dict) and v.get("name")
                        }
        except Exception as err:
            _LOGGER.debug("Steam wishlistdata fetch failed: %s", err)

        if appids:
            self._wishlist_appids = appids
        if titles:
            self._wishlist_titles = titles

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
