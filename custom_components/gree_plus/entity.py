"""Base entity for the gree_plus integration."""

from typing import override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GRCoordinator
from .gree_plus_protocol import Device


class GreePlusEntity(CoordinatorEntity[GRCoordinator]):
    """Base entity backed by a standard-cloud device."""

    _attr_has_entity_name = True

    @override
    def __init__(self, coordinator: GRCoordinator, device: Device) -> None:
        """Initialize the entity.

        Standard cloud identifies devices by ``id``. Device info comes from the
        deviceList response (name / model / type).
        """
        super().__init__(coordinator)
        self.device = device
        self._attr_unique_id = f"{device.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            manufacturer="Gree",
            model=device.detail.model or device.detail.dtype or device.type,
            name=device.name,
        )
