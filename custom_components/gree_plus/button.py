"""Refresh button for the gree_plus integration."""

import logging
from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GreePlusConfigEntry
from .coordinator import GRCoordinator
from .entity import GreePlusEntity
from .gree_plus_protocol import Device

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreePlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a per-device refresh button, including for devices added later."""
    coordinator = entry.runtime_data
    known_devices: set[str] = set()

    def _check_device() -> None:
        """Add a refresh button for devices that appeared since the last update."""
        if coordinator.data is None:
            return
        new_devices = set(coordinator.data) - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                GreeRefreshButton(coordinator, coordinator.data[device_id].device)
                for device_id in new_devices
            )

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class GreeRefreshButton(GreePlusEntity, ButtonEntity):
    """Button to force a state refresh for a device."""

    _attr_translation_key = "refresh"

    def __init__(self, coordinator: GRCoordinator, device: Device) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.id}_refresh"

    @override
    async def async_press(self) -> None:
        """Refresh on a manual press; silently ignore automated presses.

        The button domain routes presses through the entity service call
        path, which sets the live call context on this entity first. A press
        by a logged-in user in the UI carries a user_id and no parent_id;
        automation/script/scene chains carry no user_id and/or a parent_id.
        Automated presses are dropped (debug log, no error) so the on-demand
        integration cannot be turned into a poller by a looping automation —
        device control calls are unaffected.
        """
        context = self._context
        if context is None or context.user_id is None or context.parent_id is not None:
            _LOGGER.debug(
                "Ignoring non-manual refresh press for %s (automation/script/scene)",
                self.device.id,
            )
            return
        await self.coordinator.async_request_refresh()
