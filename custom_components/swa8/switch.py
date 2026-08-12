"""Switch platform: relays, "all relays" and AC power."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import SWA8Entity
from .const import DOMAIN
from .coordinator import SWA8Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SWA8 switches."""
    coordinator: SWA8Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SWA8Entity] = []

    for device_key in coordinator.devices:
        entities.append(SWA8AllRelaysSwitch(coordinator, device_key))
        entities.append(SWA8AcPowerSwitch(coordinator, device_key))
        for index in range(coordinator.relay_count(device_key)):
            entities.append(
                SWA8RelaySwitch(coordinator, device_key, index)
            )

    async_add_entities(entities)


class SWA8RelaySwitch(SWA8Entity, SwitchEntity):
    """A single relay of a SWA8 board."""

    def __init__(self, coordinator: SWA8Coordinator, device_key: str, index: int) -> None:
        """Initialize the relay switch."""
        super().__init__(coordinator, device_key)
        self._index = index
        self._attr_unique_id = f"{device_key}_relay_{index}"
        self._attr_extra_state_attributes = {
            "relay_index": index,
            "device_key": device_key,
        }
        self._name = None

    @property
    def name(self) -> str:
        """Relay name from the device config, or a default."""
        if self._name is not None:
            return self._name
        relays = self.coordinator.device_state(self._device_key).get("relays") or []
        for relay in relays:
            if relay.get("index") == self._index:
                self._name = relay.get("name") or f"Relay {self._index + 1}"
                return self._name
        return f"Relay {self._index + 1}"

    @property
    def is_on(self) -> bool:
        """Return the relay state."""
        relays = self.coordinator.device_state(self._device_key).get("relays") or []
        for relay in relays:
            if relay.get("index") == self._index:
                return bool(relay.get("state"))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the relay on through the platform."""
        await self.coordinator.async_send_command(
            self._device_key,
            {"type": "set_relay", "relay": self._index, "value": True},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the relay off through the platform."""
        await self.coordinator.async_send_command(
            self._device_key,
            {"type": "set_relay", "relay": self._index, "value": False},
        )


class SWA8AllRelaysSwitch(SWA8Entity, SwitchEntity):
    """Master switch that toggles every relay at once."""

    def __init__(self, coordinator: SWA8Coordinator, device_key: str) -> None:
        """Initialize the master switch."""
        super().__init__(coordinator, device_key)
        self._attr_unique_id = f"{device_key}_all_relays"
        self._attr_name = "All relays"

    @property
    def is_on(self) -> bool:
        """True when every relay is on."""
        relays = self.coordinator.device_state(self._device_key).get("relays") or []
        if not relays:
            return False
        return all(bool(relay.get("state")) for relay in relays)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn all relays on."""
        await self.coordinator.async_send_command(
            self._device_key,
            {"type": "set_all_relays", "value": True},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn all relays off."""
        await self.coordinator.async_send_command(
            self._device_key,
            {"type": "set_all_relays", "value": False},
        )


class SWA8AcPowerSwitch(SWA8Entity, SwitchEntity):
    """AC (air conditioner) power switch."""

    def __init__(self, coordinator: SWA8Coordinator, device_key: str) -> None:
        """Initialize the AC power switch."""
        super().__init__(coordinator, device_key)
        self._attr_unique_id = f"{device_key}_ac_power"
        self._attr_name = "AC power"

    @property
    def is_on(self) -> bool:
        """Return the AC power state."""
        return bool(self.coordinator.device_state(self._device_key).get("acPower"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the AC on."""
        await self.coordinator.async_send_command(
            self._device_key,
            {"type": "set_ac_power", "value": True},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the AC off."""
        await self.coordinator.async_send_command(
            self._device_key,
            {"type": "set_ac_power", "value": False},
        )
