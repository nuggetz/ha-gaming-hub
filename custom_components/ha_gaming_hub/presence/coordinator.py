import asyncio
import logging

from homeassistant.core import HomeAssistant

from ..coordinator import GamingHubCoordinator
from .steam import SteamClient
from .xbox import XboxClient

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
        xbox_client_id: str = "",
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
        self._xbox_clients: list[XboxClient] = [
            XboxClient(hass, acc["xuid"], xbox_client_id) for acc in xbox_accounts if acc.get("xuid")
        ]

    async def async_config_entry_first_refresh(self) -> None:
        for client in self._xbox_clients:
            ok = await client.async_init()
            if not ok:
                _LOGGER.warning(
                    "Xbox client for xuid %s could not load tokens", client._xuid
                )
        await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> dict:
        async def _noop() -> dict:
            return {}

        steam_coro = self._fetch_steam() if (self._steam and self.steam_ids) else _noop()
        xbox_tasks = [client.get_presence() for client in self._xbox_clients]

        results = await asyncio.gather(steam_coro, *xbox_tasks, return_exceptions=True)
        steam_result = results[0]
        xbox_results = results[1:]

        accounts: dict[str, dict] = {}

        if isinstance(steam_result, dict):
            for sid, info in steam_result.items():
                accounts[f"steam_{sid}"] = {"platform": "Steam", **info}
        elif isinstance(steam_result, Exception):
            _LOGGER.warning("Steam presence fetch failed: %s", steam_result)

        for client, result in zip(self._xbox_clients, xbox_results):
            if isinstance(result, dict):
                accounts[f"xbox_{client._xuid}"] = {"platform": "Xbox", **result}
            else:
                _LOGGER.warning("Xbox presence fetch failed for %s: %s", client._xuid, result)

        someone_is_gaming = any(
            bool(acc.get("playing")) for acc in accounts.values()
        )

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
