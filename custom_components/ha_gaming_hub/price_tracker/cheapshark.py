import logging

from ..const import CHEAPSHARK_API_URL

_LOGGER = logging.getLogger(__name__)


class CheapSharkClient:
    def __init__(self, session) -> None:
        self._session = session
        self._stores_cache: dict[str, str] = {}

    async def get_stores(self) -> dict[str, str]:
        if self._stores_cache:
            return self._stores_cache
        try:
            async with self._session.get(f"{CHEAPSHARK_API_URL}/stores") as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.warning("CheapShark stores fetch failed: %s", err)
            return {}
        self._stores_cache = {
            str(s["storeID"]): s["storeName"]
            for s in data
            if isinstance(s, dict) and s.get("isActive")
        }
        return self._stores_cache

    async def search_game(self, title: str) -> list[dict]:
        params = {"title": title, "exact": 0, "upperPrice": 60}
        try:
            async with self._session.get(f"{CHEAPSHARK_API_URL}/deals", params=params) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.warning("CheapShark search failed for '%s': %s", title, err)
            return []
        if not isinstance(data, list):
            return []
        seen: set[str] = set()
        results = []
        for deal in data:
            game_id = str(deal.get("gameID", ""))
            if game_id and game_id not in seen:
                seen.add(game_id)
                results.append({
                    "gameID": game_id,
                    "title": deal.get("title") or deal.get("internalName") or "",
                })
        return results

    async def get_game_prices(self, game_id: str) -> dict:
        stores = await self.get_stores()
        try:
            async with self._session.get(
                f"{CHEAPSHARK_API_URL}/games", params={"id": game_id}
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.warning("CheapShark prices fetch failed for game %s: %s", game_id, err)
            return {}

        deals = data.get("deals", [])
        if not deals:
            return {}

        best_deal = min(deals, key=lambda d: float(d.get("salePrice", 9999)))
        best_price = float(best_deal.get("salePrice", 0))
        store_id = str(best_deal.get("storeID", ""))
        best_store = stores.get(store_id, f"Store {store_id}")

        try:
            discount_pct = round(float(best_deal.get("savings", "0")), 1)
        except (ValueError, TypeError):
            discount_pct = 0.0

        cheapest_ever = data.get("cheapestPriceEver", {})
        cheapest_ever_price: float | None = None
        cheapest_ever_date: str | None = None
        if cheapest_ever:
            try:
                val = float(cheapest_ever.get("price", 0))
                cheapest_ever_price = val if val > 0 else None
            except (ValueError, TypeError):
                pass
            cheapest_ever_date = cheapest_ever.get("date")

        steam_app_id: str | None = None
        info = data.get("info", {})
        if info.get("steamAppID"):
            steam_app_id = str(info["steamAppID"])

        return {
            "best_price": best_price,
            "best_store": best_store,
            "discount_pct": discount_pct,
            "cheapest_ever_price": cheapest_ever_price,
            "cheapest_ever_date": cheapest_ever_date,
            "steam_app_id": steam_app_id,
            "all_deals": [
                {
                    "store": stores.get(str(d.get("storeID", "")), f"Store {d.get('storeID')}"),
                    "price": float(d.get("salePrice", 0)),
                    "retail_price": float(d.get("retailPrice", 0)),
                    "savings": round(float(d.get("savings", "0")), 1),
                }
                for d in deals
            ],
        }
