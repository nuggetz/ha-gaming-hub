import asyncio
import logging
from datetime import datetime, timedelta, timezone

from ..const import ITAD_API_URL

_LOGGER = logging.getLogger(__name__)

_BATCH_SIZE = 20
_THROTTLE_DELAY = 1.0


class ITADClient:
    def __init__(self, session, api_key: str | None = None) -> None:
        self._session = session
        self._api_key = api_key

    def _headers(self) -> dict:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    async def search_game(self, title: str) -> list[dict]:
        params = {"title": title, "results": 5}
        try:
            async with self._session.get(
                f"{ITAD_API_URL}/games/search/v1",
                params=params,
                headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.warning("ITAD search failed for '%s': %s", title, err)
            return []
        if not isinstance(data, list):
            return []
        return [
            {"id": g["id"], "slug": g.get("slug", ""), "title": g.get("title", "")}
            for g in data
            if isinstance(g, dict) and "id" in g
        ]

    async def get_prices(self, game_ids: list[str]) -> dict[str, dict]:
        if not game_ids:
            return {}
        results: dict[str, dict] = {}
        for i in range(0, len(game_ids), _BATCH_SIZE):
            batch = game_ids[i : i + _BATCH_SIZE]
            if i > 0:
                await asyncio.sleep(_THROTTLE_DELAY)
            try:
                async with self._session.post(
                    f"{ITAD_API_URL}/games/prices/v3",
                    params={"country": "US", "shops": "steam,gog,epic,fanatical,humblebundle"},
                    json=batch,
                    headers=self._headers(),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
            except Exception as err:
                _LOGGER.warning("ITAD prices fetch failed (batch %d): %s", i, err)
                continue
            if not isinstance(data, list):
                continue
            for item in data:
                game_id = item.get("id")
                if not game_id:
                    continue
                deals = item.get("deals") or []
                if not deals:
                    results[game_id] = {}
                    continue
                best_deal = min(
                    deals, key=lambda d: d.get("price", {}).get("amount", 9999)
                )
                results[game_id] = {
                    "best_price": best_deal.get("price", {}).get("amount"),
                    "best_store": best_deal.get("shop", {}).get("name", ""),
                    "cut_pct": best_deal.get("cut", 0),
                    "expiry": best_deal.get("expiry"),
                    "all_deals": [
                        {
                            "store": d.get("shop", {}).get("name", ""),
                            "price": d.get("price", {}).get("amount"),
                            "regular": d.get("regular", {}).get("amount"),
                            "cut": d.get("cut", 0),
                        }
                        for d in deals
                    ],
                }
        return results

    async def get_game_info_batch(self, game_ids: list[str]) -> dict[str, dict]:
        """Fetch Metacritic/OpenCritic scores from ITAD /games/info/v2 (requires API key)."""
        if not self._api_key:
            return {}
        results: dict[str, dict] = {}
        for i, game_id in enumerate(game_ids):
            if i > 0:
                await asyncio.sleep(_THROTTLE_DELAY)
            try:
                async with self._session.get(
                    f"{ITAD_API_URL}/games/info/v2",
                    params={"id": game_id},
                    headers=self._headers(),
                ) as resp:
                    if resp.status in (401, 403):
                        _LOGGER.debug("ITAD API key required for game info")
                        break
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
            except Exception as err:
                _LOGGER.warning("ITAD info fetch failed for %s: %s", game_id, err)
                continue
            if isinstance(data, dict):
                results[game_id] = data
        return results

    async def is_historical_low(self, game_id: str, current_price: float) -> bool:
        if not self._api_key:
            _LOGGER.debug(
                "ITAD API key not set, skipping historical low check for %s", game_id
            )
            return False
        since = (datetime.now(tz=timezone.utc) - timedelta(days=3650)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        try:
            async with self._session.get(
                f"{ITAD_API_URL}/games/history/v2",
                params={"id": game_id, "country": "US", "since": since},
                headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.warning("ITAD history fetch failed for %s: %s", game_id, err)
            return False
        if not isinstance(data, list) or not data:
            return False
        try:
            min_price = min(
                entry.get("price", {}).get("amount", 9999)
                for entry in data
                if isinstance(entry, dict)
            )
        except (ValueError, TypeError):
            return False
        return current_price <= min_price
