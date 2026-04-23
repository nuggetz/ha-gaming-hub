import logging
from datetime import datetime, timezone

from ..const import GAMERPOWER_API_URL

_LOGGER = logging.getLogger(__name__)

_TYPE_MAP = {
    "game": "game",
    "dlc": "dlc",
    "loot": "loot",
    "early access": "other",
    "beta": "other",
    "alpha": "other",
    "other": "other",
}


def _parse_worth(value: str | None) -> float | None:
    if not value or value.strip().upper() == "N/A":
        return None
    try:
        return float(value.replace("$", "").strip())
    except ValueError:
        return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value or value.strip().upper() == "N/A":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class GamerPowerClient:
    def __init__(self, session) -> None:
        self._session = session

    async def get_free_games(self) -> list[dict]:
        params = {"platform": "pc", "sort-by": "popularity"}
        try:
            async with self._session.get(GAMERPOWER_API_URL, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.warning("GamerPower fetch failed: %s", err)
            return []

        if not isinstance(data, list):
            _LOGGER.warning("GamerPower returned unexpected format")
            return []

        results = []
        for item in data:
            platforms_str = item.get("platforms", "")
            if "epic" in platforms_str.lower():
                continue

            raw_type = (item.get("type") or "other").lower()
            normalized_type = _TYPE_MAP.get(raw_type, "other")

            results.append({
                "title": item.get("title", "Unknown"),
                "platform": platforms_str,
                "type": normalized_type,
                "start_date": _parse_dt(item.get("published_date")),
                "end_date": _parse_dt(item.get("end_date")),
                "url": item.get("open_giveaway_url") or item.get("giveaway_url", ""),
                "worth": _parse_worth(item.get("worth")),
                "status": "current",
            })

        return results
