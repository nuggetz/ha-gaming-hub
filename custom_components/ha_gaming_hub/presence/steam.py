import logging

from ..const import STEAM_API_URL

_LOGGER = logging.getLogger(__name__)

_STATE_MAP = {
    0: "Offline",
    1: "Online",
    2: "Busy",
    3: "Away",
    4: "Snooze",
    5: "Looking to trade",
    6: "Looking to play",
}

_CHUNK_SIZE = 100


class SteamClient:
    def __init__(self, session, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    async def resolve_vanity_url(self, vanity: str) -> str | None:
        params = {"key": self._api_key, "vanityurl": vanity}
        try:
            async with self._session.get(
                f"{STEAM_API_URL}/ISteamUser/ResolveVanityURL/v1/", params=params
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.warning("Steam ResolveVanityURL failed for '%s': %s", vanity, err)
            return None
        inner = data.get("response", {})
        if inner.get("success") == 1:
            return str(inner.get("steamid", ""))
        return None

    async def get_player_summaries(self, steam_ids: list[str]) -> dict[str, dict]:
        results: dict[str, dict] = {}
        for i in range(0, len(steam_ids), _CHUNK_SIZE):
            chunk = steam_ids[i : i + _CHUNK_SIZE]
            params = {"key": self._api_key, "steamids": ",".join(chunk)}
            try:
                async with self._session.get(
                    f"{STEAM_API_URL}/ISteamUser/GetPlayerSummaries/v2/", params=params
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
            except Exception as err:
                _LOGGER.warning("Steam GetPlayerSummaries failed: %s", err)
                continue
            for player in data.get("response", {}).get("players", []):
                sid = str(player.get("steamid", ""))
                if not sid:
                    continue
                state = int(player.get("personastate", 0))
                game_id = player.get("gameid")
                results[sid] = {
                    "name": player.get("personaname", "Unknown"),
                    "online": state > 0,
                    "playing": player.get("gameextrainfo") if game_id else None,
                    "status": _STATE_MAP.get(state, "Unknown"),
                    "avatar_url": player.get("avatarfull", ""),
                    "profile_url": player.get("profileurl", ""),
                }
        return results

    async def get_recently_played(self, steam_id: str) -> list[dict]:
        params = {"key": self._api_key, "steamid": steam_id, "count": 5}
        try:
            async with self._session.get(
                f"{STEAM_API_URL}/IPlayerService/GetRecentlyPlayedGames/v1/",
                params=params,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.warning("Steam GetRecentlyPlayedGames failed for %s: %s", steam_id, err)
            return []
        games = data.get("response", {}).get("games", [])
        return [
            {
                "name": g.get("name", ""),
                "appid": g.get("appid"),
                "hours_2weeks": round(g.get("playtime_2weeks", 0) / 60, 1),
                "hours_total": round(g.get("playtime_forever", 0) / 60, 1),
            }
            for g in games
        ]
