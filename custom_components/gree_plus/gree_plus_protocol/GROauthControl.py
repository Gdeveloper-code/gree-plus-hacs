"""OAuth client for the Gree Plus integration."""

import base64
from dataclasses import dataclass
import hashlib
import re
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse

import aiohttp
from aiohttp import ClientError, ClientSession, ClientTimeout
from yarl import URL

from .GRConst import OP_CLIENT_ID, OP_CLIENT_SECRET

REDIRECT_URI = "http://localhost/"
_AUTHORIZE_PATH = "/oauth/oauth2/gree/authorize"
_TOKEN_PATH = "/oauth/oauth2/token"
_USERINFO_PATH = "/oauth/oauth2/userinfo"
_LOGIN_PATH = "/oauth/oauth2/gree/tellogin"
_AUTH_PAGE_PATH = "/oauth/oauth2/gree/auth"
_GRANT_TYPE_AUTH_CODE = "authorization_code"
_GRANT_TYPE_REFRESH = "refresh_token"

_REQUEST_TIMEOUT = ClientTimeout(total=10.0)
_REDIRECT_FOLLOW_LIMIT = 10


def _md5(value: str) -> str:
    """Return the lowercase MD5 hex digest of a string."""
    return hashlib.md5(value.encode()).hexdigest()


async def _follow_until_redirect(
    session: ClientSession, url: str, method: str, data: Any = None
) -> str | None:
    """Return an authorization code from a redirect chain."""
    target_host = urlparse(REDIRECT_URI).hostname
    for _ in range(_REDIRECT_FOLLOW_LIMIT):
        if method == "POST":
            async with session.post(url, data=data, allow_redirects=False) as resp:
                status = resp.status
                location = resp.headers.get("Location", "")
        else:
            async with session.get(url, allow_redirects=False) as resp:
                status = resp.status
                location = resp.headers.get("Location", "")

        if status not in (301, 302, 303, 307, 308):
            return None

        next_url = urljoin(url, location)
        parsed = urlparse(next_url)

        if (parsed.hostname or "") == target_host:
            return parse_qs(parsed.query).get("code", [None])[0]

        url = next_url
        method = "GET"
        data = None

    return None


class GreeOAuthError(Exception):
    """Raised when the OAuth2 token/userinfo endpoint fails."""


@dataclass(frozen=True)
class OpenPlatformHost:
    """Regional service configuration."""

    region: str
    host: str
    name: str


# Supported account regions.
_OPENPLATFORM_HOSTS: dict[str, OpenPlatformHost] = {
    "na": OpenPlatformHost("na", "openplatform-na.gree.com", "North America"),
    "sa": OpenPlatformHost("sa", "openplatform-sa.gree.com", "South America"),
    "eu": OpenPlatformHost("eu", "openplatform-eu.gree.com", "Europe"),
    "me": OpenPlatformHost("me", "openplatform-me.gree.com", "Middle East"),
    "au": OpenPlatformHost("au", "openplatform-au.gree.com", "Australia"),
    "hk": OpenPlatformHost("hk", "openplatform-hk.gree.com", "Asia"),
}
_DEFAULT_OP_REGION = "na"


def get_openplatform_host(region: str | None = None) -> OpenPlatformHost:
    """Resolve an open-platform host by region, falling back to the default.

    Args:
        region: The region key the user picked at login, or ``None`` for the
            default.

    Returns:
        The matching :class:`OpenPlatformHost` (default region if unknown).
    """
    if region is None:
        return _OPENPLATFORM_HOSTS[_DEFAULT_OP_REGION]
    return _OPENPLATFORM_HOSTS.get(region, _OPENPLATFORM_HOSTS[_DEFAULT_OP_REGION])


def available_regions() -> list[str]:
    """Return the keys of all configured open-platform regions."""
    return list(_OPENPLATFORM_HOSTS)


