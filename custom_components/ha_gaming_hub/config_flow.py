import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
    CONF_STEAM_WISHLIST_ID,
    CONF_XBOX_ACCOUNTS,
    DEFAULT_SCAN_INTERVAL_FREE_GAMES,
    DEFAULT_SCAN_INTERVAL_PRICE_TRACKER,
)

_LOGGER = logging.getLogger(__name__)

STEP_MODULE_SELECTION = "user"
STEP_FREE_GAMES = "free_games"
STEP_PRICE_TRACKER = "price_tracker"
STEP_STEAM = "steam"
STEP_XBOX_ENTITY = "xbox_entity"
STEP_SUMMARY = "summary"

SCAN_INTERVAL_FREE_GAMES_KEY = "scan_interval_free_games"
SCAN_INTERVAL_PRICE_TRACKER_KEY = "scan_interval_price_tracker"

_REMOVE_NONE = "_none_"


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
            wishlist_id = user_input.get(CONF_STEAM_WISHLIST_ID, "").strip()
            api_key = user_input.get(CONF_STEAM_API_KEY, "").strip()
            if wishlist_id:
                self._data[CONF_STEAM_WISHLIST_ID] = wishlist_id
            if api_key:
                self._data[CONF_STEAM_API_KEY] = api_key
            if MODULE_PRICE_TRACKER in self._data[CONF_MODULES]:
                return await self.async_step_price_tracker()
            if MODULE_PRESENCE in self._data[CONF_MODULES]:
                return await self.async_step_steam()
            return await self.async_step_summary()

        prefilled_wishlist_id = self._data.get(CONF_STEAM_WISHLIST_ID, "")
        prefilled_api_key = self._data.get(CONF_STEAM_API_KEY, "")
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
                vol.Optional(CONF_STEAM_API_KEY, default=prefilled_api_key): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_STEAM_WISHLIST_ID, default=prefilled_wishlist_id): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
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
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data[CONF_ITAD_API_KEY] = user_input.get(CONF_ITAD_API_KEY, "")
            self._data[SCAN_INTERVAL_PRICE_TRACKER_KEY] = user_input.get(
                SCAN_INTERVAL_PRICE_TRACKER_KEY, DEFAULT_SCAN_INTERVAL_PRICE_TRACKER
            )
            self._data[CONF_STEAM_API_KEY] = user_input.get(CONF_STEAM_API_KEY, "").strip()
            self._data[CONF_STEAM_WISHLIST_ID] = user_input.get(CONF_STEAM_WISHLIST_ID, "").strip()
            if MODULE_PRESENCE in self._data[CONF_MODULES]:
                return await self.async_step_steam()
            return await self.async_step_summary()

        prefilled_wishlist_id = self._data.get(CONF_STEAM_WISHLIST_ID, "")
        prefilled_api_key = self._data.get(CONF_STEAM_API_KEY, "")
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
                vol.Optional(CONF_STEAM_API_KEY, default=prefilled_api_key): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_STEAM_WISHLIST_ID, default=prefilled_wishlist_id): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }
        )

        return self.async_show_form(
            step_id=STEP_PRICE_TRACKER,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_steam(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input.get(CONF_STEAM_API_KEY, "").strip()
            raw_ids: list[str] = [s.strip() for s in user_input.get(CONF_STEAM_IDS, []) if s.strip()]

            if raw_ids and not api_key:
                errors[CONF_STEAM_API_KEY] = "steam_key_required"
            elif not raw_ids:
                # No IDs to track → skip Steam presence; keep api_key if provided
                if api_key:
                    self._data[CONF_STEAM_API_KEY] = api_key
                self._data[CONF_STEAM_IDS] = []
                return await self.async_step_xbox_entity()
            else:
                resolved_ids = await self._resolve_steam_ids(api_key, raw_ids)
                if resolved_ids is None:
                    errors[CONF_STEAM_IDS] = "steam_id_resolve_failed"
                else:
                    self._data[CONF_STEAM_API_KEY] = api_key
                    self._data[CONF_STEAM_IDS] = resolved_ids
                    return await self.async_step_xbox_entity()

        prefilled_key = self._data.get(CONF_STEAM_API_KEY, "")
        schema = vol.Schema(
            {
                vol.Optional(CONF_STEAM_API_KEY, default=prefilled_key): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_STEAM_IDS, default=[]): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT, multiple=True)
                ),
            }
        )
        return self.async_show_form(step_id=STEP_STEAM, data_schema=schema, errors=errors)

    async def _resolve_steam_ids(self, api_key: str, raw_ids: list[str]) -> list[str] | None:
        from .presence.steam import SteamClient
        session = async_get_clientsession(self.hass)
        client = SteamClient(session, api_key)
        resolved = []
        for raw in raw_ids:
            if raw.isdigit() and len(raw) == 17:
                resolved.append(raw)
            else:
                steam_id = await client.resolve_vanity_url(raw)
                if steam_id:
                    resolved.append(steam_id)
                else:
                    return None
        return resolved

    async def async_step_xbox_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Select Xbox accounts to track from the native Xbox integration."""
        if user_input is not None:
            selected = user_input.get("xbox_accounts", [])
            self._data[CONF_XBOX_ACCOUNTS] = [{"gamertag": s} for s in selected]
            return await self.async_step_summary()

        ent_reg = er.async_get(self.hass)
        xbox_slugs = []
        for entity in ent_reg.entities.values():
            if (
                entity.domain == "binary_sensor"
                and entity.entity_id.startswith("binary_sensor.xbox_")
                and entity.entity_id.endswith("_online")
            ):
                # entity_id: binary_sensor.xbox_{gamertag_slug}_online
                stripped = entity.entity_id.removeprefix("binary_sensor.xbox_").removesuffix("_online")
                if stripped:
                    xbox_slugs.append(stripped)

        # Auto-skip if the native Xbox integration is not installed
        if not xbox_slugs:
            self._data[CONF_XBOX_ACCOUNTS] = []
            return await self.async_step_summary()

        options = [{"value": s, "label": s} for s in sorted(xbox_slugs)]
        return self.async_show_form(
            step_id=STEP_XBOX_ENTITY,
            data_schema=vol.Schema({
                vol.Optional("xbox_accounts", default=[]): SelectSelector(
                    SelectSelectorConfig(options=options, multiple=True, mode=SelectSelectorMode.LIST)
                ),
            }),
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
        steam_wishlist_id = self._data.get(CONF_STEAM_WISHLIST_ID, "")
        xbox_accounts = self._data.get(CONF_XBOX_ACCOUNTS, [])

        if MODULE_PRESENCE in modules:
            xbox_summary = ", ".join(a["gamertag"] for a in xbox_accounts) if xbox_accounts else "none"
        else:
            xbox_summary = "—"

        placeholders = {
            "modules": ", ".join(modules),
            "itad_key": ("***" + itad_key[-4:]) if len(itad_key) > 4 else ("*" * len(itad_key)) if itad_key else "not set",
            "steam_key": ("***" + steam_key[-4:]) if len(steam_key) > 4 else ("*" * len(steam_key)) if steam_key else "not set",
            "steam_wishlist_id": steam_wishlist_id if steam_wishlist_id else "not set",
            "xbox_accounts": xbox_summary,
        }

        return self.async_show_form(
            step_id=STEP_SUMMARY,
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GamingHubOptionsFlowHandler()


class GamingHubOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow: manage Price Tracker watchlist."""

    def __init__(self) -> None:
        self._search_title: str = ""
        self._search_results: list[dict] = []
        self._coordinator = None

    def _get_coordinator(self):
        coordinators = self.hass.data.get(DOMAIN, {}).get(
            self.config_entry.entry_id, {}
        ).get("coordinators", {})
        return coordinators.get(MODULE_PRICE_TRACKER)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        enabled = self.config_entry.data.get(CONF_MODULES, [])
        if MODULE_PRICE_TRACKER not in enabled:
            return self.async_create_entry(title="", data={})

        self._coordinator = self._get_coordinator()

        if user_input is not None:
            add_title = (user_input.get("add_game_title") or "").strip()
            remove_slug = user_input.get("remove_game_slug", _REMOVE_NONE)

            if add_title:
                self._search_title = add_title
                return await self.async_step_watchlist_search()

            if remove_slug and remove_slug != _REMOVE_NONE and self._coordinator:
                await self._coordinator.async_remove_game(remove_slug)

            return self.async_create_entry(title="", data={})

        watchlist = self._coordinator.watchlist if self._coordinator else []
        titles = "\n".join(f"• {g['title']}" for g in watchlist) if watchlist else "(empty)"

        schema_dict: dict = {
            vol.Optional("add_game_title", default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }
        if watchlist:
            remove_options = [{"value": _REMOVE_NONE, "label": "— don't remove —"}] + [
                {"value": g["slug"], "label": g["title"]} for g in watchlist
            ]
            schema_dict[vol.Optional("remove_game_slug", default=_REMOVE_NONE)] = SelectSelector(
                SelectSelectorConfig(options=remove_options, mode=SelectSelectorMode.LIST)
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"watchlist": titles},
        )

    async def async_step_watchlist_search(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            choice = user_input.get("game_choice")
            if choice and self._coordinator:
                for result in self._search_results:
                    if result["gameID"] == choice:
                        await self._coordinator.async_add_game({
                            "title": result["title"],
                            "cheapshark_id": result["gameID"],
                            "itad_id": None,
                        })
                        break
            return self.async_create_entry(title="", data={})

        from .price_tracker.cheapshark import CheapSharkClient
        session = async_get_clientsession(self.hass)
        cs = CheapSharkClient(session)
        self._search_results = await cs.search_game(self._search_title)

        if not self._search_results:
            return self.async_show_form(
                step_id="watchlist_search",
                data_schema=vol.Schema({}),
                description_placeholders={"search_title": self._search_title},
                errors={"base": "no_results"},
            )

        options = [
            {"value": r["gameID"], "label": r["title"]} for r in self._search_results
        ]
        return self.async_show_form(
            step_id="watchlist_search",
            data_schema=vol.Schema({
                vol.Required("game_choice"): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                ),
            }),
            description_placeholders={"search_title": self._search_title},
        )
