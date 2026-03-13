"""BLE device wrapper for Flamerite Glazer fires."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClient, establish_connection

from .const import (
    BRIGHTNESS_MAX,
    BRIGHTNESS_MIN,
    CHAR_FW_REVISION,
    CHAR_HW_REVISION,
    CHAR_MANUFACTURER,
    CHAR_MODEL_NUMBER,
    CHAR_SERIAL_NUMBER,
    CMD_REQUEST_UUID,
    CMD_RESPONSE_UUID,
    DEVICE_RESPONSE_TIMEOUT_SECONDS,
    THERMOSTAT_MAX,
    THERMOSTAT_MIN,
    Command,
    HeatMode,
)


_LOGGER = logging.getLogger(__name__)


class State:
    """Current known state of the device."""

    def __init__(self) -> None:
        self.is_powered_on: bool = False
        self.heat_mode: HeatMode = HeatMode.OFF
        self.flame_brightness: int = BRIGHTNESS_MIN
        self.thermostat: int = THERMOSTAT_MIN

    def update_from_bytes(self, data: bytearray) -> bool:
        """
        Parse a state notification packet.

        Packet structure:
          [0]     0x20 (fixed header)
          [1]     payload length (must be 7)
          [2]     device state:
                    0x0A = off
                    0x0B = on, no heat
                    0x0C = on, low heat
                    0x0D = on, high heat
          [3]     unknown
          [4]     thermostat offset (0-15, add 16 for degrees C)
          [5]     flame brightness (0-9, add 1 for display value)
          [6..8]  unused on Glazer model
        """
        _LOGGER.debug("Flamerite: state packet raw=%s", data.hex())

        if len(data) < 2 or data[0] != 0x20:
            _LOGGER.debug(
                "Flamerite: rejected packet header=0x%02x len=%d",
                data[0] if data else 0xFF,
                len(data),
            )
            return False

        payload = data[2:]

        if len(payload) != 7:
            _LOGGER.debug(
                "Flamerite: rejected packet payload len=%d (expected 7)",
                len(payload),
            )
            return False

        state_byte = int(payload[0])

        self.is_powered_on = state_byte > 0x0A

        self.heat_mode = (
            HeatMode(state_byte) if self.is_powered_on else HeatMode.OFF
        )

        self.thermostat = max(
            THERMOSTAT_MIN,
            min(THERMOSTAT_MAX, int(payload[2]) + 16),
        )

        self.flame_brightness = max(
            BRIGHTNESS_MIN,
            min(BRIGHTNESS_MAX, int(payload[3]) + 1),
        )

        _LOGGER.debug(
            "Flamerite: state parsed powered=%s heat=%s brightness=%d thermostat=%d",
            self.is_powered_on,
            self.heat_mode,
            self.flame_brightness,
            self.thermostat,
        )

        return True


class Device:
    """Wrapper for a Flamerite Glazer BLE device."""

    _connection_lock: asyncio.Lock
    _state_lock: asyncio.Lock

    def __init__(self, ble_device: BLEDevice) -> None:
        """Initialise device."""
        self._ble_device = ble_device
        self._connection: BleakClient | None = None
        self._is_connected = False

        self._mac = ble_device.address
        self._name = ble_device.name or DEFAULT_NAME

        self._state = State()
        self._state_updated = asyncio.Event()
        self._state_change_callback: Callable | None = None

        self._connection_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()

        # Device metadata
        self._model_number: str | None = None
        self._serial_number: str | None = None
        self._manufacturer: str | None = None
        self._fw_revision: str | None = None
        self._hw_revision: str | None = None

        _LOGGER.debug("Flamerite[%s]: device created", self._mac)

    # ------------------------------------------------------------------
    # Callback wiring
    # ------------------------------------------------------------------

    def set_state_change_callback(self, callback: Callable) -> None:
        """Register callback to be called on unsolicited state changes."""
        self._state_change_callback = callback

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the device if not already connected."""
        if self._is_connected:
            return

        async with self._connection_lock:
            if self._is_connected:
                return

            try:
                _LOGGER.debug("Flamerite[%s]: connecting", self._mac)

                self._connection = await establish_connection(
                    client_class=BleakClient,
                    device=self._ble_device,
                    name=self._mac,
                    disconnected_callback=self._on_disconnected,
                    max_attempts=4,
                    use_services_cache=True,
                )

                self._is_connected = True

                _LOGGER.debug("Flamerite[%s]: connected", self._mac)

                await self._read_metadata()
                await self._subscribe_notifications()

            except Exception as ex:
                _LOGGER.error(
                    "Flamerite[%s]: connection failed %s: %s",
                    self._mac,
                    type(ex).__name__,
                    ex,
                )
                await self._cleanup()

    async def disconnect(self) -> None:
        """Disconnect cleanly."""
        await self._cleanup()

    def _on_disconnected(self, client: BleakClient) -> None:
        """Handle unexpected disconnection."""
        _LOGGER.warning("Flamerite[%s]: disconnected", self._mac)
        self._is_connected = False

    async def _cleanup(self) -> None:
        """Release BLE connection."""
        try:
            if self._connection:
                try:
                    await self._connection.stop_notify(CMD_RESPONSE_UUID)
                except Exception:
                    pass
                await self._connection.disconnect()
        except Exception as ex:
            _LOGGER.debug("Flamerite[%s]: cleanup error %s", self._mac, ex)
        finally:
            self._connection = None
            self._is_connected = False

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    async def _read_metadata(self) -> None:
        """Read device information characteristics."""
        self._model_number  = await self._read_char(CHAR_MODEL_NUMBER)
        self._serial_number = await self._read_char(CHAR_SERIAL_NUMBER)
        self._manufacturer  = await self._read_char(CHAR_MANUFACTURER)
        self._fw_revision   = await self._read_char(CHAR_FW_REVISION)
        self._hw_revision   = await self._read_char(CHAR_HW_REVISION)

        _LOGGER.debug(
            "Flamerite[%s]: model=%s serial=%s manufacturer=%s fw=%s hw=%s",
            self._mac,
            self._model_number,
            self._serial_number,
            self._manufacturer,
            self._fw_revision,
            self._hw_revision,
        )

    async def _read_char(self, uuid: str) -> str:
        """Read a GATT characteristic and decode as UTF-8."""
        try:
            value = await self._connection.read_gatt_char(uuid)
            return value.decode("utf-8").strip("\x00")
        except Exception as ex:
            _LOGGER.debug(
                "Flamerite[%s]: failed to read char %s: %s", self._mac, uuid, ex
            )
            return ""

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    async def _subscribe_notifications(self) -> None:
        """Subscribe to state notification characteristic."""
        _LOGGER.debug(
            "Flamerite[%s]: subscribing to notifications", self._mac
        )
        await self._connection.start_notify(
            CMD_RESPONSE_UUID, self._on_notify
        )

    def _on_notify(
        self, char: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle incoming BLE notification."""
        _LOGGER.debug(
            "Flamerite[%s]: notification char=%s data=%s",
            self._mac,
            char.uuid,
            data.hex(),
        )

        if self._state.update_from_bytes(data):
            self._state_updated.set()

            # Push update to coordinator immediately
            if self._state_change_callback:
                self._state_change_callback()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def query_state(self) -> None:
        """Request current device state."""
        async with self._state_lock:
            self._state_updated.clear()
            await self._send(Command.QUERY_STATE)
            try:
                await asyncio.wait_for(
                    self._state_updated.wait(),
                    timeout=DEVICE_RESPONSE_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                _LOGGER.warning(
                    "Flamerite[%s]: state query timed out", self._mac
                )

    async def set_powered_on(self, value: bool) -> None:
        """Turn the fire on or off."""
        _LOGGER.debug("Flamerite[%s]: set_powered_on=%s", self._mac, value)
        async with self._state_lock:
            if self._state.is_powered_on == value:
                return
            await self._send(
                Command.POWER_ON if value else Command.POWER_OFF
            )
            self._state.is_powered_on = value

    async def set_heat_mode(self, mode: HeatMode) -> None:
        """Set the heat mode."""
        _LOGGER.debug("Flamerite[%s]: set_heat_mode=%s", self._mac, mode)
        async with self._state_lock:
            if mode == HeatMode.LOW:
                await self._send(Command.HEAT_LOW)
            elif mode == HeatMode.HIGH:
                await self._send(Command.HEAT_HIGH)
            else:
                await self._send(Command.POWER_OFF)
            self._state.heat_mode = mode

    async def set_flame_brightness(self, brightness: int) -> None:
        """Set flame brightness by sending inc/dec commands."""
        brightness = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, brightness))
        _LOGGER.debug(
            "Flamerite[%s]: set_flame_brightness=%d (current=%d)",
            self._mac,
            brightness,
            self._state.flame_brightness,
        )
        async with self._state_lock:
            delta = brightness - self._state.flame_brightness
            cmd = (
                Command.FLAME_BRIGHTNESS_INC
                if delta > 0
                else Command.FLAME_BRIGHTNESS_DEC
            )
            for _ in range(abs(delta)):
                await self._send(cmd)
            self._state.flame_brightness = brightness

    async def set_thermostat(self, temp_celsius: int) -> None:
        """Set the target thermostat temperature."""
        _LOGGER.debug(
            "Flamerite[%s]: set_thermostat=%d", self._mac, temp_celsius
        )
        async with self._state_lock:
            await self._send(Command.set_thermostat(temp_celsius))
            self._state.thermostat = max(
                THERMOSTAT_MIN, min(THERMOSTAT_MAX, temp_celsius)
            )

    async def _send(self, cmd: bytes) -> None:
        """Write a command to the device."""
        _LOGGER.debug(
            "Flamerite[%s]: send cmd=%s", self._mac, cmd.hex()
        )
        await self._connection.write_gatt_char(
            CMD_REQUEST_UUID, cmd, response=True
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def mac(self) -> str:
        return self._mac

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_powered_on(self) -> bool:
        return self._state.is_powered_on

    @property
    def heat_mode(self) -> HeatMode:
        return self._state.heat_mode

    @property
    def flame_brightness(self) -> int:
        return self._state.flame_brightness

    @property
    def thermostat(self) -> int:
        return self._state.thermostat

    @property
    def model_number(self) -> str | None:
        return self._model_number

    @property
    def serial_number(self) -> str | None:
        return self._serial_number

    @property
    def manufacturer(self) -> str | None:
        return self._manufacturer

    @property
    def firmware_revision(self) -> str | None:
        return self._fw_revision

    @property
    def hardware_revision(self) -> str | None:
        return self._hw_revision
