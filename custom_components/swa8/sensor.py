"""Sensor platform: temperature and pressure (BMP280)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import SWA8Entity
from .const import DOMAIN
from .coordinator import SWA8Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SWA8 sensors."""
    coordinator: SWA8Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SWA8Entity] = []
    for device_key in coordinator.devices:
        entities.append(SWA8TemperatureSensor(coordinator, device_key))
        entities.append(SWA8PressureSensor(coordinator, device_key))
    async_add_entities(entities)


class SWA8TemperatureSensor(SWA8Entity, SensorEntity):
    """Temperature reported by the device."""

    def __init__(self, coordinator: SWA8Coordinator, device_key: str) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator, device_key)
        self._attr_unique_id = f"{device_key}_temperature"
        self._attr_name = "Temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> Any:
        """Return the temperature value (None when no BMP280)."""
        return self.coordinator.device_state(self._device_key).get("temperature")


class SWA8PressureSensor(SWA8Entity, SensorEntity):
    """Pressure reported by the device."""

    def __init__(self, coordinator: SWA8Coordinator, device_key: str) -> None:
        """Initialize the pressure sensor."""
        super().__init__(coordinator, device_key)
        self._attr_unique_id = f"{device_key}_pressure"
        self._attr_name = "Pressure"
        self._attr_device_class = SensorDeviceClass.PRESSURE
        self._attr_native_unit_of_measurement = UnitOfPressure.HPA

    @property
    def native_value(self) -> Any:
        """Return the pressure value (None when no BMP280)."""
        return self.coordinator.device_state(self._device_key).get("pressure")
