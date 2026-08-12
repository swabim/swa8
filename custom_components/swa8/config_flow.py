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

from .cloud import SWA8AuthError, SWA8CloudClient, SWA8TwoFactorRequired
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
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

STEP_2FA_SCHEMA = vol.Schema(
    {
        vol.Required("code"): str,
    }
)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot reach the SWA8 platform."""


class SWA8ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SWA8."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Init the config flow."""
        self._email: str | None = None
        self._password: str | None = None
        self._client: SWA8CloudClient | None = None

    def _remember_credentials(self, email: str, password: str) -> None:
        """Remember email/password while the flow spans multiple steps."""
        self._email = email
        self._password = password

    def _entry_data(self, token: str | None) -> dict[str, Any]:
        """Build config entry data including the session token."""
        data: dict[str, Any] = {CONF_EMAIL: self._email, CONF_PASSWORD: self._password}
        if token:
            data[CONF_TOKEN] = token
        return data

    async def _finish_login(self, client: SWA8CloudClient) -> bool:
        """Validate the session works by fetching devices. Returns True on success."""
        try:
            await client.get_devices()
            return True
        except SWA8AuthError:
            return False
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("SWA8 connect failed: %s", err)
            return False

    async def _validate_login(self, email: str, password: str) -> str | None:
        """Validate login. Returns the token, or raises TwoFactorRequired."""
        client = SWA8CloudClient()
        try:
            token = await client.login(email, password)
        except SWA8TwoFactorRequired:
            self._client = client
            raise
        if not await self._finish_login(client):
            raise SWA8AuthError("Login succeeded but no devices were returned")
        self._client = client
        return token

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Account flow: email + password, imports all linked devices."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            self._remember_credentials(email, password)
            try:
                await self._validate_login(email, password)
            except SWA8TwoFactorRequired:
                return await self.async_step_2fa()
            except SWA8AuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("SWA8 connect failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"swa8_account_{email.lower()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=email,
                    data=self._entry_data(self._client.token if self._client else None),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """2FA step: ask for the TOTP code when the account requires it."""
        errors: dict[str, str] = {}
        email = self._email
        if user_input is not None and email is not None and self._client is not None:
            code = user_input.get("code", "").strip()
            try:
                token = await self._client.verify_2fa(email, code)
            except SWA8AuthError:
                errors["base"] = "invalid_2fa_code"
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("SWA8 connect failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not await self._finish_login(self._client):
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(f"swa8_account_{email.lower()}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=email,
                        data=self._entry_data(token),
                    )

        return self.async_show_form(
            step_id="2fa",
            data_schema=STEP_2FA_SCHEMA,
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
            self._remember_credentials(email, password)
            try:
                await self._validate_login(email, password)
            except SWA8TwoFactorRequired:
                return await self.async_step_2fa_reauth()
            except SWA8AuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("SWA8 connect failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data=self._entry_data(self._client.token if self._client else None),
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

    async def async_step_2fa_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """2FA step during re-authentication."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="not_configured")
        email = self._email
        if user_input is not None and email is not None and self._client is not None:
            code = user_input.get("code", "").strip()
            try:
                token = await self._client.verify_2fa(email, code)
            except SWA8AuthError:
                errors["base"] = "invalid_2fa_code"
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("SWA8 connect failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not await self._finish_login(self._client):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data=self._entry_data(token),
                    )

        return self.async_show_form(
            step_id="2fa_reauth",
            data_schema=STEP_2FA_SCHEMA,
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
        self._email: str | None = None
        self._password: str | None = None
        self._scan_interval: int | None = None
        self._client: SWA8CloudClient | None = None

    def _remember_credentials(self, email: str, password: str, scan_interval: int) -> None:
        """Remember values while the options flow spans multiple steps."""
        self._email = email
        self._password = password
        self._scan_interval = scan_interval

    def _options_data(self, token: str | None) -> dict[str, Any]:
        """Build options data including the session token."""
        data: dict[str, Any] = {
            CONF_EMAIL: self._email,
            CONF_PASSWORD: self._password,
            CONF_SCAN_INTERVAL: self._scan_interval,
        }
        if token:
            data[CONF_TOKEN] = token
        return data

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            self._remember_credentials(email, password, scan_interval)

            client = SWA8CloudClient()
            self._client = client
            try:
                token = await client.login(email, password)
            except SWA8TwoFactorRequired:
                return await self.async_step_2fa()
            except SWA8AuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("SWA8 connect failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                try:
                    await client.get_devices()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("SWA8 connect failed: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title="",
                        data=self._options_data(token),
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

    async def async_step_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """2FA step inside the options flow."""
        errors: dict[str, str] = {}
        email = self._email
        if user_input is not None and email is not None and self._client is not None:
            code = user_input.get("code", "").strip()
            try:
                token = await self._client.verify_2fa(email, code)
            except SWA8AuthError:
                errors["base"] = "invalid_2fa_code"
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("SWA8 connect failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                try:
                    await self._client.get_devices()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("SWA8 connect failed: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title="",
                        data=self._options_data(token),
                    )

        return self.async_show_form(
            step_id="2fa",
            data_schema=STEP_2FA_SCHEMA,
            errors=errors,
        )
