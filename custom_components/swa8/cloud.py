"""Async client for the SWA8 platform cloud API (mm.swabim.com)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    API_2FA_VERIFY,
    API_DEVICE_COMMANDS,
    API_DEVICE_DETAIL,
    API_DEVICES,
    API_LOGIN,
    API_ME,
    DEFAULT_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)


class SWA8AuthError(Exception):
    """Raised when login fails (wrong email/password)."""


class SWA8TwoFactorRequired(SWA8AuthError):
    """Raised when the account has 2FA and a TOTP code is needed."""

    def __init__(self, email: str) -> None:
        super().__init__("Two-factor authentication is required")
        self.email = email


class SWA8ApiError(Exception):
    """Raised for any other SWA8 API error."""


class SWA8CloudClient:
    """Minimal async REST client for the SWA8 platform.

    A normal user only needs an email + password: every device linked to
    that account is returned by GET /api/devices and controlled through
    POST /api/devices/{key}/commands.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._token: str | None = None
        self._email: str | None = None
        self._password: str | None = None
        self._owner_only: bool = False

    def set_credentials(self, email: str, password: str) -> None:
        """Store credentials used for automatic re-login."""
        self._email = email
        self._password = password

    def set_token(self, token: str) -> None:
        """Store a previously obtained session token."""
        self._token = token

    def set_owner_only(self, owner_only: bool) -> None:
        """When True, only return devices whose owner matches the account."""
        self._owner_only = owner_only

    @property
    def token(self) -> str | None:
        """Return the current session token."""
        return self._token

    async def login(self, email: str | None = None, password: str | None = None) -> str:
        """Login and store the JWT token. Raises SWA8AuthError on failure.

        If the account has 2FA enabled, raises SWA8TwoFactorRequired instead.
        """
        email = email or self._email
        password = password or self._password
        if not email or not password:
            raise SWA8AuthError("No credentials configured")

        url = f"{self.base_url}{API_LOGIN}"
        payload = {"email": email, "password": password}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                data = await self._response_data(resp)
                if resp.status >= 400 or not isinstance(data, dict):
                    raise SWA8AuthError(
                        str(data.get("error")) if isinstance(data, dict) else f"Login failed ({resp.status})"
                    )
                if data.get("needsTwoFactor"):
                    raise SWA8TwoFactorRequired(email)
                if not data.get("token"):
                    raise SWA8AuthError("Login failed: no token returned")

        self._token = str(data["token"])
        self._email = email
        self._password = password
        return self._token

    async def verify_2fa(self, email: str, code: str) -> str:
        """Verify the TOTP code and store the JWT token."""
        url = f"{self.base_url}{API_2FA_VERIFY}"
        payload = {"email": email, "code": code}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                data = await self._response_data(resp)
                if resp.status >= 400 or not isinstance(data, dict) or not data.get("token"):
                    raise SWA8AuthError(
                        str(data.get("error")) if isinstance(data, dict) else f"2FA verification failed ({resp.status})"
                    )

        self._token = str(data["token"])
        self._email = email
        return self._token

    async def validate_token(self) -> bool:
        """Check whether the stored token still works with GET /auth/me."""
        if not self._token:
            return False
        try:
            headers = {"Authorization": f"Bearer {self._token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}{API_ME}", headers=headers) as resp:
                    return resp.status < 400
        except aiohttp.ClientError as err:
            raise SWA8ApiError(str(err)) from err

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Authenticated request with one automatic re-login on 401/403."""
        if not self._token:
            await self.login()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, **kwargs) as resp:
                    data = await self._response_data(resp)
                    if resp.status in (401, 403):
                        await self.login()
                        headers["Authorization"] = f"Bearer {self._token}"
                        async with aiohttp.ClientSession() as session2:
                            async with session2.request(method, url, headers=headers, **kwargs) as resp2:
                                data2 = await self._response_data(resp2)
                                if resp2.status >= 400:
                                    raise SWA8ApiError(self._error_message(data2, resp2.status))
                                return data2
                    if resp.status >= 400:
                        raise SWA8ApiError(self._error_message(data, resp.status))
                    return data
        except aiohttp.ClientError as err:
            raise SWA8ApiError(str(err)) from err

    @staticmethod
    async def _response_data(resp: aiohttp.ClientResponse) -> Any:
        if resp.status == 204:
            return {}
        try:
            return await resp.json(content_type=None)
        except Exception:  # noqa: BLE001
            return {}

    @staticmethod
    def _error_message(data: Any, status: int) -> str:
        if isinstance(data, dict) and data.get("error"):
            return str(data["error"])
        return f"SWA8 API error (HTTP {status})"

    async def get_devices(self) -> list[dict[str, Any]]:
        """Return all devices linked to the account.

        When owner_only is enabled, filters out devices whose owner
        does not match the authenticated user's email.
        """
        data = await self._request("GET", f"{self.base_url}{API_DEVICES}")
        if isinstance(data, list):
            raw = data
        elif isinstance(data, dict):
            devices = data.get("devices", [])
            raw = list(devices) if isinstance(devices, list) else []
        else:
            raw = []

        if not self._owner_only or not self._email:
            return raw

        owner_lower = self._email.lower()
        filtered = []
        for dev in raw:
            if not isinstance(dev, dict):
                continue
            dev_owner = (
                dev.get("ownerEmail")
                or dev.get("owner_email")
                or dev.get("accountEmail")
                or dev.get("account_email")
            )
            if dev_owner and str(dev_owner).lower() != owner_lower:
                _LOGGER.debug(
                    "Skipping device %s (owned by %s, not %s)",
                    dev.get("deviceKey"), dev_owner, self._email,
                )
                continue
            filtered.append(dev)
        return filtered

    async def get_device(self, key: str) -> dict[str, Any]:
        """Return full device detail: state + online + firmware + config."""
        data = await self._request("GET", f"{self.base_url}{API_DEVICE_DETAIL.format(key=key)}")
        if isinstance(data, dict):
            device = data.get("device")
            return device if isinstance(device, dict) else data
        return {}

    async def send_command(self, key: str, command: dict[str, Any]) -> None:
        """Enqueue a command (e.g. {'type':'set_relay','relay':0,'value':True})."""
        await self._request(
            "POST", f"{self.base_url}{API_DEVICE_COMMANDS.format(key=key)}", json=command
        )
