"""Config flow for Flamerite Glazer integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DEFAULT_NAME, DEVICE_SERVICE_UUID, DOMAIN, SUPPORTED_DEVICE_NAMES

_LOGGER = logging.getLogger(__name__)


class FlameriteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flamerite Glazer."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a bluetooth discovery."""

        _LOGGER.debug(
            "Flamerite: bluetooth discovery name=%s address=%s",
            discovery_info.name,
            discovery_info.address,
        )

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        if discovery_info.name not in SUPPORTED_DEVICE_NAMES:
            return self.async_abort(reason="not_supported")

        self._discovery_info = discovery_info

        self.context["title_placeholders"] = {
            "name": discovery_info.name,
            "address": discovery_info.address,
        }

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a bluetooth discovery."""

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name,
                data={CONF_ADDRESS: self._discovery_info.address},
            )

        self._set_confirm_only()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name,
                "address": self._discovery_info.address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user-initiated setup (manual add)."""

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={CONF_ADDRESS: address},
            )

        # Scan for discovered devices not yet configured
        current_addresses = self._async_current_ids()

        _LOGGER.warning("Flamerite config_flow: scanning for devices")

        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            _LOGGER.warning(
                "Flamerite config_flow: seen device name=%s address=%s uuids=%s",
                discovery_info.name,
                address,
                discovery_info.service_uuids,
            )
            if (
                address not in current_addresses
                and discovery_info.name in SUPPORTED_DEVICE_NAMES
            ):
                _LOGGER.warning(
                    "Flamerite config_flow: matched device %s", address
                )
                self._discovered_devices[address] = discovery_info

        _LOGGER.warning(
            "Flamerite config_flow: total matched=%d",
            len(self._discovered_devices),
        )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        devices_list = {
            address: f"{info.name} ({address})"
            for address, info in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(devices_list)}
            ),
        )