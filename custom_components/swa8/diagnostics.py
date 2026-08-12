"""Diagnostics support for the SWA8 integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, "token", "Authorization"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return async_redact_data(
        {
            "entry_data": dict(entry.data),
            "options": dict(entry.options),
            "last_update_success": coordinator.last_update_success,
            "last_update_exception": str(coordinator.last_update_exception)
            if coordinator.last_update_exception
            else None,
            "coordinator_data": coordinator.data,
        },
        TO_REDACT,
    )
