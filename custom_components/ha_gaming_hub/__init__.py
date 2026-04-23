import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_MODULES,
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
        coordinator = FreeGamesCoordinator(hass, session)
        await coordinator.async_config_entry_first_refresh()
        coordinators[MODULE_FREE_GAMES] = coordinator

    if MODULE_PRICE_TRACKER in enabled_modules:
        from .price_tracker.coordinator import PriceTrackerCoordinator
        coordinator = PriceTrackerCoordinator(hass, session, entry.data)
        await coordinator.async_config_entry_first_refresh()
        coordinators[MODULE_PRICE_TRACKER] = coordinator

    if MODULE_PRESENCE in enabled_modules:
        from .presence.coordinator import PresenceCoordinator
        coordinator = PresenceCoordinator(hass, session, entry.data)
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
