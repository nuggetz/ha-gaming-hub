import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    DOMAIN,
    MODULE_FREE_GAMES,
    MODULE_PRICE_TRACKER,
    MODULE_PRESENCE,
    CONF_MODULES,
    CONF_ITAD_API_KEY,
    CONF_STEAM_API_KEY,
    CONF_STEAM_IDS,
    DEFAULT_SCAN_INTERVAL_FREE_GAMES,
    DEFAULT_SCAN_INTERVAL_PRICE_TRACKER,
)

_LOGGER = logging.getLogger(__name__)

STEP_MODULE_SELECTION = "user"
STEP_FREE_GAMES = "free_games"
STEP_PRICE_TRACKER = "price_tracker"
STEP_STEAM = "steam"
STEP_XBOX = "xbox"
STEP_SUMMARY = "summary"

SCAN_INTERVAL_FREE_GAMES_KEY = "scan_interval_free_games"
SCAN_INTERVAL_PRICE_TRACKER_KEY = "scan_interval_price_tracker"


class GamingHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for HA Gaming Hub."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input.get(CONF_MODULES, [])
            if not selected:
                errors[CONF_MODULES] = "no_modules_selected"
            else:
                self._data[CONF_MODULES] = selected
                if MODULE_FREE_GAMES in selected:
                    return await self.async_step_free_games()
                if MODULE_PRICE_TRACKER in selected:
                    return await self.async_step_price_tracker()
                if MODULE_PRESENCE in selected:
                    return await self.async_step_steam()
                return await self.async_step_summary()

        schema = vol.Schema(
            {
                vol.Required(CONF_MODULES): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": MODULE_FREE_GAMES, "label": "Free Games"},
                            {"value": MODULE_PRICE_TRACKER, "label": "Price Tracker"},
                            {"value": MODULE_PRESENCE, "label": "Presence (Steam & Xbox)"},
                        ],
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_free_games(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._data[SCAN_INTERVAL_FREE_GAMES_KEY] = user_input.get(
                SCAN_INTERVAL_FREE_GAMES_KEY, DEFAULT_SCAN_INTERVAL_FREE_GAMES
            )
            if MODULE_PRICE_TRACKER in self._data[CONF_MODULES]:
                return await self.async_step_price_tracker()
            if MODULE_PRESENCE in self._data[CONF_MODULES]:
                return await self.async_step_steam()
            return await self.async_step_summary()

        schema = vol.Schema(
            {
                vol.Optional(
                    SCAN_INTERVAL_FREE_GAMES_KEY,
                    default=DEFAULT_SCAN_INTERVAL_FREE_GAMES,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1800,
                        max=86400,
                        step=1800,
                        unit_of_measurement="seconds",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id=STEP_FREE_GAMES,
            data_schema=schema,
        )

    async def async_step_price_tracker(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._data[CONF_ITAD_API_KEY] = user_input.get(CONF_ITAD_API_KEY, "")
            self._data[SCAN_INTERVAL_PRICE_TRACKER_KEY] = user_input.get(
                SCAN_INTERVAL_PRICE_TRACKER_KEY, DEFAULT_SCAN_INTERVAL_PRICE_TRACKER
            )
            if MODULE_PRESENCE in self._data[CONF_MODULES]:
                return await self.async_step_steam()
            return await self.async_step_summary()

        schema = vol.Schema(
            {
                vol.Optional(CONF_ITAD_API_KEY, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(
                    SCAN_INTERVAL_PRICE_TRACKER_KEY,
                    default=DEFAULT_SCAN_INTERVAL_PRICE_TRACKER,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=3600,
                        max=86400,
                        step=3600,
                        unit_of_measurement="seconds",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id=STEP_PRICE_TRACKER,
            data_schema=schema,
        )

    async def async_step_steam(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get(CONF_STEAM_API_KEY):
                errors[CONF_STEAM_API_KEY] = "steam_key_required"
            else:
                self._data[CONF_STEAM_API_KEY] = user_input[CONF_STEAM_API_KEY]
                self._data[CONF_STEAM_IDS] = user_input.get(CONF_STEAM_IDS, [])
                return await self.async_step_xbox()

        schema = vol.Schema(
            {
                vol.Required(CONF_STEAM_API_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_STEAM_IDS, default=[]): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT,
                        multiple=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id=STEP_STEAM,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_xbox(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            return await self.async_step_summary()

        return self.async_show_form(
            step_id=STEP_XBOX,
            data_schema=vol.Schema({}),
            description_placeholders={
                "info": "Xbox setup will be completed after saving via the Options Flow."
            },
        )

    async def async_step_summary(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="HA Gaming Hub", data=self._data)

        modules = self._data.get(CONF_MODULES, [])
        itad_key = self._data.get(CONF_ITAD_API_KEY, "")
        steam_key = self._data.get(CONF_STEAM_API_KEY, "")

        placeholders = {
            "modules": ", ".join(modules),
            "itad_key": ("***" + itad_key[-4:]) if len(itad_key) > 4 else ("*" * len(itad_key)) if itad_key else "not set",
            "steam_key": ("***" + steam_key[-4:]) if len(steam_key) > 4 else ("*" * len(steam_key)) if steam_key else "not set",
        }

        return self.async_show_form(
            step_id=STEP_SUMMARY,
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GamingHubOptionsFlowHandler(config_entry)


class GamingHubOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler (placeholder — logic added in future milestones)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
            description_placeholders={
                "info": (
                    "Options configuration (watchlist, accounts, polling intervals) "
                    "will be available in a future release."
                )
            },
        )
