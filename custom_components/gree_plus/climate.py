"""Climate entities for the gree_plus standard-cloud integration.

Maps the standard-cloud device JSON model onto HA's ClimateEntity:

- ``pow`` (on/off) ↔ HVACMode.OFF / current mode
- ``mode`` (cool/heat/dry/fan/auto) ↔ HVACMode
- ``temperature`` sub-object ↔ target_temperature (``addPointFiveValue=1``
  appends ".5" to the integer; Celsius only — Fahrenheit has no decimal part)
- ``temUnit`` (C/F) ↔ values are converted to the HA unit system at the
  boundary (``temperature_unit`` reports the system unit)
- ``speed`` (s1..s6/auto) ↔ fan_mode (filtered by ``detail.speedList``)
- ``quiet``/``strong`` ↔ extra fan modes; they replace the active speed on
  the device, so a normal speed sends ``quiet/strong=off``. strong is
  omitted when the graded scale tops out at s6 (translated as "Strong"),
  which would read as a duplicate "max air" option
"""

from collections.abc import Callable
from typing import Any, override

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.unit_conversion import TemperatureConverter

from . import GreePlusConfigEntry
from .const import DOMAIN
from .coordinator import GRCoordinator
from .entity import GreePlusEntity
from .gree_plus_protocol import Device, DevState, GreeStandardCloudError

# Gree mode string → HA HVACMode.
_MODE_TO_HVAC: dict[str, HVACMode] = {
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "dry": HVACMode.DRY,
    "fan": HVACMode.FAN_ONLY,
    "auto": HVACMode.AUTO,
}
_HVAC_TO_MODE: dict[HVACMode, str] = {v: k for k, v in _MODE_TO_HVAC.items()}

# quiet/strong are separate protocol fields, not speed values — but on the
# device they *replace* the active fan speed, so they are exposed as extra
# fan modes. strong is omitted when the graded scale already tops out at s6
# (translated as "Strong") — exposing both read as two identical "max air"
# options.
# Selecting a normal speed must explicitly turn both off.
_FAN_MODE_QUIET = "quiet"
_FAN_MODE_STRONG = "strong"

# Protocol unit letters ("C"/"F") → HA unit constants for conversion.
_DEVICE_UNIT_TO_HA = {
    "C": UnitOfTemperature.CELSIUS,
    "F": UnitOfTemperature.FAHRENHEIT,
}

# The cloud accepts fan modes a device cannot do and silently snaps them to
# the nearest supported one. After each fan command we re-check once; a mode
# the device talked back out of is remembered (persisted per device+mode)
# and pruned from fan_modes. Delay covers the device's state sync latency.
_FAN_VERIFY_DELAY = 4.0

PARALLEL_UPDATES = 1


