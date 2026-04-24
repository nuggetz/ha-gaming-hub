import logging

import httpx
from homeassistant.helpers.storage import Store

from xbox.webapi.authentication.manager import AuthenticationManager
from xbox.webapi.authentication.models import OAuth2TokenResponse
from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.presence.models import PresenceLevel, PresenceState
from xbox.webapi.common.signed_session import SignedSession

_LOGGER = logging.getLogger(__name__)

XBOX_CLIENT_ID = "388ea51c-0b25-4029-aae2-17df49d23905"
XBOX_TOKEN_STORAGE_KEY = "ha_gaming_hub_xbox_tokens"
XBOX_TOKEN_STORAGE_VERSION = 1

_MS_DEVICE_CODE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
_MS_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
_XBL_SCOPES = "Xboxlive.signin Xboxlive.offline_access"


class XboxAuthPendingError(Exception):
    """Token not yet granted — user has not authorized yet."""


class XboxAuthExpiredError(Exception):
    """Device code has expired."""


class XboxAuthDeclinedError(Exception):
    """User declined the authorization."""


class XboxDeviceCodeFlow:
    """Manages the Microsoft Device Code Flow to obtain an initial Xbox Live token."""

    def __init__(self, session, client_id: str) -> None:
        self._session = session
        self._client_id = client_id

    async def start_flow(self) -> dict:
        """Start the device code flow. Returns the device code response dict."""
        data = {
            "client_id": self._client_id,
            "scope": _XBL_SCOPES,
        }
        async with self._session.post(
            _MS_DEVICE_CODE_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def poll_for_token(self, device_code: str) -> dict:
        """Poll the token endpoint once.

        Returns the token dict if authorized.
        Raises XboxAuthPendingError if not yet authorized.
        Raises XboxAuthExpiredError if the device code has expired.
        Raises XboxAuthDeclinedError if the user declined.
        """
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": self._client_id,
            "device_code": device_code,
        }
        async with self._session.post(
            _MS_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as resp:
            body = await resp.json(content_type=None)

        error = body.get("error")
        if not error:
            return body

        if error == "authorization_pending":
            raise XboxAuthPendingError()
        if error == "expired_token":
            raise XboxAuthExpiredError()
        if error == "authorization_declined":
            raise XboxAuthDeclinedError()
        raise Exception(f"Xbox token error: {error} — {body.get('error_description', '')}")


class XboxClient:
    """Manages a single authenticated Xbox Live account."""

    def __init__(self, hass, xuid: str, client_id: str = XBOX_CLIENT_ID) -> None:
        self._hass = hass
        self._xuid = xuid
        self._client_id = client_id
        self._store = Store(hass, XBOX_TOKEN_STORAGE_VERSION, XBOX_TOKEN_STORAGE_KEY)
        self._auth_mgr: AuthenticationManager | None = None
        self._xl_client: XboxLiveClient | None = None
        self._signed_session: SignedSession | None = None
        self.gamertag: str = ""

    async def async_init(self) -> bool:
        """Load tokens from storage and initialize the Xbox Live client.

        Returns False if tokens are missing (setup not completed).
        """
        data = await self._store.async_load() or {}
        account = data.get("accounts", {}).get(self._xuid)
        if not account:
            _LOGGER.debug("No Xbox token found for xuid %s", self._xuid)
            return False

        try:
            oauth = OAuth2TokenResponse(**{
                k: account[k]
                for k in ("token_type", "expires_in", "scope", "access_token", "refresh_token", "user_id")
                if k in account
            })
        except Exception as err:
            _LOGGER.warning("Failed to reconstruct Xbox OAuth token for %s: %s", self._xuid, err)
            return False

        self._signed_session = SignedSession()
        self._auth_mgr = AuthenticationManager(
            self._signed_session, self._client_id, "", ""
        )
        self._auth_mgr.oauth = oauth
        self._xl_client = XboxLiveClient(self._auth_mgr)
        self.gamertag = account.get("gamertag", "")
        return True

    async def get_presence(self) -> dict:
        """Fetch current presence for this account.

        Returns {gamertag, xuid, online, playing}.
        """
        if not self._auth_mgr or not self._xl_client:
            return {"gamertag": self.gamertag, "xuid": self._xuid, "online": False, "playing": None}

        try:
            await self._auth_mgr.refresh_tokens()
            await self._save_tokens()

            self.gamertag = self._auth_mgr.xsts_token.gamertag

            presence = await self._xl_client.presence.get_presence(
                self._xuid, PresenceLevel.ALL
            )

            online = presence.state == PresenceState.ACTIVE
            playing: str | None = None
            if online and presence.devices:
                for device in presence.devices:
                    for title in device.titles or []:
                        if title.placement == "Full" and title.state == "Active":
                            playing = title.name
                            break
                    if playing:
                        break

            return {"gamertag": self.gamertag, "xuid": self._xuid, "online": online, "playing": playing}

        except Exception as err:
            _LOGGER.warning("Xbox presence fetch failed for %s: %s", self._xuid, err)
            return {"gamertag": self.gamertag, "xuid": self._xuid, "online": False, "playing": None}

    async def _save_tokens(self) -> None:
        """Persist refreshed OAuth token to storage."""
        if not self._auth_mgr or not self._auth_mgr.oauth:
            return
        data = await self._store.async_load() or {}
        accounts = data.setdefault("accounts", {})
        accounts[self._xuid] = {
            "gamertag": self.gamertag,
            "token_type": self._auth_mgr.oauth.token_type,
            "expires_in": self._auth_mgr.oauth.expires_in,
            "scope": self._auth_mgr.oauth.scope,
            "access_token": self._auth_mgr.oauth.access_token,
            "refresh_token": self._auth_mgr.oauth.refresh_token or "",
            "user_id": self._auth_mgr.oauth.user_id,
        }
        await self._store.async_save(data)


async def save_xbox_account(hass, xuid: str, gamertag: str, token_data: dict) -> None:
    """Persist a newly authorized Xbox account to HA Storage."""
    store = Store(hass, XBOX_TOKEN_STORAGE_VERSION, XBOX_TOKEN_STORAGE_KEY)
    data = await store.async_load() or {}
    accounts = data.setdefault("accounts", {})
    accounts[xuid] = {
        "gamertag": gamertag,
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_in": token_data.get("expires_in", 3600),
        "scope": token_data.get("scope", _XBL_SCOPES),
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "user_id": token_data.get("user_id", ""),
    }
    await store.async_save(data)


async def exchange_token_for_xsts(token_data: dict, client_id: str = XBOX_CLIENT_ID) -> tuple[str, str]:
    """Exchange a Device Code OAuth token for an XSTS token.

    Returns (xuid, gamertag).
    """
    oauth = OAuth2TokenResponse(
        token_type=token_data.get("token_type", "Bearer"),
        expires_in=int(token_data.get("expires_in", 3600)),
        scope=token_data.get("scope", _XBL_SCOPES),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        user_id=token_data.get("user_id", ""),
    )
    async with SignedSession() as session:
        auth_mgr = AuthenticationManager(session, client_id, "", "")
        auth_mgr.oauth = oauth
        await auth_mgr.refresh_tokens()
        return auth_mgr.xsts_token.xuid, auth_mgr.xsts_token.gamertag
