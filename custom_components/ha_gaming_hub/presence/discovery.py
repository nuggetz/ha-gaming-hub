"""Language-independent discovery helpers for native presence integrations.

Native integrations (PlayStation Network, Xbox) generate their ``entity_id``
suffixes from *translated* friendly names, so any logic that matches on a
hardcoded English suffix (e.g. ``_online_status``) silently breaks on a
non-English Home Assistant instance. These helpers resolve the right entities
via the entity registry ``translation_key`` and the device registry instead,
which are language-independent by design.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify

PSN_INTEGRATION = "playstation_network"
PSN_ONLINE_STATUS_KEY = "online_status"
PSN_NOW_PLAYING_KEY = "now_playing"


def resolve_psn_account(hass: HomeAssistant, entity_id: str) -> dict | None:
    """Resolve a PSN account from any of its registry entities.

    Given *any* entity belonging to a PlayStation Network account (the user may
    pick whichever one is convenient in the entity selector), locate its device
    and return the account's online-status and now-playing sensors by
    ``translation_key`` — never by a localized entity_id suffix.

    Returns a dict ``{slug, name, online_status, now_playing}`` or ``None`` if
    the entity cannot be resolved to a PSN device.
    """
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(entity_id)
    if entry is None or entry.device_id is None:
        return None

    online_status: str | None = None
    now_playing: str | None = None
    for sibling in er.async_entries_for_device(
        ent_reg, entry.device_id, include_disabled_entities=True
    ):
        if sibling.domain != "sensor":
            continue
        if sibling.translation_key == PSN_ONLINE_STATUS_KEY:
            online_status = sibling.entity_id
        elif sibling.translation_key == PSN_NOW_PLAYING_KEY:
            now_playing = sibling.entity_id

    # Fall back to the picked entity if the online-status sensor isn't found
    # (e.g. a future PSN release renames the translation key).
    if online_status is None:
        online_status = entity_id

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(entry.device_id)
    name = (device.name_by_user or device.name) if device else entity_id

    return {
        "slug": slugify(name),
        "name": name,
        "online_status": online_status,
        "now_playing": now_playing,
    }


def xbox_now_playing_from_device(hass: HomeAssistant, entity_id: str) -> str | None:
    """Best-effort "now playing" fallback for an Xbox account.

    The Xbox binary_sensor usually carries the game name in its attributes; this
    is only used when it doesn't. Rather than guessing English entity_id
    suffixes, look for a ``media_player`` on the same device (whose state is the
    current media/game title), which is language-independent.
    """
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(entity_id)
    if entry is None or entry.device_id is None:
        return None

    for sibling in er.async_entries_for_device(
        ent_reg, entry.device_id, include_disabled_entities=False
    ):
        if sibling.domain != "media_player":
            continue
        state = hass.states.get(sibling.entity_id)
        if state and state.state not in (
            "",
            "unknown",
            "unavailable",
            "None",
            "none",
            "idle",
            "off",
            "standby",
        ):
            return state.state
    return None
