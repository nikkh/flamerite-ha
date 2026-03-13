"""Climate entity for Flamerite Glazer - heat mode and thermostat."""
from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.climate.const import (
    FAN_HIGH,
    FAN_LOW,
    FAN_OFF,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import HeatMode, THERMOSTAT_MIN, THERMOSTAT_MAX
from .coordinator import FlameriteConfigEntry, FlameriteCoordinator
from .entity import FlameriteEntity


class FlameriteClimateEntity(FlameriteEntity, ClimateEntity):
    """
    Climate entity for the Flamerite Glazer heater.

    Heat mode is exposed as fan mode:
      FAN_OFF  → heater off
      FAN_LOW  → 1kW low heat
      FAN_HIGH → 1.5kW high heat

    Thermostat target temperature is also supported.
    """

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_fan_modes = [FAN_OFF, FAN_LOW, FAN_HIGH]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = float(THERMOSTAT_MIN)
    _attr_max_temp = float(THERMOSTAT_MAX)
    _attr_target_temperature_step = 1.0
    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
    )

    def __init__(
        self,
        coordinator: FlameriteCoordinator,
        description: ClimateEntityDescription,
    ) -> None:
        """Initialise climate entity."""
        super().__init__(coordinator, description)

    # ------------------------------------------------------------------
    # HVAC mode
    # ------------------------------------------------------------------

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if self.device.heat_mode is HeatMode.OFF:
            return HVACMode.OFF
        return HVACMode.HEAT

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode is HVACMode.HEAT:
            if not self.device.is_powered_on:
                await self.device.set_powered_on(True)
            if self.device.heat_mode is HeatMode.OFF:
                await self.device.set_heat_mode(HeatMode.LOW)
        else:
            await self.device.set_heat_mode(HeatMode.OFF)

        await self.coordinator.async_request_refresh()

    # ------------------------------------------------------------------
    # Fan mode (maps to heat level)
    # ------------------------------------------------------------------

    @property
    def fan_mode(self) -> str:
        """Return current fan mode (heat level)."""
        if self.device.heat_mode is HeatMode.LOW:
            return FAN_LOW
        if self.device.heat_mode is HeatMode.HIGH:
            return FAN_HIGH
        return FAN_OFF

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode (heat level)."""
        if fan_mode in (FAN_LOW, FAN_HIGH):
            if not self.device.is_powered_on:
                await self.device.set_powered_on(True)
            mode = HeatMode.LOW if fan_mode == FAN_LOW else HeatMode.HIGH
        else:
            mode = HeatMode.OFF

        await self.device.set_heat_mode(mode)
        await self.coordinator.async_request_refresh()

    # ------------------------------------------------------------------
    # Thermostat
    # ------------------------------------------------------------------

    @property
    def target_temperature(self) -> float:
        """Return target thermostat temperature."""
        return float(self.device.thermostat)

    @property
    def current_temperature(self) -> float | None:
        """Glazer does not report current temperature."""
        return None

    async def async_set_temperature(self, **kwargs) -> None:
        """Set thermostat target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            await self.device.set_thermostat(int(temperature))
            await self.coordinator.async_request_refresh()


CLIMATE_DESCRIPTION = ClimateEntityDescription(
    key="heater",
    translation_key="heater",
    icon="mdi:radiator",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlameriteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entity."""
    coordinator = entry.runtime_data
    async_add_entities([
        FlameriteClimateEntity(coordinator, CLIMATE_DESCRIPTION)
    ])
