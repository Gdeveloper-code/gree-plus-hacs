"""Config flow for the gree_plus integration (OAuth2 authorization code).

Flow:
1. user — pick region + enter Gree account credentials (username/password).
   The integration simulates the browser login server-side and captures the
   authorization ``code`` from the redirect chain.
2. exchange — trade the captured code for tokens and fetch user identity
   (userInfo).
3. create the config entry with access_token / refresh_token / open_id / region.

Reauthentication is triggered when the refresh_token itself expires (>180 days
unused).
"""

from collections.abc import Mapping
from datetime import timedelta
import logging
import secrets
from typing import Any, override
from urllib.parse import parse_qs, urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.util.dt as dt_util

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_EXPIRES_AT,
    CONF_NAME,
    CONF_OPEN_ID,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_ISSUED_AT,
    CONF_REGION,
    DOMAIN,
)
from .gree_plus_protocol import (
    GreeOAuthError,
    GROauthControl,
    OAuthInteractionRequired,
    available_regions,
    get_openplatform_host,
)

_LOGGER = logging.getLogger(__name__)
_MAX_REDIRECT_LENGTH = 4096


def _validated_authorization_code(value: str, expected_state: str | None) -> str | None:
    """Return a code only from the exact redirect issued for this flow."""
    if len(value) > _MAX_REDIRECT_LENGTH:
        return None
    try:
        redirect = urlparse(value)
        port = redirect.port
    except ValueError:
        return None
    query = parse_qs(redirect.query, keep_blank_values=True)
    codes = query.get("code", [])
    states = query.get("state", [])
    if (
        redirect.scheme != "http"
        or redirect.hostname != "localhost"
        or port is not None
        or redirect.path not in ("", "/")
        or redirect.params
        or redirect.fragment
        or redirect.username is not None
        or redirect.password is not None
        or len(codes) != 1
        or not codes[0]
        or states != [expected_state]
    ):
        return None
    return codes[0]


class GreePlusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for gree_plus via OAuth2 authorization code."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._region: str = available_regions()[0]
        self._completion_step = "user"
        self._authorization_state: str | None = None

    def _login(self) -> GROauthControl:
        """Build an OAuth client for the selected region."""
        return GROauthControl(
            session=async_get_clientsession(self.hass),
            region=self._region,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: pick region + enter credentials, server-side captures code."""
        self._completion_step = "user"
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            self._region = user_input[CONF_REGION]
            account = user_input["account"].strip()
            password = user_input["password"]
            if not account or not password:
                errors["base"] = "missing_credentials"
            else:
                oauth = self._login()
                try:
                    code = await oauth.capture_code(account, password)
                except OAuthInteractionRequired:
                    self._authorization_state = secrets.token_urlsafe(24)
                    return await self.async_step_verification()
                except GreeOAuthError as err:
                    errors["base"] = "login_failed"
                    placeholders["message"] = str(err)
                else:
                    return await self.async_step_exchange(code)

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_schema(),
            errors=errors,
            description_placeholders=placeholders,
        )

    def _user_schema(self) -> vol.Schema:
        """Build the user-step form schema."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_REGION, default=self._region
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=r, label=get_openplatform_host(r).name
                            )
                            for r in available_regions()
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required("account"): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=False)
                ),
                vol.Required("password"): selector.TextSelector(
                    selector.TextSelectorConfig(
                        multiline=False, type=selector.TextSelectorType.PASSWORD
                    )
                ),
            }
        )

    async def async_step_verification(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Complete a login that requires browser interaction."""
        errors: dict[str, str] = {}
        if user_input is not None:
            code = _validated_authorization_code(
                user_input["redirect_url"].strip(), self._authorization_state
            )
            if code is None:
                errors["base"] = "invalid_redirect"
            else:
                try:
                    title, data = await self._exchange_and_build(code)
                except GreeOAuthError:
                    errors["base"] = "invalid_code"
                else:
                    return await self._async_complete(title, data)

        if self._authorization_state is None:
            self._authorization_state = secrets.token_urlsafe(24)
        return self.async_show_form(
            step_id="verification",
            data_schema=vol.Schema(
                {
                    vol.Required("redirect_url"): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=False)
                    )
                }
            ),
            errors=errors,
            description_placeholders={
                "authorize_url": self._login().authorize_url(
                    state=self._authorization_state
                )
            },
        )

    async def async_step_exchange(self, code: str) -> ConfigFlowResult:
        """Step 2: exchange the code for tokens + fetch userInfo, then create."""
        try:
            title, data = await self._exchange_and_build(code)
        except GreeOAuthError as err:
            _LOGGER.error("Exchange/userInfo failed: %s", err)
            return self.async_show_form(
                step_id="user",
                data_schema=self._user_schema(),
                errors={"base": "invalid_code"},
            )

        return await self._async_complete(title, data)

    async def _async_complete(
        self, title: str, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create or update the config entry for the active flow."""
        unique_id = f"{DOMAIN}_{data[CONF_OPEN_ID]}"
        if self._completion_step == "reauth_confirm":
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data=data,
                unique_id=unique_id,
                title=title,
            )
        if self._completion_step == "reconfigure":
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data=data,
                unique_id=unique_id,
                title=title,
            )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)

    async def _exchange_and_build(self, code: str) -> tuple[str, dict[str, Any]]:
        """Exchange code → tokens + userInfo → return (title, entry_data)."""
        oauth = self._login()
        token = await oauth.exchange_code(code)
        user = await oauth.user_info(token.access_token)
        now = dt_util.utcnow()
        return (
            f"Gree Plus - {user.name}",
            {
                CONF_ACCESS_TOKEN: token.access_token,
                CONF_REFRESH_TOKEN: token.refresh_token,
                CONF_ACCESS_TOKEN_EXPIRES_AT: (
                    now + timedelta(seconds=token.expires_in)
                ).isoformat(),
                CONF_REFRESH_TOKEN_ISSUED_AT: now.isoformat(),
                CONF_OPEN_ID: user.open_id,
                CONF_NAME: user.name,
                CONF_REGION: self._region,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger reauthentication when the refresh_token expires."""
        self._completion_step = "reauth_confirm"
        self._region = entry_data.get(CONF_REGION, available_regions()[0])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to re-authorize."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self._user_schema(),
            )
        account = user_input["account"].strip()
        password = user_input["password"]
        if not account or not password:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self._user_schema(),
                errors={"base": "missing_credentials"},
            )
        oauth = self._login()
        try:
            code = await oauth.capture_code(account, password)
            title, data = await self._exchange_and_build(code)
        except OAuthInteractionRequired:
            self._authorization_state = secrets.token_urlsafe(24)
            return await self.async_step_verification()
        except GreeOAuthError as err:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self._user_schema(),
                errors={"base": "login_failed"},
                description_placeholders={"message": str(err)},
            )
        return await self._async_complete(title, data)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to change region / credentials without removing."""
        self._completion_step = "reconfigure"
        existing = self._get_reconfigure_entry().data
        self._region = existing.get(CONF_REGION, available_regions()[0])

        if user_input is not None:
            self._region = user_input[CONF_REGION]
            account = user_input["account"].strip()
            password = user_input["password"]
            if not account or not password:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._user_schema(),
                    errors={"base": "missing_credentials"},
                )
            oauth = self._login()
            try:
                code = await oauth.capture_code(account, password)
                title, data = await self._exchange_and_build(code)
            except OAuthInteractionRequired:
                self._authorization_state = secrets.token_urlsafe(24)
                return await self.async_step_verification()
            except GreeOAuthError as err:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._user_schema(),
                    errors={"base": "login_failed"},
                    description_placeholders={"message": str(err)},
                )
            return await self._async_complete(title, data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._user_schema(),
        )
