"""
Pydantic configuration models for selve2mqtt.

This module defines all Pydantic models used across the application:
- Configuration models (loaded from YAML)
- Domain state models (device, group, sensor, gateway)
- API request/response models (web endpoints)
- Logging configuration model

Kept in a separate module to avoid circular imports between selve2mqtt.py
and the component modules (mqtt_client.py, selve_manager.py, etc.).
"""

import re
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class LoggingConfig(BaseModel):
    """Structured logging configuration."""

    level: str = Field(
        default="INFO",
        description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Python logging format string",
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        normalized = v.strip().upper()
        if normalized not in VALID_LOG_LEVELS:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}"
            )
        return normalized

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        # Basic sanity: the format string should contain at least one %(...)s directive
        if not re.search(r"%\([^)]+\)[ds]", v):
            raise ValueError(
                f"Log format string must contain at least one %(name)s-style directive, got: {v!r}"
            )
        return v


# ---------------------------------------------------------------------------
# Selve gateway configuration
# ---------------------------------------------------------------------------

PORT_PATTERN = re.compile(r"^/dev/(tty[A-Za-z0-9_-]+|serial/by-id/.+)$")


class SelveConfig(BaseModel):
    """Configuration for the Selve USB-RF gateway connection."""

    port: Optional[str] = Field(
        default=None,
        description="Serial port device path (e.g. /dev/ttyUSB0). None = auto-detect.",
    )
    open_close_fix: bool = Field(
        default=False,
        description="Correct position endpoints: 0-1% → 0%, 99-100% → 100%.",
    )
    min_firmware_version: str = Field(
        default="2.0.0",
        description="Minimum required gateway firmware version.",
    )
    firmware_url: Optional[str] = Field(
        default=None,
        description="URL to fetch latest firmware version info from.",
    )
    command_delay_ms: int = Field(
        default=100,
        ge=10,
        le=5000,
        description="Delay (ms) between gateway commands to prevent 'Command overwritten' races.",
    )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not PORT_PATTERN.match(v):
            raise ValueError(
                f"Invalid serial port path '{v}'. Expected pattern: /dev/tty* or /dev/serial/by-id/*"
            )
        return v

    @field_validator("min_firmware_version")
    @classmethod
    def validate_firmware_version(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\d+(\.\d+){0,3}$", v):
            raise ValueError(
                f"Invalid firmware version format '{v}'. Expected e.g. '2.0.0' or '24.6.4.2'."
            )
        return v


# ---------------------------------------------------------------------------
# MQTT broker configuration
# ---------------------------------------------------------------------------

class MQTTConfig(BaseModel):
    """Configuration for the MQTT broker connection."""

    broker: str = Field(
        ...,  # required
        min_length=1,
        description="MQTT broker hostname or IP address.",
    )
    port: int = Field(
        default=1883,
        ge=1,
        le=65535,
        description="MQTT broker TCP port.",
    )
    username: str = Field(
        default="",
        description="MQTT authentication username (empty = no auth).",
    )
    password: str = Field(
        default="",
        description="MQTT authentication password.",
    )
    client_id: str = Field(
        default="selve2mqtt",
        min_length=1,
        max_length=128,
        description="MQTT client identifier.",
    )
    discovery_prefix: str = Field(
        default="homeassistant",
        min_length=1,
        description="Home Assistant MQTT discovery prefix.",
    )

    @model_validator(mode="after")
    def check_credentials_consistency(self) -> "MQTTConfig":
        """If a username is provided, a password must also be set (can be empty)."""
        # This is just a consistency check – empty password is allowed with username.
        return self


# ---------------------------------------------------------------------------
# Web server configuration
# ---------------------------------------------------------------------------

HOST_PATTERN = re.compile(r"^[a-zA-Z0-9.*_-]+$")


class WebConfig(BaseModel):
    """Configuration for the built-in FastAPI/webserver."""

    host: str = Field(
        default="0.0.0.0",
        description="Web server bind address.",
    )
    port: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="Web server TCP port.",
    )

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        v = v.strip()
        # Allow common special values
        if v in ("0.0.0.0", "127.0.0.1", "::", "::1", "localhost"):
            return v
        if not HOST_PATTERN.match(v):
            raise ValueError(f"Invalid host address '{v}'.")
        return v


# ---------------------------------------------------------------------------
# Top-level application configuration
# ---------------------------------------------------------------------------

LANGUAGE_CODES = {"de", "en", "es", "fr", "nl", "pt", "it"}


