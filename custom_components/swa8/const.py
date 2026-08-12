"""Constants for the SWA8 cloud integration."""

from homeassistant.const import Platform

DOMAIN = "swa8"
MANUFACTURER = "SWA8"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_BASE_URL = "https://mm.swabim.com"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15

API_LOGIN = "/api/auth/login"
API_DEVICES = "/api/devices"
API_DEVICE_DETAIL = "/api/devices/{key}/detail"
API_DEVICE_STATE = "/api/devices/{key}/state"
API_DEVICE_COMMANDS = "/api/devices/{key}/commands"

NUM_RELAYS = 8
DEFAULT_AC_TEMP = 24

AC_TEMP_MIN = 16
AC_TEMP_MAX = 30

PLATFORMS = [Platform.SWITCH, Platform.NUMBER, Platform.SENSOR, Platform.BINARY_SENSOR]
