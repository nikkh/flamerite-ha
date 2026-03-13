"""Number entity for Flamerite Glazer - flame brightness."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BRIGHTNESS_MAX, BRIGHTNESS_MIN
from .coordinator import FlameriteConfigEntry, FlameriteCoordinator
from .device import Device
from .entity import FlameriteEntity


@dataclass(frozen=True, kw_only=True)
class FlameriteNumberDescription(NumberEntityDescription):
    """Describes a Flamerite number entity."""
    get_value_fn: Callable[[Device], int]
    set_value_fn: Callable[[Device, int], Coroutine[Any, Any, None]]


class FlameriteNumberEntity(FlameriteEntity, NumberEntity):
    """Flame brightness slider for the Flamerite Glazer."""

    entity_description: FlameriteNumberDescription

    def __init__(
        self,
        coordinator: FlameriteCoordinator,
        description: FlameriteNumberDescription,
    ) -> None:
        """Initialise number entity."""
        super().__init__(coordinator, description)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Return current brightness."""
        return float(self.entity_description.get_value_fn(self.device))

    async def async_set_native_value(self, value: float) -> None:
        """Set brightness."""
        await self.entity_description.set_value_fn(self.device, int(value))
        await self.coordinator.async_request_refresh()


NUMBER_DESCRIPTIONS: list[FlameriteNumberDescription] = [
    FlameriteNumberDescription(
        key="flame_brightness",
        translation_key="flame_brightness",
        icon="mdi:brightness-6",
        native_min_value=float(BRIGHTNESS_MIN),
        native_max_value=float(BRIGHTNESS_MAX),
        native_step=1.0,
        mode=NumberMode.SLIDER,
        get_value_fn=lambda dev: dev.flame_brightness,
        set_value_fn=lambda dev, val: dev.set_flame_brightness(val),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlameriteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        FlameriteNumberEntity(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    )
