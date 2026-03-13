"""Switch entity for Flamerite Glazer - power on/off."""
from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlameriteConfigEntry, FlameriteCoordinator
from .device import Device
from .entity import FlameriteEntity


@dataclass(frozen=True, kw_only=True)
class FlameriteSwitchDescription(SwitchEntityDescription):
    """Describes a Flamerite switch entity."""
    is_on_fn: Callable[[Device], bool]
    turn_on_fn: Callable[[Device], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[Device], Coroutine[Any, Any, None]]


class FlameriteSwitchEntity(FlameriteEntity, SwitchEntity):
    """Power switch for the Flamerite Glazer."""

    entity_description: FlameriteSwitchDescription

    # The fire takes a few seconds to power down, during which it still
    # reports itself as on. This delay prevents the UI flickering back to on.
    _OFF_DELAY_SECONDS = 7.0
    _off_delay_until: float | None = None

    def __init__(
        self,
        coordinator: FlameriteCoordinator,
        description: FlameriteSwitchDescription,
    ) -> None:
        """Initialise switch entity."""
        super().__init__(coordinator, description)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return True if the fire is on."""
        if (
            self._off_delay_until
            and time.monotonic() < self._off_delay_until
        ):
            return False
        return self.entity_description.is_on_fn(self.device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the fire on."""
        self._off_delay_until = None
        await self.entity_description.turn_on_fn(self.device)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fire off."""
        await self.entity_description.turn_off_fn(self.device)
        self._off_delay_until = time.monotonic() + self._OFF_DELAY_SECONDS
        self.async_write_ha_state()


SWITCH_DESCRIPTIONS: list[FlameriteSwitchDescription] = [
    FlameriteSwitchDescription(
        key="power",
        translation_key="power",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:power",
        is_on_fn=lambda dev: dev.is_powered_on,
        turn_on_fn=lambda dev: dev.set_powered_on(True),
        turn_off_fn=lambda dev: dev.set_powered_on(False),
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlameriteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        FlameriteSwitchEntity(coordinator, description)
        for description in SWITCH_DESCRIPTIONS
    )
