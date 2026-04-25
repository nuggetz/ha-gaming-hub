import asyncio
import logging

from homeassistant.core import HomeAssistant

from ..coordinator import GamingHubCoordinator
from ..const import EVENT_FRIEND_ONLINE
from .steam import SteamClient

_LOGGER = logging.getLogger(__name__)


class PresenceCoordinator(GamingHubCoordinator):

    def __init__(
        self,
        hass: HomeAssistant,
        session,
        scan_interval: int,
        steam_api_key: str,
        steam_ids: list[str],
        xbox_accounts: list[dict],
    ) -> None:
        super().__init__(
            hass,
            name="HA Gaming Hub - Presence",
            update_interval=scan_interval,
            session=session,
        )
        self.steam_ids = steam_ids
        self.xbox_accounts = xbox_accounts

        self._steam: SteamClient | None = (
            SteamClient(session, steam_api_key) if steam_api_key and steam_ids else None
        )
        self._prev_online: dict[str, bool] = {}
        self._initial_refresh_done: bool = False

    async def _async_update_data(self) -> dict:
        async def _noop() -> dict:
            return {}

        steam_coro = self._fetch_steam() if (self._steam and self.steam_ids) else _noop()
        steam_result, *_ = await asyncio.gather(steam_coro, return_exceptions=True)

        accounts: dict[str, dict] = {}

        if isinstance(steam_result, dict):
            for sid, info in steam_result.items():
                accounts[f"steam_{sid}"] = {"platform": "Steam", **info}
        elif isinstance(steam_result, Exception):
            _LOGGER.warning("Steam presence fetch failed: %s", steam_result)

        for account in self.xbox_accounts:
            slug = account.get("gamertag", "")
            if not slug:
                continue

            # Native Xbox integration entity: binary_sensor.{gamertag_slug}
            online_state = self.hass.states.get(f"binary_sensor.{slug}")

            online = online_state is not None and online_state.state == "on"

            # Try to get current game from binary_sensor attributes first,
            # then fall back to a separate now_playing sensor if it exists.
            playing: str | None = None
            if online_state:
                attrs = online_state.attributes
                playing = (
                    attrs.get("media_title")
                    or attrs.get("current_game")
                    or attrs.get("game")
                )
            if not playing:
                for candidate in (
                    f"sensor.{slug}_now_playing",
                    f"sensor.{slug}_game",
                    f"media_player.{slug}",
                ):
                    state = self.hass.states.get(candidate)
                    if state and state.state not in ("", "unknown", "unavailable", "None", "none", "idle", "off"):
                        playing = state.state
                        break

            accounts[f"xbox_{slug}"] = {
                "platform": "Xbox",
                "gamertag": slug,
                "online": online,
                "playing": playing,
            }

        if self._initial_refresh_done:
            for key, acc in accounts.items():
                if acc.get("online") and not self._prev_online.get(key, False):
                    self.hass.bus.async_fire(EVENT_FRIEND_ONLINE, {
                        "platform": acc.get("platform", ""),
                        "name": acc.get("name") or acc.get("gamertag") or key,
                        "playing": acc.get("playing"),
                    })
        else:
            self._initial_refresh_done = True
        self._prev_online = {key: bool(acc.get("online")) for key, acc in accounts.items()}

        someone_is_gaming = any(bool(acc.get("playing")) for acc in accounts.values())
        return {"accounts": accounts, "someone_is_gaming": someone_is_gaming}

    async def _fetch_steam(self) -> dict:
        summaries = await self._steam.get_player_summaries(self.steam_ids)
        for sid in self.steam_ids:
            if sid not in summaries:
                continue
            try:
                recent = await self._steam.get_recently_played(sid)
                hours = recent[0]["hours_2weeks"] if recent else None
            except Exception:
                hours = None
            summaries[sid]["hours_recent"] = hours
        return summaries