def _build_temperature_cmd(
    target: float,
    unit: str,
    *,
    channel: str | None,
) -> dict[str, Any]:
    """Build the temperature sub-object for the device's fractional channel.

    ``channel`` is how the device accepts 0.5° control: ``"five"`` uses
    ``addPointFiveValue=1``; ``"one"`` uses ``addPointOneValue=5`` (sending
    ap5=1 to those is rejected by the cloud); ``None`` means integer-only.
    Only Celsius has a fractional part — Fahrenheit is integer-only.
    """
    integer = int(target)
    half = unit == "C" and channel is not None and (target - integer) >= 0.5
    cmd: dict[str, Any] = {
        "temperature": integer,
        "addPointFiveValue": int(half and channel == "five"),
        "temUnit": unit,
    }
    if channel == "one":
        cmd["addPointOneValue"] = 5 if half else 0
    return cmd


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreePlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create climate entities for all ac/multiAc devices.

    Devices discovered later (e.g. added to the Gree account then a refresh is
    triggered) get their entities added via the coordinator listener.
    """
    coordinator = entry.runtime_data
    known_devices: set[str] = set()

    def _check_device() -> None:
        """Add entities for devices that appeared since the last update."""
        if coordinator.data is None:
            return
        new_devices = set(coordinator.data) - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                GreeClimateEntity(coordinator, coordinator.data[device_id].device)
                for device_id in new_devices
            )

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class GreeClimateEntity(GreePlusEntity, ClimateEntity):
    """A Gree standard-cloud climate device."""

    # Fan mode values stay as protocol strings (s1..s6 / auto / quiet /
    # strong); the frontend translates them via
    # entity.climate.air_conditioner.state_attributes.fan_mode.state.
    _attr_translation_key = "air_conditioner"

    def __init__(self, coordinator: GRCoordinator, device: Device) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, device)
        # Base fan modes from the device's advertised speedList (fallback to
        # sane defaults when the device doesn't report one), plus the quiet
        # special mode — and strong except when the graded scale already
        # tops out at s6 (translated as "Strong"), which would duplicate it.
        # Unsupported entries are pruned dynamically in :attr:`fan_modes`
        # as the device rejects them.
        if device.detail.speed_list:
            speeds = list(device.detail.speed_list)
        elif device.type == "multiAc":
            speeds = ["s1", "s2", "s3", "s4", "s5", "s6", "auto"]
        else:
            speeds = ["s1", "s2", "s3", "s4", "s5", "auto"]
        self._base_fan_modes = [*speeds, _FAN_MODE_QUIET]
        if "s6" not in speeds:
            self._base_fan_modes.append(_FAN_MODE_STRONG)
        self._pending_fan_mode: str | None = None
        self._cancel_fan_verify: Callable[[], None] | None = None

    @override
    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Offer only the controls that work in the current mode.

        Temperature is always offered (the setpoint sticks in every mode;
        auto-only gating lives in async_set_temperature). Dry mode forces
        low fan, so FAN_MODE is dropped there.
        """
        features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
        )
        if self.hvac_mode is HVACMode.DRY:
            features &= ~ClimateEntityFeature.FAN_MODE
        return features

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending fan-mode verification."""
        if self._cancel_fan_verify is not None:
            self._cancel_fan_verify()
            self._cancel_fan_verify = None

    @property
    @override
    def fan_modes(self) -> list[str]:
        """Base modes minus the ones this device ignored for this HVAC mode.

        The cloud never advertises per-device fan capabilities, so unsupported
        modes are learned the first time a user picks one and the device snaps
        to a different speed. Fan capability is HVAC-mode-dependent, so the
        learned rejections are bucketed per HVAC mode. The mode the device is
        currently in is always shown, even if it was pruned earlier (e.g. set
        from the vendor app).
        """
        unsupported = self.coordinator.unsupported_fan_modes(
            self.device.id, self.hvac_mode.value
        )
        modes = [m for m in self._base_fan_modes if m not in unsupported]
        if (current := self.fan_mode) and current not in modes:
            modes.append(current)
        return modes

    @property
    def _fraction_channel(self) -> str | None:
        """How the device accepts 0.5° *control*, per its detail flags.

        supportPointFive → ``"five"``; supportPointOne → ``"one"`` (those
        devices reject the ap5 encoding); neither → integer-only. The 0.5
        flag in query state is an output echo only — display always follows
        the reported state regardless of this channel.
        """
        detail = self.device.detail
        if detail.support_point_five:
            return "five"
        if detail.support_point_one:
            return "one"
        return None

    @override
    @property
    def target_temperature_step(self) -> float:
        """Step in the reported (system) unit.

        0.5 only when both the device and the reported unit are Celsius and
        the device has a fractional channel. Fahrenheit and unit-mismatched
        cases step by 1.0 — the target is snapped to the device's own step
        after conversion in async_set_temperature.
        """
        if (
            self._device_unit == "C"
            and self.temperature_unit == UnitOfTemperature.CELSIUS
            and self._fraction_channel is not None
        ):
            return 0.5
        return 1.0

    @property
    def _state(self) -> DevState | None:
        """The device's last known state from the coordinator cache."""
        if self.coordinator.data is None:
            return None
        entry = self.coordinator.data.get(self.device.id)
        return entry.state if entry else None

    @property
    def _device_unit(self) -> str:
        """The device's native temperature unit."""
        if self._state and self._state.tem_unit == "F":
            return "F"
        return "C"

    @override
    @property
    def temperature_unit(self) -> str:
        """Report in the HA unit system.

        Device values are converted at the integration boundary, so display
        and inputs always follow the user's HA unit setting and HA's built-in
        service-call conversion becomes a no-op.
        """
        return self.hass.config.units.temperature_unit

    @override
    @property
    def min_temp(self) -> float:
        """Protocol range: 16~30 °C / 61~86 °F, in the reported unit."""
        native = 61.0 if self._device_unit == "F" else 16.0
        return TemperatureConverter.convert(
            native, _DEVICE_UNIT_TO_HA[self._device_unit], self.temperature_unit
        )

    @override
    @property
    def max_temp(self) -> float:
        """Protocol range: 16~30 °C / 61~86 °F, in the reported unit."""
        native = 86.0 if self._device_unit == "F" else 30.0
        return TemperatureConverter.convert(
            native, _DEVICE_UNIT_TO_HA[self._device_unit], self.temperature_unit
        )

    @property
    def _auto_temp_allowed(self) -> bool:
        """Whether the device permits setting a temperature in auto mode.

        Opt-in per device: allowed only with an explicit positive flag.
        ac-family devices report autoModelSetTemp (0/1); commercial multiAc
        units instead report autoSetTempEn ("on"/"off", not in the protocol
        doc but present in server state). Missing/0/off all deny. Devices
        that deny report ``temperature: 0`` in auto — not a real setpoint.
        """
        if self._state is None:
            return False
        raw = self._state.raw
        return str(raw.get("autoModelSetTemp", "0")) == "1" or (
            str(raw.get("autoSetTempEn", "off")).lower() == "on"
        )

    @override
    @property
    def target_temperature(self) -> float | None:
        """The setpoint in the reported unit (device +0.5 already applied).

        Hidden in auto mode without the device's opt-in flag — those devices
        report ``temperature: 0`` there and the frontend would show a bogus
        0° setpoint instead of just the mode.
        """
        if self._state is None or self._state.temperature is None:
            return None
        if self.hvac_mode is HVACMode.AUTO and not self._auto_temp_allowed:
            return None
        return TemperatureConverter.convert(
            self._state.temperature,
            _DEVICE_UNIT_TO_HA[self._device_unit],
            self.temperature_unit,
        )

    @override
    @property
    def current_temperature(self) -> float | None:
        """Room temperature (``indoorTem``); hidden when not reported.

        Devices without a temperature sensor report ``0``/empty — show no
        value rather than a bogus 0°.
        """
        if self._state is None:
            return None
        raw = self._state.raw.get("indoorTem")
        if raw is None or raw in ("", 0, "0"):
            return None
        try:
            indoor = float(raw)
        except ValueError, TypeError:
            return None
        if indoor == 0:
            return None
        return TemperatureConverter.convert(
            indoor, _DEVICE_UNIT_TO_HA[self._device_unit], self.temperature_unit
        )

    @override
    @property
    def hvac_mode(self) -> HVACMode:
        """Current mode (OFF when powered off)."""
        state = self._state
        if state is None or state.pow != "on":
            return HVACMode.OFF
        return _MODE_TO_HVAC.get(state.mode, HVACMode.AUTO)

    @override
    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Modes the user can pick, filtered by the device's modeList."""
        mode_list = self.device.detail.mode_list
        modes = [HVACMode.OFF]
        for m in mode_list:
            if (hvac := _MODE_TO_HVAC.get(m)) and hvac not in modes:
                modes.append(hvac)
        if len(modes) == 1:
            modes.extend(
                [
                    HVACMode.COOL,
                    HVACMode.HEAT,
                    HVACMode.AUTO,
                    HVACMode.DRY,
                    HVACMode.FAN_ONLY,
                ]
            )
        return modes

    @override
    @property
    def hvac_action(self) -> HVACAction | None:
        """Current running action.

        The protocol exposes no compressor state, so the action is derived
        from the mode. AUTO has no meaningful guess — reporting IDLE there
        misleads while the unit is running, so it maps to None (no action
        shown).
        """
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return {
            HVACMode.COOL: HVACAction.COOLING,
            HVACMode.HEAT: HVACAction.HEATING,
            HVACMode.DRY: HVACAction.DRYING,
            HVACMode.FAN_ONLY: HVACAction.FAN,
        }.get(self.hvac_mode)

    @override
    @property
    def fan_mode(self) -> str | None:
        """Current fan speed.

        quiet/strong replace the device's speed while active, so they win
        over the plain speed value. ``quiet=auto`` counts as not-quiet.
        """
        if self._state is None:
            return None
        raw = self._state.raw
        if raw.get("strong") == "on":
            return _FAN_MODE_STRONG
        if raw.get("quiet") == "on":
            return _FAN_MODE_QUIET
        return self._state.speed

    @override
    @property
    def available(self) -> bool:
        """Unavailable when the device reports offline.

        Uses the query-reported flag when available (fresher than deviceList).
        """
        if (
            self.coordinator.data is None
            or (device_data := self.coordinator.data.get(self.device.id)) is None
            or not device_data.is_online
        ):
            return False
        return super().available

    def _cmd(self, **fields: Any) -> dict[str, dict[str, Any]]:
        """Wrap command fields in the device-type key (``ac`` / ``multiAc``)."""
        return {self.device.type: fields}

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the operating mode (or turn off)."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_send_command(
                self.device.id, self._cmd(pow="off")
            )
            return
        # offSetMode constraint: device must be off to switch mode.
        if (
            self.device.detail.off_set_mode
            and self._state is not None
            and self._state.pow == "on"
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_before_mode_change",
            )
        await self.coordinator.async_send_command(
            self.device.id,
            self._cmd(pow="on", mode=_HVAC_TO_MODE.get(hvac_mode, "auto")),
        )

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature.

        The incoming target is in the reported (system) unit; it is converted
        to the device's native unit and snapped to the device's own step
        before encoding — fractional inputs (unit conversion, raw service
        calls) would otherwise encode decimal fields the device rejects. In
        auto mode the device must report ``autoModelSetTemp=1`` to allow
        adjustment.
        """
        if ATTR_TEMPERATURE not in kwargs:
            return
        if self.hvac_mode == HVACMode.AUTO and not self._auto_temp_allowed:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auto_mode_no_temperature",
            )
        unit = self._device_unit
        native_min, native_max = (61.0, 86.0) if unit == "F" else (16.0, 30.0)
        step = 0.5 if unit == "C" and self._fraction_channel is not None else 1.0
        target = TemperatureConverter.convert(
            float(kwargs[ATTR_TEMPERATURE]),
            self.temperature_unit,
            _DEVICE_UNIT_TO_HA[unit],
        )
        target = round(round(target / step) * step, 1)
        target = min(max(target, native_min), native_max)
        state = self._state
        # No-op filter: at min/max the more-info dialog re-sends the current
        # setpoint (the dashboard card clamps client-side and sends nothing),
        # which made the unit ACK-beep inconsistently between the two pages.
        if (
            state is not None
            and state.temperature is not None
            and abs(state.temperature - target) < 0.05
        ):
            return
        await self.coordinator.async_send_command(
            self.device.id,
            self._cmd(
                temperature=_build_temperature_cmd(
                    target,
                    unit,
                    channel=self._fraction_channel,
                )
            ),
        )

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed, translating quiet/strong to their protocol fields."""
        if fan_mode == _FAN_MODE_QUIET:
            fields: dict[str, Any] = {"quiet": "on", "strong": "off"}
        elif fan_mode == _FAN_MODE_STRONG:
            fields = {"quiet": "off", "strong": "on"}
        else:
            # A normal speed must clear the special modes to take effect.
            fields = {
                "speed": fan_mode,
                "quiet": "off",
                "strong": "off",
            }
        self._pending_fan_mode = fan_mode
        await self.coordinator.async_send_command(self.device.id, self._cmd(**fields))
        self._schedule_fan_verify()

    def _schedule_fan_verify(self) -> None:
        """Schedule the one-shot post-command fan-mode verification."""
        if self._cancel_fan_verify is not None:
            self._cancel_fan_verify()
        self._cancel_fan_verify = async_call_later(
            self.hass, _FAN_VERIFY_DELAY, self._async_verify_fan_mode
        )

    async def _async_verify_fan_mode(self, now: Any) -> None:
        """Prune a fan mode the device snapped away from.

        The cloud accepts unsupported modes and the device silently lands on
        the nearest supported one. Re-query once before condemning — the
        coordinator's post-command re-query may have raced the device.
        """
        self._cancel_fan_verify = None
        requested = self._pending_fan_mode
        self._pending_fan_mode = None
        if requested is None or self._state is None:
            return
        if self._fan_mode_accepted(requested):
            return
        try:
            await self.coordinator.async_query_device(self.device.id)
        except GreeStandardCloudError:
            return
        if self._state is None or self._fan_mode_accepted(requested):
            return
        self.coordinator.record_unsupported_fan_mode(
            self.device.id, requested, self.hvac_mode.value
        )
        self.async_write_ha_state()

    def _fan_mode_accepted(self, requested: str) -> bool:
        """Whether the last known state reflects the requested fan mode."""
        if self._state is None:
            return False
        raw = self._state.raw
        if requested == _FAN_MODE_QUIET:
            return raw.get("quiet") == "on"
        if requested == _FAN_MODE_STRONG:
            return raw.get("strong") == "on"
        return self._state.speed == requested

    @override
    async def async_turn_on(self) -> None:
        """Turn the device on."""
        await self.coordinator.async_send_command(self.device.id, self._cmd(pow="on"))

    @override
    async def async_turn_off(self) -> None:
        """Turn the device off."""
        await self.coordinator.async_send_command(self.device.id, self._cmd(pow="off"))
