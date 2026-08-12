"""Base entity for the SWA8 cloud integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SWA8Coordinator


class SWA8Entity(CoordinatorEntity[SWA8Coordinator]):
    """Base class for all SWA8 entities.

    Each SWA8 board becomes one Home Assistant device; all of its
    relays / AC / sensors are grouped under that device.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: SWA8Coordinator, device_key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._attr_device_info = build_device_info(coordinator, device_key)


def build_device_info(
    coordinator: SWA8Coordinator, device_key: str
) -> DeviceInfo:
    """Build the DeviceInfo for one SWA8 board."""
    meta: dict[str, Any] = (coordinator.devices or {}).get(device_key, {})
    return DeviceInfo(
        identifiers={(DOMAIN, f"swa8_{device_key.lower()}")},
        name=meta.get("name") or device_key,
        manufacturer=MANUFACTURER,
        model=meta.get("hardwareModel") or meta.get("model") or "SWA8 Smart Hub",
        sw_version=meta.get("firmwareVersion"),
        configuration_url="https://mm.swabim.com/devices",
    )
