import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_MODULES,
    CONF_ITAD_API_KEY,
    CONF_STEAM_API_KEY,
    CONF_STEAM_IDS,
    CONF_STEAM_WISHLIST_ID,
    CONF_XBOX_ACCOUNTS,
    MODULE_FREE_GAMES,
    MODULE_PRICE_TRACKER,
    MODULE_PRESENCE,
    DEFAULT_SCAN_INTERVAL_FREE_GAMES,
    DEFAULT_SCAN_INTERVAL_PRICE_TRACKER,
    DEFAULT_SCAN_INTERVAL_PRESENCE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "calendar"]

SERVICE_ADD_TO_WATCHLIST = "add_to_watchlist"
SERVICE_REMOVE_FROM_WATCHLIST = "remove_from_watchlist"

_SERVICE_ADD_SCHEMA = vol.Schema({vol.Required("title"): cv.string})
_SERVICE_REMOVE_SCHEMA = vol.Schema({vol.Required("slug"): cv.string})


def _get_pt_coordinator(hass: HomeAssistant):
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if not isinstance(entry_data, dict):
            continue
        coord = entry_data.get("coordinators", {}).get(MODULE_PRICE_TRACKER)
        if coord is not None:
            return coord
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    coordinators = {}
    enabled_modules = entry.data.get(CONF_MODULES, [])

    if MODULE_FREE_GAMES in enabled_modules:
        from .free_games.coordinator import FreeGamesCoordinator
        scan_interval = entry.data.get("scan_interval_free_games", DEFAULT_SCAN_INTERVAL_FREE_GAMES)
        steam_wishlist_id = entry.data.get(CONF_STEAM_WISHLIST_ID) or None
        steam_api_key = entry.data.get(CONF_STEAM_API_KEY) or None
        coordinator = FreeGamesCoordinator(hass, session, int(scan_interval), steam_wishlist_id, steam_api_key)
        await coordinator.async_config_entry_first_refresh()
        coordinators[MODULE_FREE_GAMES] = coordinator

    if MODULE_PRICE_TRACKER in enabled_modules:
        from .price_tracker.coordinator import PriceTrackerCoordinator
        scan_interval = int(entry.data.get("scan_interval_price_tracker", DEFAULT_SCAN_INTERVAL_PRICE_TRACKER))
        api_key_itad = entry.data.get(CONF_ITAD_API_KEY) or None
        steam_api_key = entry.data.get(CONF_STEAM_API_KEY) or None
        steam_wishlist_id = entry.data.get(CONF_STEAM_WISHLIST_ID) or None
        coordinator = PriceTrackerCoordinator(hass, session, scan_interval, api_key_itad, steam_api_key, steam_wishlist_id)
        await coordinator.async_config_entry_first_refresh()
        coordinators[MODULE_PRICE_TRACKER] = coordinator

    if MODULE_PRESENCE in enabled_modules:
        from .presence.coordinator import PresenceCoordinator
        scan_interval = int(entry.data.get("scan_interval_presence", DEFAULT_SCAN_INTERVAL_PRESENCE))
        steam_api_key = entry.data.get(CONF_STEAM_API_KEY, "")
        steam_ids = entry.data.get(CONF_STEAM_IDS, [])
        xbox_accounts = entry.data.get(CONF_XBOX_ACCOUNTS, [])
        coordinator = PresenceCoordinator(hass, session, scan_interval, steam_api_key, steam_ids, xbox_accounts)
        await coordinator.async_config_entry_first_refresh()
        coordinators[MODULE_PRESENCE] = coordinator

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinators": coordinators,
        "enabled_modules": enabled_modules,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_TO_WATCHLIST):

        async def _add_to_watchlist(call: ServiceCall) -> None:
            title: str = call.data["title"]
            coordinator = _get_pt_coordinator(hass)
            if not coordinator:
                _LOGGER.error("add_to_watchlist: Price Tracker module is not enabled")
                return
            candidates = await coordinator.cheapshark.search_game(title)
            if not candidates:
                _LOGGER.warning("add_to_watchlist: no results found for '%s'", title)
                return
            best = candidates[0]
            game_data = {"title": best["title"], "cheapshark_id": best["gameID"]}
            itad_results = await coordinator.itad.search_game(title)
            if itad_results:
                game_data["itad_id"] = itad_results[0]["id"]
            await coordinator.async_add_game(game_data)
            _LOGGER.info("add_to_watchlist: added '%s'", game_data["title"])

        async def _remove_from_watchlist(call: ServiceCall) -> None:
            slug: str = call.data["slug"]
            coordinator = _get_pt_coordinator(hass)
            if not coordinator:
                _LOGGER.error("remove_from_watchlist: Price Tracker module is not enabled")
                return
            await coordinator.async_remove_game(slug)
            _LOGGER.info("remove_from_watchlist: removed '%s'", slug)

        hass.services.async_register(
            DOMAIN, SERVICE_ADD_TO_WATCHLIST, _add_to_watchlist, schema=_SERVICE_ADD_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_REMOVE_FROM_WATCHLIST, _remove_from_watchlist, schema=_SERVICE_REMOVE_SCHEMA
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_ADD_TO_WATCHLIST)
            hass.services.async_remove(DOMAIN, SERVICE_REMOVE_FROM_WATCHLIST)
    return unload_ok
