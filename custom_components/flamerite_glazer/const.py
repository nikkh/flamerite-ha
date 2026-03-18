"""Constants for the Flamerite Glazer integration."""
from enum import IntEnum

DOMAIN = "flamerite_glazer"
DEFAULT_NAME = "Flamerite Glazer"

SUPPORTED_DEVICE_NAMES = ["Flamerite", "Flamerite ","NITRAFlame"]
DEVICE_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"

CMD_RESPONSE_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
CMD_REQUEST_UUID  = "0000fff2-0000-1000-8000-00805f9b34fb"

CHAR_MODEL_NUMBER  = "00002a24-0000-1000-8000-00805f9b34fb"
CHAR_SERIAL_NUMBER = "00002a25-0000-1000-8000-00805f9b34fb"
CHAR_FW_REVISION   = "00002a26-0000-1000-8000-00805f9b34fb"
CHAR_HW_REVISION   = "00002a27-0000-1000-8000-00805f9b34fb"
CHAR_MANUFACTURER  = "00002a29-0000-1000-8000-00805f9b34fb"

UPDATE_INTERVAL_SECONDS = 30
DEVICE_RESPONSE_TIMEOUT_SECONDS = 5

BRIGHTNESS_MIN = 1
BRIGHTNESS_MAX = 10

THERMOSTAT_MIN = 16
THERMOSTAT_MAX = 31


class HeatMode(IntEnum):
    """Heat modes as reported in state response byte."""
    OFF  = 0x0B
    LOW  = 0x0C
    HIGH = 0x0D


class Command:
    """BLE commands for the Flamerite Glazer (ERX40 module)."""
    QUERY_STATE          = bytes([0xA1, 0x01, 0x0A])
    POWER_ON             = bytes([0xA1, 0x01, 0xFF])
    POWER_OFF            = bytes([0xA1, 0x01, 0x00])
    HEAT_LOW             = bytes([0xA1, 0x01, 0x01])
    HEAT_HIGH            = bytes([0xA1, 0x01, 0x03])
    FLAME_BRIGHTNESS_INC = bytes([0xA1, 0x01, 0x04])
    FLAME_BRIGHTNESS_DEC = bytes([0xA1, 0x01, 0x05])

    @staticmethod
    def set_thermostat(temp_celsius: int) -> bytes:
        """Build a thermostat command for the given temperature."""
        temp = max(THERMOSTAT_MIN, min(THERMOSTAT_MAX, temp_celsius))
        return bytes([0xA2, 0x01, temp])