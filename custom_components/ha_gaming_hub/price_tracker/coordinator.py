import asyncio
import logging
from typing import Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..coordinator import GamingHubCoordinator
from ..const import DEFAULT_SCAN_INTERVAL_PRICE_TRACKER, EVENT_DEAL_FOUND, EVENT_HISTORICAL_LOW
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
        steam_api_key: str | None = None,
        steam_wishlist_id: str | None = None,
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
        self._steam_api_key = steam_api_key
        self._steam_wishlist_id = steam_wishlist_id
        self._sensor_add_cb: Callable | None = None
        self._sensor_remove_cb: Callable | None = None
        self._binary_sensor_add_cb: Callable | None = None
        self._binary_sensor_remove_cb: Callable | None = None
        self._prev_sale_state: dict[str, bool] = {}
        self._prev_low_state: dict[str, bool] = {}
        self._initial_refresh_done: bool = False
        self._score_cache: dict[str, dict] = {}

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

    async def _async_fetch_steam_wishlist(self) -> set[str]:
        if not self._steam_wishlist_id:
            return set()
        url = f"https://store.steampowered.com/wishlist/profiles/{self._steam_wishlist_id}/wishlistdata/"
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Steam wishlist returned HTTP %s", resp.status)
                    return set()
                data = await resp.json(content_type=None)
            if not isinstance(data, dict):
                return set()
            return set(data.keys())
        except Exception as err:
            _LOGGER.warning("Steam wishlist fetch failed: %s", err)
            return set()

    async def _async_update_data(self) -> dict[str, dict]:
        if not self.watchlist:
            return {}

        cs_tasks = [self._fetch_cheapshark(game) for game in self.watchlist]
        cs_results, wishlist_ids = await asyncio.gather(
            asyncio.gather(*cs_tasks, return_exceptions=True),
            self._async_fetch_steam_wishlist(),
        )

        itad_ids = [g["itad_id"] for g in self.watchlist if g.get("itad_id")]
        itad_data: dict[str, dict] = {}
        if itad_ids:
            try:
                itad_data = await self.itad.get_prices(itad_ids)
            except Exception as err:
                _LOGGER.warning("ITAD batch price fetch failed: %s", err)

        uncached_ids = [gid for gid in itad_ids if gid not in self._score_cache]
        if uncached_ids:
            try:
                info_data = await self.itad.get_game_info_batch(uncached_ids)
                for gid, info in info_data.items():
                    mc = (info.get("reviews") or {}).get("metacritic") or {}
                    oc = (info.get("reviews") or {}).get("opencritic") or {}
                    self._score_cache[gid] = {
                        "score": mc.get("score"),
                        "metacritic_url": mc.get("url", ""),
                        "opencritic_score": oc.get("score"),
                        "opencritic_url": oc.get("url", ""),
                    }
                for gid in uncached_ids:
                    self._score_cache.setdefault(gid, {})
            except Exception as err:
                _LOGGER.warning("ITAD game info fetch failed: %s", err)

        result: dict[str, dict] = {}
        for game, cs_result in zip(self.watchlist, cs_results):
            slug = game["slug"]
            score_info = self._score_cache.get(game.get("itad_id", ""), {})
            entry: dict = {
                "title": game["title"],
                "best_price": None,
                "best_store": None,
                "discount_pct": 0.0,
                "on_sale": False,
                "historical_low": False,
                "in_steam_wishlist": False,
                "thumb": None,
                "retail_price": None,
                "score": score_info.get("score"),
                "metacritic_url": score_info.get("metacritic_url", ""),
                "opencritic_score": score_info.get("opencritic_score"),
                "opencritic_url": score_info.get("opencritic_url", ""),
            }

            if isinstance(cs_result, dict) and cs_result:
                best_price = cs_result.get("best_price")
                entry["best_price"] = best_price
                entry["best_store"] = cs_result.get("best_store")
                entry["discount_pct"] = cs_result.get("discount_pct", 0.0)
                entry["on_sale"] = entry["discount_pct"] > 0
                entry["thumb"] = cs_result.get("thumb")
                entry["retail_price"] = cs_result.get("retail_price")

                cheapest_ever = cs_result.get("cheapest_ever_price")
                if best_price is not None and cheapest_ever is not None and cheapest_ever > 0:
                    entry["historical_low"] = best_price <= cheapest_ever

                steam_app_id = cs_result.get("steam_app_id")
                if steam_app_id and wishlist_ids:
                    entry["in_steam_wishlist"] = steam_app_id in wishlist_ids
            elif isinstance(cs_result, Exception):
                _LOGGER.warning("CheapShark fetch error for '%s': %s", game["title"], cs_result)

            result[slug] = entry

        if self._initial_refresh_done:
            for slug, entry in result.items():
                if entry["on_sale"] and not self._prev_sale_state.get(slug, False):
                    self.hass.bus.async_fire(EVENT_DEAL_FOUND, {
                        "title": entry["title"],
                        "best_price": entry["best_price"],
                        "best_store": entry["best_store"],
                        "discount_pct": entry["discount_pct"],
                        "in_steam_wishlist": entry["in_steam_wishlist"],
                    })
                if entry["historical_low"] and not self._prev_low_state.get(slug, False):
                    self.hass.bus.async_fire(EVENT_HISTORICAL_LOW, {
                        "title": entry["title"],
                        "best_price": entry["best_price"],
                        "best_store": entry["best_store"],
                        "in_steam_wishlist": entry["in_steam_wishlist"],
                    })
        else:
            self._initial_refresh_done = True
        self._prev_sale_state = {s: e["on_sale"] for s, e in result.items()}
        self._prev_low_state = {s: e["historical_low"] for s, e in result.items()}

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
