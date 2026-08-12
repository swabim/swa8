"""Number platform: AC target temperature."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import SWA8Entity
from .const import AC_TEMP_MAX, AC_TEMP_MIN, DEFAULT_AC_TEMP, DOMAIN
from .coordinator import SWA8Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SWA8 numbers."""
    coordinator: SWA8Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SWA8AcTempNumber(coordinator, device_key)
        for device_key in coordinator.devices
    )


class SWA8AcTempNumber(SWA8Entity, NumberEntity):
    """AC target temperature (16-30 °C)."""

    def __init__(self, coordinator: SWA8Coordinator, device_key: str) -> None:
        """Initialize the AC temperature number."""
        super().__init__(coordinator, device_key)
        self._attr_unique_id = f"{device_key}_ac_temperature"
        self._attr_name = "AC temperature"
        self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_native_min_value = AC_TEMP_MIN
        self._attr_native_max_value = AC_TEMP_MAX
        self._attr_native_step = 1

    @property
    def native_value(self) -> float | None:
        """Return the current AC target temperature."""
        value = self.coordinator.device_state(self._device_key).get("acTemp")
        if value is None:
            return None
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the AC target temperature."""
        await self.coordinator.async_send_command(
            self._device_key,
            {"type": "set_ac_temp", "value": int(round(value))},
        )
