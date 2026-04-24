import logging
import re
from datetime import datetime, timezone

from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "ha_gaming_hub_watchlist"
STORAGE_VERSION = 1


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


async def load_watchlist(store: Store) -> list[dict]:
    data = await store.async_load()
    if not data:
        return []
    return data.get("games", [])


async def save_watchlist(store: Store, games: list[dict]) -> None:
    await store.async_save({"games": games})


async def add_game_to_watchlist(store: Store, game_data: dict) -> list[dict]:
    games = await load_watchlist(store)
    slug = game_data.get("slug") or _slugify(game_data["title"])
    itad_id = game_data.get("itad_id")
    for existing in games:
        if (itad_id and existing.get("itad_id") == itad_id) or existing["slug"] == slug:
            return games
    games.append({
        "title": game_data["title"],
        "slug": slug,
        "cheapshark_id": game_data.get("cheapshark_id"),
        "itad_id": itad_id,
        "added_at": datetime.now(tz=timezone.utc).isoformat(),
    })
    await save_watchlist(store, games)
    return games


async def remove_game_from_watchlist(store: Store, slug: str) -> list[dict]:
    games = await load_watchlist(store)
    games = [g for g in games if g["slug"] != slug]
    await save_watchlist(store, games)
    return games
