"""Gree Plus data coordinator — open-platform standard cloud.

On-demand coordinator (no background polling). State is fetched once at setup
(``async_config_entry_first_refresh``), after each control command, and when the
user triggers a refresh (button / service / ``homeassistant.update_entity``).

Token lifecycle is **request-gated**: before every cloud call, ``_ensure_token``
checks locally whether the access_token is about to expire (<60s) or the
refresh_token is past 150 days, and refreshes first if so. A 101 from the cloud
acts as a safety net: force one refresh + retry.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_ISSUED_AT,
    CONF_REGION,
    DOMAIN,
)
from .gree_plus_protocol import (
    Device,
    DevState,
    GreeStandardCloudError,
    GROauthControl,
    GRStandardCloud,
    TokenInfo,
)

_LOGGER = logging.getLogger(__name__)

# Refresh the access_token when less than this many seconds remain.
_ACCESS_TOKEN_REFRESH_MARGIN = timedelta(seconds=60)
# Rotate the refresh_token (and access_token) before this age.
_REFRESH_TOKEN_ROTATE_AGE = timedelta(days=150)

AUTH_ERROR_CODES = {101}  # token invalid/expired → refresh + retry
OFFLINE_ERROR_CODES = {601, 602}  # device offline/timeout → mark unavailable
# "Account has no devices" — a valid empty state, not an error. Treat as an
# empty device list so the stale-device cleanup removes everything the previous
# account (or a now-empty account) left behind.
NO_DEVICES_ERROR_CODES = {121}

# Store version for learned per-device capabilities (unsupported fan modes).
# v3 buckets rejections per HVAC mode — fan capability is mode-dependent, so
# a mode tried in one mode must not prune it in the others. Pre-v3 entries
# land in the "all" bucket (applied to every mode).
_FAN_CAPABILITIES_STORE_VERSION = 3
_FAN_MODE_BUCKET_ALL = "all"


def _migrate_fan_capabilities_store(
    old_version: int, data: dict[str, Any]
) -> dict[str, Any]:
    """Migrate older store shapes to the v3 per-mode-bucket shape."""
    if not data:
        return data
    # v1 keeps {device_id: [modes]} at the top level; v2+ wraps it.
    flat = data.get("unsupported_fan_modes", data)
    if flat and any(isinstance(v, dict) for v in flat.values()):
        return {"unsupported_fan_modes": flat}  # already v3
    return {
        "unsupported_fan_modes": {
            dev: {_FAN_MODE_BUCKET_ALL: list(modes)} for dev, modes in flat.items()
        }
    }


class FanCapabilitiesStore(Store[dict[str, Any]]):
    """Store for learned per-device capabilities, with shape migration."""

    @override
    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Upgrade pre-v3 fan-mode shapes on read."""
        return _migrate_fan_capabilities_store(old_major_version, old_data)


@dataclass
class DeviceData:
    """A device plus its last known state, held by the coordinator.

    ``online`` merges the deviceList flag with the (fresher) query result:
    the query value wins when present.
    """

    device: Device
    state: DevState | None
    online: bool | None = None

    @property
    def is_online(self) -> bool:
        """Effective online flag — query result first, deviceList fallback."""
        if self.online is not None:
            return self.online
        return self.device.online


