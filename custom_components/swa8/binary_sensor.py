"""Binary sensor platform: device online status."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    """Set up SWA8 binary sensors."""
    coordinator: SWA8Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SWA8OnlineBinarySensor(coordinator, device_key)
        for device_key in coordinator.devices
    )


class SWA8OnlineBinarySensor(SWA8Entity, BinarySensorEntity):
    """Online/offline status of the device (from the platform)."""

    def __init__(self, coordinator: SWA8Coordinator, device_key: str) -> None:
        """Initialize the online sensor."""
        super().__init__(coordinator, device_key)
        self._attr_unique_id = f"{device_key}_online"
        self._attr_name = "Online"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return whether the device reported recently."""
        meta = self.coordinator.devices.get(self._device_key, {})
        return bool(meta.get("online"))
