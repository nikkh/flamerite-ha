"""Coordinator for the Flamerite Glazer integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_NAME, DOMAIN, UPDATE_INTERVAL_SECONDS
from .device import Device

_LOGGER = logging.getLogger(__name__)

type FlameriteConfigEntry = ConfigEntry[FlameriteCoordinator]


class FlameriteCoordinator(DataUpdateCoordinator[Device]):
    """Flamerite Glazer data update coordinator."""

    config_entry: FlameriteConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FlameriteConfigEntry,
        device: Device,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DEFAULT_NAME,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self._device = device

        # Wire BLE notifications → immediate coordinator refresh
        self._device.set_state_change_callback(
            lambda: hass.async_create_task(self.async_request_refresh())
        )

    async def _async_update_data(self) -> Device:
        """Poll device state."""
        await self._device.connect()
        await self._device.query_state()
        return self._device

    @property
    def device(self) -> Device:
        """Return the device."""
        return self._device
