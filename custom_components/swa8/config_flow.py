"""Config flow for the SWA8 cloud integration.

The user only provides their mm.swabim.com account (email + password).
All devices linked to that account are imported automatically.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .cloud import SWA8AuthError, SWA8CloudClient
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot reach the SWA8 platform."""


class SWA8ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SWA8."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _validate_login(self, email: str, password: str) -> None:
        client = SWA8CloudClient()
        try:
            await client.login(email, password)
            await client.get_devices()
        except SWA8AuthError as err:
            raise InvalidAuth from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("SWA8 connect failed: %s", err)
            raise CannotConnect from err

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Account flow: email + password, imports all linked devices."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            try:
                await self._validate_login(email, password)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected SWA8 login error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(f"swa8_account_{email.lower()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication when the password changes."""
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the reauth form."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="not_configured")

        if user_input is not None:
            email = user_input.get(CONF_EMAIL, entry.data[CONF_EMAIL]).strip()
            password = user_input[CONF_PASSWORD]
            try:
                await self._validate_login(email, password)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected SWA8 login error")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=entry.data.get(CONF_EMAIL, "")): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return SWA8OptionsFlow(config_entry)


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid authentication."""


class SWA8OptionsFlow(OptionsFlow):
    """Handle options: credentials + polling interval."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            scan_interval = user_input[CONF_SCAN_INTERVAL]

            client = SWA8CloudClient()
            try:
                await client.login(email, password)
            except SWA8AuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("SWA8 connect failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_SCAN_INTERVAL: scan_interval,
                    },
                )

        entry = self.config_entry
        data_schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=entry.options.get(CONF_EMAIL, entry.data.get(CONF_EMAIL, ""))): str,
                vol.Required(CONF_PASSWORD, default=entry.options.get(CONF_PASSWORD, entry.data.get(CONF_PASSWORD, ""))): str,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=entry.options.get(
                        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
