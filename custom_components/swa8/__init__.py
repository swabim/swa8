"""The SWA8 cloud integration.

Lets a normal user import every device linked to their mm.swabim.com
account and control it from Home Assistant through the platform.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .cloud import (
    SWA8ApiError,
    SWA8AuthError,
    SWA8CloudClient,
    SWA8TwoFactorRequired,
)
from .const import (
    CONF_EMAIL,
    CONF_OWNER_ONLY,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import SWA8Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SWA8 from a config entry."""
    email = entry.options.get(CONF_EMAIL, entry.data[CONF_EMAIL])
    password = entry.options.get(CONF_PASSWORD, entry.data.get(CONF_PASSWORD))
    token = entry.options.get(CONF_TOKEN, entry.data.get(CONF_TOKEN))
    if not email or not password:
        raise ConfigEntryAuthFailed("Credentials are missing, re-authenticate the integration")

    cloud = SWA8CloudClient()
    cloud.set_credentials(email, password)
    owner_only = entry.options.get(
        CONF_OWNER_ONLY, entry.data.get(CONF_OWNER_ONLY, False)
    )
    cloud.set_owner_only(owner_only)
    if token:
        cloud.set_token(token)
    try:
        if token and await cloud.validate_token():
            pass
        else:
            await cloud.login()
    except SWA8TwoFactorRequired as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SWA8AuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SWA8ApiError as err:
        raise ConfigEntryNotReady(f"Could not reach SWA8: {err}") from err

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    coordinator = SWA8Coordinator(hass, cloud, scan_interval, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
