import logging

_LOGGER = logging.getLogger(__name__)

_MIN_SIMILARITY = 0.5


async def search_hltb(title: str) -> dict | None:
    """Search HowLongToBeat for a game title.

    Returns a dict with hours_main/extra/completionist, or None if no
    good match is found. Uses the library's native async_search to avoid
    blocking the event loop.
    """
    try:
        from howlongtobeatpy import HowLongToBeat
        results = await HowLongToBeat().async_search(
            title, similarity_case_sensitive=False
        )
    except ImportError:
        _LOGGER.warning("howlongtobeatpy not installed — cost_per_hour unavailable")
        return None
    except Exception as err:
        _LOGGER.warning("HLTB search failed for '%s': %s", title, err)
        return None

    if not results:
        return None

    best = max(results, key=lambda r: r.similarity)
    if best.similarity < _MIN_SIMILARITY:
        _LOGGER.debug(
            "HLTB: no good match for '%s' (best similarity %.2f)", title, best.similarity
        )
        return None

    return {
        "hours_main": best.main_story if best.main_story and best.main_story > 0 else None,
        "hours_extra": best.main_extra if best.main_extra and best.main_extra > 0 else None,
        "hours_completionist": best.completionist if best.completionist and best.completionist > 0 else None,
    }
