import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_gaming_hub"
INTEGRATION_NAME = "HA Gaming Hub"

# Module keys
MODULE_FREE_GAMES = "free_games"
MODULE_PRICE_TRACKER = "price_tracker"
MODULE_PRESENCE = "presence"

# Config entry keys
CONF_MODULES = "modules"
CONF_ITAD_API_KEY = "itad_api_key"
CONF_STEAM_API_KEY = "steam_api_key"
CONF_STEAM_IDS = "steam_ids"
CONF_STEAM_WISHLIST_ID = "steam_wishlist_id"
CONF_XBOX_ACCOUNTS = "xbox_accounts"
CONF_PSN_ACCOUNTS = "psn_accounts"

# Default polling intervals (seconds)
DEFAULT_SCAN_INTERVAL_FREE_GAMES = 3600
DEFAULT_SCAN_INTERVAL_PRICE_TRACKER = 21600
DEFAULT_SCAN_INTERVAL_PRESENCE = 300

# API endpoints
EPIC_FREE_GAMES_URL = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
GAMERPOWER_API_URL = "https://www.gamerpower.com/api/giveaways"
CHEAPSHARK_API_URL = "https://www.cheapshark.com/api/1.0"
ITAD_API_URL = "https://api.isthereanydeal.com"
STEAM_API_URL = "https://api.steampowered.com"

# Entity name prefixes
ENTITY_PREFIX = "gaming_hub"

# Free game expiry warning
DEFAULT_EXPIRY_WARNING_HOURS = 24
CONF_EXPIRY_WARNING_HOURS = "expiry_warning_hours"

# Events
EVENT_FREE_GAME_ADDED = "ha_gaming_hub_free_game_added"
EVENT_DEAL_FOUND = "ha_gaming_hub_deal_found"
EVENT_HISTORICAL_LOW = "ha_gaming_hub_historical_low"
EVENT_FRIEND_ONLINE = "ha_gaming_hub_friend_online"
EVENT_SESSION_STARTED = "ha_gaming_hub_session_started"
EVENT_SESSION_ENDED = "ha_gaming_hub_session_ended"
