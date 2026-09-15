"""The gree_plus integration — open-platform standard cloud.

Sets up the on-demand coordinator for a config entry and forwards the climate
and button platforms. The integration registers no custom services: device
state is refreshed per device via the refresh button entity or the built-in
``homeassistant.update_entity`` service (``CoordinatorEntity.async_update``
forwards to ``coordinator.async_request_refresh``).
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .coordinator import GRCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.CLIMATE]

type GreePlusConfigEntry = ConfigEntry[GRCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: GreePlusConfigEntry) -> bool:
    """Set up gree_plus from a config entry.

    Creates the coordinator, performs the initial on-demand device/state fetch
    (so entities have state immediately after setup), and forwards the platforms.
    """
    coordinator = GRCoordinator(hass, entry)
    await coordinator.async_load_fan_capabilities()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async def _on_core_config_update(event: Event) -> None:
        """Rewrite entity state when core config (e.g. unit system) changes.

        Temperatures are rendered live in the HA unit system, but without
        polling nothing rewrites the state machine after the switch — values
        stayed stale until a manual refresh.
        """
        coordinator.async_update_listeners()

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _on_core_config_update)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GreePlusConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: GreePlusConfigEntry) -> bool:
    """Migrate entity defaults and remove retired entities."""
    if entry.version < 3:
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if (
                entity.domain == Platform.BUTTON
                and entity.unique_id.endswith("_refresh")
                and entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
            ):
                entity_registry.async_update_entity(entity.entity_id, disabled_by=None)
            elif entity.domain == Platform.SWITCH and entity.unique_id.endswith(
                "_light"
            ):
                entity_registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(entry, version=3)
    return True
