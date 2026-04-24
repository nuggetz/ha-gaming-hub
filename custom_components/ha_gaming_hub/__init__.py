import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    coordinators = {}
    enabled_modules = entry.data.get(CONF_MODULES, [])

    if MODULE_FREE_GAMES in enabled_modules:
        from .free_games.coordinator import FreeGamesCoordinator
        scan_interval = entry.data.get("scan_interval_free_games", DEFAULT_SCAN_INTERVAL_FREE_GAMES)
        coordinator = FreeGamesCoordinator(hass, session, int(scan_interval))
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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
