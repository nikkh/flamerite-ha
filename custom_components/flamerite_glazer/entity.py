"""Base entity for Flamerite Glazer integration."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FlameriteCoordinator
from .device import Device


class FlameriteEntity(CoordinatorEntity[FlameriteCoordinator]):
    """Base class for all Flamerite Glazer entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FlameriteCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)

        self.entity_description = description

        device = coordinator.device

        self._attr_unique_id = f"{device.mac}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.mac)},
            name=device.name,
            manufacturer=device.manufacturer,
            model=device.model_number,
            serial_number=device.serial_number,
            sw_version=device.firmware_revision,
            hw_version=device.hardware_revision,
        )

    @property
    def device(self) -> Device:
        """Return the device from coordinator."""
        return self.coordinator.device

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_available = self.coordinator.device.is_connected
        self.async_write_ha_state()