class AppConfig(BaseModel):
    """Root configuration model loaded from config.yaml."""

    mqtt: MQTTConfig
    selve: SelveConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    language: str = Field(default="de", description="UI language code (de, en).")
    discovery_interval: int = Field(
        default=60,
        ge=0,
        le=86400,
        description="Seconds between discovery runs (0 = disabled).",
    )
    update_interval: int = Field(
        default=30,
        ge=5,
        le=3600,
        description="Seconds between periodic state updates.",
    )
    dashboard_token: Optional[str] = Field(
        default=None,
        description="Token for dashboard/API authentication. None = no auth required.",
    )
    web: WebConfig = Field(default_factory=WebConfig)

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in LANGUAGE_CODES:
            raise ValueError(
                f"Unsupported language '{v}'. Must be one of: {', '.join(sorted(LANGUAGE_CODES))}"
            )
        return normalized

    @field_validator("dashboard_token")
    @classmethod
    def validate_token(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if v == "":
                return None  # Treat empty string as "no token"
        return v


# ---------------------------------------------------------------------------
# Domain state models (used as frozen / immutable data containers)
# ---------------------------------------------------------------------------


class DeviceState(BaseModel):
    """Immutable snapshot of a single Selve device (actor) state."""

    position: Optional[int] = Field(
        default=None, ge=0, le=100, description="Position in HA percent (0=closed, 100=open)."
    )
    moving: bool = Field(default=False, description="Whether the device is currently moving.")
    movement_direction: Optional[str] = Field(
        default=None,
        pattern=r"^(opening|closing|stopped)$",
        description="Direction of movement: 'opening', 'closing', 'stopped', or None if unknown."
    )
    name: str = Field(default="Unknown", description="Human-readable device name/label.")
    unreachable: bool = Field(default=False, description="Device is not reachable.")
    obstructed: bool = Field(default=False, description="Device movement is obstructed.")
    overload: bool = Field(default=False, description="Device reports overload.")
    auto_mode: bool = Field(default=False, description="Automatic mode is enabled.")
    selve_raw_value: int = Field(default=0, ge=0, le=100, description="Raw Selve position (0=open, 100=closed).")
    model_config = {"frozen": True}


class DeviceCreate(BaseModel):
    """Payload for creating a new device (learning mode result)."""

    device_id: str = Field(..., description="Selve device ID.")
    name: str = Field(default="", max_length=128, description="Optional friendly name.")


class DeviceRename(BaseModel):
    """Payload for renaming a device."""

    name: str = Field(..., min_length=1, max_length=128, description="New device name.")


class DeviceCommand(BaseModel):
    """Payload for sending a command to a device or group."""
    command: str = Field(
        ..., pattern=r"^(open|close|stop|position|pos1|pos2)$",
        description="Command: open, close, stop, position, pos1, pos2.",
    )
    value: Optional[int] = Field(
        default=None, ge=0, le=100,
        description="Target position (0-100), required only when command='position'.",
    )

    @model_validator(mode="after")
    def check_position_value(self) -> "DeviceCommand":
        if self.command == "position" and self.value is None:
            raise ValueError("A 'value' (0-100) is required when command='position'.")
        if self.command != "position" and self.value is not None:
            raise ValueError("A 'value' is only allowed when command='position'.")
        return self


class GroupState(BaseModel):
    """Immutable snapshot of a single Selve group state."""

    name: str = Field(default="Unknown", description="Group label/name.")
    device_ids: List[str] = Field(
        default_factory=list, description="List of device IDs that belong to this group."
    )

    model_config = {"frozen": True}


class GroupSave(BaseModel):
    """Payload for creating or updating a group."""

    id: int = Field(..., ge=0, le=63, description="Group ID (0-63).")
    name: str = Field(..., min_length=1, max_length=128, description="Group name.")
    device_ids: List[int] = Field(
        ..., min_length=1, description="List of device member IDs."
    )


class SensorState(BaseModel):
    """Immutable snapshot of a single Selve sensor state."""

    value: Union[int, float, str] = Field(default="unknown", description="Current sensor reading.")
    type: str = Field(default="Generic", description="Translated sensor type name.")
    unit: str = Field(default="", description="Measurement unit symbol.")
    name: str = Field(default="Unknown", description="Sensor label/name.")

    model_config = {"frozen": True}


class SensorRename(BaseModel):
    """Payload for renaming a sensor."""

    name: str = Field(..., min_length=1, max_length=128, description="New sensor name.")


class GatewayState(BaseModel):
    """Immutable snapshot of the Selve USB-RF gateway state."""

    duty_cycle: int = Field(default=0, ge=0, le=100, description="Current duty cycle percentage.")
    duty_blocked: bool = Field(default=False, description="Duty cycle limit reached / blocked.")
    hardware: str = Field(default="N/A", description="Hardware version string.")
    firmware: str = Field(default="N/A", description="Firmware version string.")
    latest_firmware: str = Field(default="N/A", description="Latest available firmware version online.")
    serial_number: str = Field(default="Unknown", description="Gateway serial number.")

    model_config = {"frozen": True}


class GatewaySettingToggle(BaseModel):
    """Payload for toggling a gateway setting (LED, forwarding)."""

    enabled: bool = Field(..., description="Desired state: true = ON, false = OFF.")


class SenderInfo(BaseModel):
    """Information about a sender (remote control) taught to the gateway."""
    id: str = Field(..., description="Sender ID.")
    name: str = Field(default="Unknown", description="Sender label/name.")
    rfAddress: Optional[str] = Field(default=None, description="RF address, if available.")
    rfChannel: Optional[int] = Field(default=None, description="RF channel, if available.")
    rfResetCount: Optional[int] = Field(default=None, description="RF reset counter, if available.")


class SenderRename(BaseModel):
    """Payload for renaming a sender."""

    name: str = Field(..., min_length=1, max_length=128, description="New sender name.")


class SenderTeachResult(BaseModel):
    """Result of a sender teach-in operation."""

    status: str = Field(
        ..., pattern=r"^(success|failed|timeout|error|not_supported)$",
        description="Outcome of the teach operation.",
    )
    sender: Optional[str] = Field(default=None, description="Discovered sender ID on success.")
    error: Optional[str] = Field(default=None, description="Error message on failure.")


class LearningResult(BaseModel):
    """Result of a device or sensor learning operation."""

    status: str = Field(
        ..., pattern=r"^(success|timeout)$",
        description="Outcome of the learning operation.",
    )
    message: str = Field(..., description="Human-readable result message.")


# ---------------------------------------------------------------------------
# API response wrappers
# ---------------------------------------------------------------------------


class StatusResponse(BaseModel):
    """Generic status response for API endpoints."""

    status: str = Field(default="ok", pattern=r"^(ok|error)$")
    message: Optional[str] = Field(default=None)


class FullSystemState(BaseModel):
    """Complete system snapshot returned over WebSocket."""

    type: str = Field(default="full_state", pattern=r"^full_state$")
    devices: Dict[str, DeviceState] = Field(default_factory=dict)
    groups: Dict[str, GroupState] = Field(default_factory=dict)
    sensors: Dict[str, SensorState] = Field(default_factory=dict)
    senders: Dict[str, SenderInfo] = Field(default_factory=dict)
    gateway: GatewayState = Field(default_factory=GatewayState)
    mqtt_connected: bool = Field(default=False)


class WebSocketMessage(BaseModel):
    """Typed union for WebSocket messages (validated at runtime)."""

    type: str = Field(..., description="Message type identifier.")
    data: Optional[Dict[str, Any]] = Field(default=None)


class DeviceUpdateWS(BaseModel):
    """WebSocket device update payload."""

    type: str = Field(default="device_update", pattern=r"^device_update$")
    id: str = Field(..., description="Device ID.")
    position: Optional[int] = Field(default=None, ge=0, le=100)
    moving: bool = Field(default=False)
    movement_direction: Optional[str] = Field(default=None, pattern=r"^(opening|closing|stopped)$")
    unreachable: bool = Field(default=False)
    obstructed: bool = Field(default=False)
    overload: bool = Field(default=False)
    auto_mode: bool = Field(default=False)


class GatewayUpdateWS(BaseModel):
    """WebSocket gateway diagnostics update."""

    type: str = Field(default="gateway_update", pattern=r"^gateway_update$")
    duty_cycle: int = Field(default=0, ge=0, le=100)
    duty_blocked: bool = Field(default=False)


class SensorUpdateWS(BaseModel):
    """WebSocket sensor value update."""

    type: str = Field(default="sensor_update", pattern=r"^sensor_update$")
    id: str = Field(..., description="Sensor ID.")
    value: Union[int, float, str] = Field(default="unknown")
    unit: str = Field(default="")


class SenderUpdateWS(BaseModel):
    """WebSocket sender event update."""

    type: str = Field(default="sender_update", pattern=r"^sender_update$")
    id: str = Field(..., description="Sender ID.")
    event: int = Field(default=0, description="Last event code.")