@dataclass(frozen=True)
class TokenInfo:
    """Parsed token response (OAuth2 token endpoint, spec §3.5)."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str


@dataclass(frozen=True)
class UserInfo:
    """Parsed user-info response (OAuth2 userInfo endpoint §5)."""

    open_id: str
    name: str
    app_id: str


class GROauthControl:
    """OAuth2 authorization-code client for the Gree open platform."""

    def __init__(self, session: ClientSession, region: str | None = None) -> None:
        """Initialize for a regional open-platform host.

        Args:
            session: HA's shared aiohttp ClientSession
                (``async_get_clientsession``); never construct one here.
            region: The region key the user picked at login. ``None`` → default.
        """
        self._session = session
        self._host = get_openplatform_host(region)

    @property
    def base_url(self) -> str:
        """The ``https://<host>`` base for this region."""
        return f"https://{self._host.host}"

    def authorize_url(self, state: str | None = None) -> str:
        """Build the authorize URL the user opens in a browser.

        Args:
            state: Optional opaque state value echoed back in the redirect;
                recommended to bind the redirect to this session (CSRF).
        """
        params: dict[str, str] = {
            "client_id": OP_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
        }
        if state is not None:
            params["state"] = state
        return f"{self.base_url}{_AUTHORIZE_PATH}?{urlencode(params)}"

    async def capture_code(self, account: str, password: str) -> str:
        """Authenticate the account and return an authorization code."""
        authorize_url = (
            f"{self.base_url}{_AUTHORIZE_PATH}?client_id={OP_CLIENT_ID}"
            f"&response_type=code&redirect_uri={quote(REDIRECT_URI, safe='')}"
        )
        try:
            async with self._session.get(
                authorize_url, timeout=_REQUEST_TIMEOUT, allow_redirects=True
            ) as resp:
                await resp.read()
        except ClientError as err:
            raise GreeOAuthError(f"authorize request failed: {err}") from err

        hashed_password = _md5(_md5(password) + password)
        try:
            async with self._session.post(
                f"{self.base_url}{_LOGIN_PATH}",
                json={"username": account, "password": hashed_password},
                timeout=_REQUEST_TIMEOUT,
            ) as resp:
                tellogin = await resp.json(content_type=None)
        except ClientError as err:
            raise GreeOAuthError(f"tellogin request failed: {err}") from err
        if not isinstance(tellogin, dict) or tellogin.get("code") != 200:
            msg = (
                tellogin.get("message", "Login failed")
                if isinstance(tellogin, dict)
                else "Unexpected tellogin response format"
            )
            raise GreeOAuthError(msg)

        try:
            async with self._session.get(
                f"{self.base_url}{_AUTH_PAGE_PATH}", timeout=_REQUEST_TIMEOUT
            ) as resp:
                auth_body = await resp.text()
        except ClientError as err:
            raise GreeOAuthError(f"auth page request failed: {err}") from err

        auth_inputs: dict[str, str] = {}
        for match in re.finditer(
            r'<input[^>]+name="([^"]*)"[^>]*value="([^"]*)"', auth_body, re.IGNORECASE
        ):
            auth_inputs[match.group(1)] = match.group(2)
        auth_data = auth_inputs or {"SelectApp": "true", "SelectBase": "true"}

        try:
            async with self._create_temp_session() as temp_session:
                code = await _follow_until_redirect(
                    temp_session,
                    f"{self.base_url}{_AUTH_PAGE_PATH}",
                    "POST",
                    auth_data,
                )
        except ClientError as err:
            raise GreeOAuthError(f"auth confirm request failed: {err}") from err
        if not code:
            raise GreeOAuthError(
                "Could not capture authorization code — "
                "redirect chain broken or CAPTCHA required"
            )
        return code

    def _basic_auth_header(self) -> str:
        """Build the OAuth client authorization header."""
        raw = f"{OP_CLIENT_ID}:{OP_CLIENT_SECRET}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    def _create_temp_session(self) -> ClientSession:
        """Create a session that preserves login state across redirects."""
        jar = aiohttp.CookieJar()
        for cookie in self._session.cookie_jar:
            jar.update_cookies(
                {cookie.key: cookie.value},
                URL(f"https://{self._host.host}{cookie.get('path', '/')}"),
            )
        return ClientSession(
            connector=self._session.connector,
            connector_owner=False,
            trust_env=False,
            cookie_jar=jar,
        )

    async def _request_token(self, body: dict[str, str]) -> TokenInfo:
        """Request and parse a token response."""
        url = f"{self.base_url}{_TOKEN_PATH}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self._basic_auth_header(),
        }
        try:
            async with self._session.post(
                url, data=body, headers=headers, timeout=_REQUEST_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    raise GreeOAuthError(f"token endpoint returned HTTP {resp.status}")
                payload = await resp.json()
        except ClientError as err:
            raise GreeOAuthError(f"token endpoint request failed: {err}") from err

        try:
            return TokenInfo(
                access_token=payload["access_token"],
                refresh_token=payload["refresh_token"],
                expires_in=int(payload["expires_in"]),
                token_type=payload["token_type"],
            )
        except (KeyError, ValueError, TypeError) as err:
            # No payload repr: it contains live tokens.
            raise GreeOAuthError("malformed token response") from err

    async def exchange_code(self, code: str) -> TokenInfo:
        """Exchange an authorization code for a token pair."""
        return await self._request_token(
            {
                "grant_type": _GRANT_TYPE_AUTH_CODE,
                "code": code,
                "redirect_uri": REDIRECT_URI,
            }
        )

    async def refresh(self, refresh_token: str) -> TokenInfo:
        """Refresh an expired access token."""
        return await self._request_token(
            {
                "grant_type": _GRANT_TYPE_REFRESH,
                "refresh_token": refresh_token,
            }
        )

    async def user_info(self, access_token: str) -> UserInfo:
        """Return the account identity."""
        url = f"{self.base_url}{_USERINFO_PATH}"
        try:
            async with self._session.post(
                url,
                data={"access_token": access_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=_REQUEST_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    raise GreeOAuthError(f"userinfo returned HTTP {resp.status}")
                payload = await resp.json()
        except ClientError as err:
            raise GreeOAuthError(f"userinfo request failed: {err}") from err

        data = payload.get("data")
        if not isinstance(data, dict):
            # No payload repr: it contains the user's identity.
            raise GreeOAuthError("userinfo returned no data")
        try:
            return UserInfo(
                open_id=data["openId"],
                name=data["name"],
                app_id=data["appId"],
            )
        except (KeyError, TypeError) as err:
            # No data repr: it contains the user's identity.
            raise GreeOAuthError("malformed userinfo data") from err
