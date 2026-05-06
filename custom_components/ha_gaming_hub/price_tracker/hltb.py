import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

_MIN_SIMILARITY = 0.5


def _sync_hltb_search(title: str):
    from howlongtobeatpy import HowLongToBeat
    return HowLongToBeat().search(title, similarity_case_sensitive=False)


async def search_hltb(title: str) -> dict | None:
    try:
        results = await asyncio.get_running_loop().run_in_executor(
            None, _sync_hltb_search, title
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