class GRCoordinator(DataUpdateCoordinator[dict[str, DeviceData]]):
    """Coordinates standard-cloud device data for a config entry."""

    config_entry: ConfigEntry[Any]

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry[Any]) -> None:
        """Initialize the coordinator from the config entry's data."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
        )
        self.config_entry = config_entry
        self._oauth = GROauthControl(
            session=async_get_clientsession(hass),
            region=config_entry.data.get(CONF_REGION),
        )
        self._access_token = config_entry.data[CONF_ACCESS_TOKEN]
        self._refresh_token = config_entry.data[CONF_REFRESH_TOKEN]
        self._access_token_expires_at = _parse_dt(
            config_entry.data.get(CONF_ACCESS_TOKEN_EXPIRES_AT)
        )
        self._refresh_token_issued_at = _parse_dt(
            config_entry.data.get(CONF_REFRESH_TOKEN_ISSUED_AT)
        )
        self._cloud = GRStandardCloud(
            session=async_get_clientsession(hass),
            access_token=self._access_token,
            region=config_entry.data.get(CONF_REGION),
        )
        # Learned per-device capabilities, persisted: fan modes each device
        # ignored (snapped away), bucketed by HVAC mode. "all" holds
        # mode-agnostic rejections and migrated pre-v3 learnings.
        self._fan_capabilities_store: FanCapabilitiesStore = FanCapabilitiesStore(
            hass,
            _FAN_CAPABILITIES_STORE_VERSION,
            f"{DOMAIN}.fan_capabilities.{config_entry.entry_id}",
        )
        self._unsupported_fan_modes: dict[str, dict[str, set[str]]] = {}

    async def async_load_fan_capabilities(self) -> None:
        """Load the learned per-device capabilities."""
        if (data := await self._fan_capabilities_store.async_load()) is None:
            return
        self._unsupported_fan_modes = {
            dev: {bucket: set(modes) for bucket, modes in buckets.items()}
            for dev, buckets in data.get("unsupported_fan_modes", {}).items()
        }

    def _save_fan_capabilities(self) -> None:
        """Schedule a save of the learned-capability snapshot."""
        self._fan_capabilities_store.async_delay_save(
            lambda: {
                "unsupported_fan_modes": {
                    dev: {bucket: sorted(modes) for bucket, modes in buckets.items()}
                    for dev, buckets in self._unsupported_fan_modes.items()
                }
            }
        )

    def unsupported_fan_modes(
        self, device_id: str, hvac_mode: str | None = None
    ) -> set[str]:
        """Fan modes this device ignored for the given HVAC mode.

        Includes the mode-agnostic "all" bucket; empty when all supported.
        """
        buckets = self._unsupported_fan_modes.get(device_id, {})
        return buckets.get(_FAN_MODE_BUCKET_ALL, set()) | buckets.get(
            hvac_mode or "", set()
        )

    def record_unsupported_fan_mode(
        self, device_id: str, mode: str, hvac_mode: str | None = None
    ) -> None:
        """Remember a fan mode the device snapped away from; persisted."""
        buckets = self._unsupported_fan_modes.setdefault(device_id, {})
        bucket = buckets.setdefault(hvac_mode or _FAN_MODE_BUCKET_ALL, set())
        if mode in bucket:
            return
        bucket.add(mode)
        self._save_fan_capabilities()

    async def _ensure_token(self) -> None:
        """Refresh in place if a token rotation condition is met.

        Refreshes when the access_token is near-expiry or the refresh_token is
        past its rotation age. No-op otherwise.
        """
        now = dt_util.utcnow()
        access_expired = (
            self._access_token_expires_at is None
            or self._access_token_expires_at - now <= _ACCESS_TOKEN_REFRESH_MARGIN
        )
        refresh_stale = (
            self._refresh_token_issued_at is not None
            and now - self._refresh_token_issued_at >= _REFRESH_TOKEN_ROTATE_AGE
        )
        if not (access_expired or refresh_stale):
            return
        await self._do_refresh()

    async def _do_refresh(self) -> None:
        """Exchange the refresh_token for a new token pair and persist it."""
        token = await self._oauth.refresh(self._refresh_token)
        self._apply_tokens(token)

    def _apply_tokens(self, token: TokenInfo) -> None:
        """Apply refreshed tokens to memory + the config entry."""
        now = dt_util.utcnow()
        self._access_token = token.access_token
        self._refresh_token = token.refresh_token
        self._access_token_expires_at = now + timedelta(seconds=token.expires_in)
        self._refresh_token_issued_at = now
        self._cloud.access_token = token.access_token
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                CONF_ACCESS_TOKEN: token.access_token,
                CONF_REFRESH_TOKEN: token.refresh_token,
                CONF_ACCESS_TOKEN_EXPIRES_AT: self._access_token_expires_at.isoformat(),
                CONF_REFRESH_TOKEN_ISSUED_AT: self._refresh_token_issued_at.isoformat(),
            },
        )

    async def _call[T](self, func: Callable[..., Awaitable[T]], *args: Any) -> T:
        """Run a cloud call with token gate + 101 safety-net retry."""
        await self._ensure_token()
        try:
            return await func(*args)
        except GreeStandardCloudError as err:
            if err.code not in AUTH_ERROR_CODES:
                raise
            # Auth failed despite local checks (clock skew) → force refresh once.
            _LOGGER.warning("Auth error %s, refreshing token and retrying", err.code)
            try:
                await self._do_refresh()
            except Exception:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "token_refresh_failed",
                    is_fixable=True,
                    is_persistent=True,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="token_refresh_failed",
                    data={"entry_id": self.config_entry.entry_id},
                )
                raise
            return await func(*args)

    @override
    async def _async_update_data(self) -> dict[str, DeviceData]:
        """Fetch device list + state, removing stale devices (on-demand)."""
        try:
            devices = await self._call(self._cloud.get_devices)
        except GreeStandardCloudError as err:
            # "Account has no devices" is a valid empty state, not an error:
            # treat it as an empty list so the stale-device cleanup wipes the
            # devices left by a previous account (or a now-empty account).
            if err.code not in NO_DEVICES_ERROR_CODES:
                raise
            devices = []
        device_ids = [d.id for d in devices]
        cur_ids = set(device_ids)

        # Remove stale devices: query the device registry for ALL devices owned
        # by this config entry, and remove any that are no longer in the cloud.
        # This also handles account switches via reconfigure (self.data is None
        # after reload, so we can't rely on it alone).
        dev_reg = dr.async_get(self.hass)
        entry_devices = dr.async_entries_for_config_entry(
            dev_reg, self.config_entry.entry_id
        )
        known_ids = {
            next(iter(de.identifiers))[1] for de in entry_devices if de.identifiers
        }
        for stale_id in known_ids - cur_ids:
            if (
                device_entry := dev_reg.async_get_device(
                    identifiers={(DOMAIN, stale_id)}
                )
            ) is not None:
                dev_reg.async_remove_device(device_entry.id)

        states = await self._call(self._cloud.query, device_ids) if device_ids else {}

        # Warn if the account has no compatible devices.
        if not devices:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "no_devices",
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="no_devices",
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, "no_devices")

        data: dict[str, DeviceData] = {}
        for d in devices:
            qr = states.get(d.id)
            state = qr.state if qr else None
            data[d.id] = DeviceData(
                device=d,
                state=state,
                online=qr.online if qr is not None else None,
            )
        return data

    async def async_send_command(self, device_id: str, cmd: dict[str, Any]) -> None:
        """Send a control command, then background-query to refresh state.

        The control API only returns ``done/error``, not the new state.
        We schedule a background re-query so the UI isn't blocked waiting.
        """
        try:
            await self._call(self._cloud.control, device_id, cmd)
        except GreeStandardCloudError as err:
            if err.code in OFFLINE_ERROR_CODES:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="device_offline",
                    translation_placeholders={"message": str(err)},
                ) from err
            raise

        async def _re_query():
            """Background: re-query after device syncs state to cloud."""
            await asyncio.sleep(1)
            try:
                await self.async_query_device(device_id)
            except GreeStandardCloudError:
                return

        self.hass.async_create_background_task(_re_query(), "gree_plus re-query")

    async def async_query_device(self, device_id: str) -> None:
        """Query one device now and update the cache (post-command checks)."""
        states = await self._call(self._cloud.query, [device_id])
        if self.data is not None and device_id in self.data:
            qr = states.get(device_id)
            state = qr.state if qr else None
            self.data[device_id] = DeviceData(
                device=self.data[device_id].device,
                state=state,
                online=qr.online if qr is not None else None,
            )
        self.async_update_listeners()


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO timestamp string into a timezone-aware datetime."""
    if not value:
        return None
    return dt_util.parse_datetime(value)
