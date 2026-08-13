"""DataUpdateCoordinator for the SWA8 cloud integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import async_get as async_get_dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud import SWA8ApiError, SWA8AuthError, SWA8CloudClient
from .const import DEFAULT_AC_TEMP, DOMAIN, NUM_RELAYS

_LOGGER = logging.getLogger(__name__)


class SWA8Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch all account devices and their states from the SWA8 platform."""

    def __init__(
        self,
        hass: HomeAssistant,
        cloud: SWA8CloudClient,
        scan_interval: int,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=config_entry,
        )
        self.cloud = cloud

    @property
    def devices(self) -> dict[str, dict[str, Any]]:
        """Map device_key -> device metadata from the last update."""
        return (self.data or {}).get("devices", {})

    def device_state(self, device_key: str) -> dict[str, Any]:
        """State payload of one device from the last update."""
        return (self.data or {}).get("states", {}).get(device_key, {})

    def relay_count(self, device_key: str) -> int:
        """Number of relays the device exposes (from its config or default)."""
        device = self.devices.get(device_key, {})
        config = device.get("config")
        if isinstance(config, dict):
            relays = config.get("relays")
            if isinstance(relays, list) and relays:
                return len(relays)
        return NUM_RELAYS

    async def async_send_command(
        self, device_key: str, command: dict[str, Any]
    ) -> None:
        """Send a command through the platform and apply it optimistically."""
        await self.cloud.send_command(device_key, command)
        self._apply_command(device_key, command)
        self.async_set_updated_data(self.data)

    def _apply_command(self, device_key: str, command: dict[str, Any]) -> None:
        """Mirror the command locally so the UI updates instantly."""
        if not self.data:
            return
        command_type = command.get("type")
        value = command.get("value")
        state = self.data["states"].setdefault(device_key, {})

        if command_type == "set_relay" and isinstance(command.get("relay"), int):
            relays = state.setdefault("relays", [])
            for relay in relays:
                if relay.get("index") == command["relay"]:
                    relay["state"] = bool(value)
                    break
        elif command_type == "set_all_relays":
            for relay in state.setdefault("relays", []):
                relay["state"] = bool(value)
        elif command_type == "set_ac_power":
            state["acPower"] = bool(value)
        elif command_type == "set_ac_temp":
            state["acTemp"] = int(value) if isinstance(value, (int, float)) else DEFAULT_AC_TEMP

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            devices: dict[str, dict[str, Any]] = {}
            states: dict[str, dict[str, Any]] = {}

            raw_devices = await self.cloud.get_devices()
            for dev in raw_devices:
                key = dev.get("deviceKey")
                if not key:
                    continue
                try:
                    detail = await self.cloud.get_device(key)
                except SWA8ApiError as err:
                    _LOGGER.warning("Skipping device %s: %s", key, err)
                    detail = dev
                detail = detail if isinstance(detail, dict) else dev
                devices[key] = detail
                config = detail.get("config")
                state = config.get("state", {}) if isinstance(config, dict) else {}
                states[key] = state if isinstance(state, dict) else {}

            self._cleanup_removed_devices(set(devices))
            return {"devices": devices, "states": states}
        except SWA8AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SWA8ApiError as err:
            raise UpdateFailed(f"SWA8 API error: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error communicating with SWA8: {err}") from err

    def _cleanup_removed_devices(self, current_keys: set[str]) -> None:
        """Remove HA devices that no longer exist on the SWA8 account.

        Called after every successful refresh so devices deleted from the
        platform are also removed from the Home Assistant device registry.
        """
        if not current_keys:
            return
        lower_keys = {key.lower() for key in current_keys}
        dr = async_get_dr(self.hass)
        for device in dr.devices.values():
            if self.config_entry.entry_id not in device.config_entries:
                continue
            for domain, identifier in device.identifiers:
                if domain != DOMAIN or not identifier.startswith("swa8_"):
                    continue
                if identifier[5:].lower() not in lower_keys:
                    _LOGGER.info("Removing SWA8 device %s (no longer on the account)", identifier[5:])
                    dr.async_remove_device(device.id)
                break
