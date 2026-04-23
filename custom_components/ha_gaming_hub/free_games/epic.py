import logging
import re
from datetime import datetime, timezone

from ..const import EPIC_FREE_GAMES_URL

_LOGGER = logging.getLogger(__name__)

_EPIC_STORE_BASE = "https://store.epicgames.com/en-US/p"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _build_url(element: dict) -> str:
    slug = element.get("productSlug") or ""
    if not slug:
        mappings = (
            element.get("catalogNs", {}).get("mappings") or []
        )
        if mappings:
            slug = mappings[0].get("pageSlug", "")
    if slug:
        return f"{_EPIC_STORE_BASE}/{slug}"
    title_slug = re.sub(r"[^a-z0-9]+", "-", element.get("title", "").lower()).strip("-")
    return f"{_EPIC_STORE_BASE}/{title_slug}"


class EpicClient:
    def __init__(self, session) -> None:
        self._session = session

    async def get_free_games(self) -> list[dict]:
        params = {
            "locale": "en-US",
            "country": "US",
            "allowCountries": "US",
        }
        try:
            async with self._session.get(EPIC_FREE_GAMES_URL, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as err:
            _LOGGER.warning("Epic Games fetch failed: %s", err)
            return []

        elements = (
            data.get("data", {})
            .get("Catalog", {})
            .get("searchStore", {})
            .get("elements", [])
        )

        results = []
        for el in elements:
            if el.get("offerType") != "BASE_GAME":
                continue

            promotions = el.get("promotions") or {}
            active_offers = promotions.get("promotionalOffers") or []
            upcoming_offers = promotions.get("upcomingPromotionalOffers") or []

            url = _build_url(el)
            title = el.get("title", "Unknown")

            for group in active_offers:
                for offer in group.get("promotionalOffers", []):
                    discount_price = (
                        el.get("price", {})
                        .get("totalPrice", {})
                        .get("discountPrice", -1)
                    )
                    if discount_price != 0:
                        continue
                    results.append({
                        "title": title,
                        "platform": "Epic Games",
                        "type": "game",
                        "start_date": _parse_dt(offer.get("startDate")),
                        "end_date": _parse_dt(offer.get("endDate")),
                        "url": url,
                        "worth": None,
                        "status": "current",
                    })

            for group in upcoming_offers:
                for offer in group.get("promotionalOffers", []):
                    results.append({
                        "title": title,
                        "platform": "Epic Games",
                        "type": "game",
                        "start_date": _parse_dt(offer.get("startDate")),
                        "end_date": _parse_dt(offer.get("endDate")),
                        "url": url,
                        "worth": None,
                        "status": "upcoming",
                    })

        return results
