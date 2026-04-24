import asyncio
import logging
from typing import Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..coordinator import GamingHubCoordinator
from ..const import DEFAULT_SCAN_INTERVAL_PRICE_TRACKER
from . import STORAGE_KEY, STORAGE_VERSION, load_watchlist, add_game_to_watchlist, remove_game_from_watchlist, _slugify
from .cheapshark import CheapSharkClient
from .itad import ITADClient

_LOGGER = logging.getLogger(__name__)


class PriceTrackerCoordinator(GamingHubCoordinator):

    def __init__(
        self,
        hass: HomeAssistant,
        session,
        scan_interval: int,
        api_key_itad: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            name="HA Gaming Hub - Price Tracker",
            update_interval=scan_interval,
            session=session,
        )
        self.cheapshark = CheapSharkClient(session)
        self.itad = ITADClient(session, api_key_itad)
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.watchlist: list[dict] = []
        self._sensor_add_cb: Callable | None = None
        self._sensor_remove_cb: Callable | None = None
        self._binary_sensor_add_cb: Callable | None = None
        self._binary_sensor_remove_cb: Callable | None = None

    def register_sensor_callbacks(
        self, on_add: Callable, on_remove: Callable
    ) -> None:
        self._sensor_add_cb = on_add
        self._sensor_remove_cb = on_remove

    def register_binary_sensor_callbacks(
        self, on_add: Callable, on_remove: Callable
    ) -> None:
        self._binary_sensor_add_cb = on_add
        self._binary_sensor_remove_cb = on_remove

    async def async_config_entry_first_refresh(self) -> None:
        self.watchlist = await load_watchlist(self.store)
        await super().async_config_entry_first_refresh()

    async def async_add_game(self, game_data: dict) -> None:
        game_data.setdefault("slug", _slugify(game_data["title"]))
        self.watchlist = await add_game_to_watchlist(self.store, game_data)
        if self._sensor_add_cb:
            self._sensor_add_cb(game_data)
        if self._binary_sensor_add_cb:
            self._binary_sensor_add_cb(game_data)
        await self.async_refresh()

    async def async_remove_game(self, slug: str) -> None:
        self.watchlist = await remove_game_from_watchlist(self.store, slug)
        if self._sensor_remove_cb:
            self._sensor_remove_cb(slug)
        if self._binary_sensor_remove_cb:
            self._binary_sensor_remove_cb(slug)
        await self.async_refresh()

    async def _async_update_data(self) -> dict[str, dict]:
        if not self.watchlist:
            return {}

        cs_tasks = [self._fetch_cheapshark(game) for game in self.watchlist]
        cs_results = await asyncio.gather(*cs_tasks, return_exceptions=True)

        itad_ids = [g["itad_id"] for g in self.watchlist if g.get("itad_id")]
        itad_data: dict[str, dict] = {}
        if itad_ids:
            try:
                itad_data = await self.itad.get_prices(itad_ids)
            except Exception as err:
                _LOGGER.warning("ITAD batch price fetch failed: %s", err)

        result: dict[str, dict] = {}
        for game, cs_result in zip(self.watchlist, cs_results):
            slug = game["slug"]
            entry: dict = {
                "title": game["title"],
                "best_price": None,
                "best_store": None,
                "discount_pct": 0.0,
                "on_sale": False,
                "historical_low": False,
            }

            if isinstance(cs_result, dict) and cs_result:
                best_price = cs_result.get("best_price")
                entry["best_price"] = best_price
                entry["best_store"] = cs_result.get("best_store")
                entry["discount_pct"] = cs_result.get("discount_pct", 0.0)
                entry["on_sale"] = entry["discount_pct"] > 0

                cheapest_ever = cs_result.get("cheapest_ever_price")
                if best_price is not None and cheapest_ever is not None and cheapest_ever > 0:
                    entry["historical_low"] = best_price <= cheapest_ever
            elif isinstance(cs_result, Exception):
                _LOGGER.warning("CheapShark fetch error for '%s': %s", game["title"], cs_result)

            result[slug] = entry

        return result

    async def _fetch_cheapshark(self, game: dict) -> dict:
        cheapshark_id = game.get("cheapshark_id")
        if not cheapshark_id:
            candidates = await self.cheapshark.search_game(game["title"])
            if not candidates:
                _LOGGER.debug("CheapShark: no results for '%s'", game["title"])
                return {}
            cheapshark_id = candidates[0]["gameID"]
            game["cheapshark_id"] = cheapshark_id
        return await self.cheapshark.get_game_prices(cheapshark_id)
