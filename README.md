# Selve2MQTT Bridge

Selve2MQTT is a bridge that connects a **Selve USB-RF Gateway** to an MQTT broker. It allows you to control Selve Commeo and Iveo radio-controlled motors (shutters, awnings, blinds) via Home Assistant, openHAB, Node-RED, or any other MQTT-capable smart home system.

## Features

- **MQTT Discovery:** Automatic integration into Home Assistant (Cover entities with position feedback, diagnostic binary sensors, gateway switches).
- **Cover State (`is_opening` / `is_closing`):** Full bi-directional movement status reporting — Home Assistant correctly shows "Opening", "Closing", "Stopped", "Open", or "Closed".
- **Web Dashboard:** A built-in web interface for device management, pairing (learning mode), renaming, and diagnostics.
- **WebSocket API:** Real-time device updates and gateway events pushed to the dashboard.
- **REST API:** Full HTTP API for device control, group management, sender teach-in, and gateway configuration.
- **Commeo Support:** Bi-directional communication (position feedback, status flags, movement state).
- **Iveo Support:** Basic uni-directional control (optimistic state).
- **Group Control:** Support for Selve hardware groups (via `groupWrite`).
- **Gateway Diagnostics:** Monitoring of the Gateway Duty Cycle, LED control, Commeo Forwarding toggle.
- **Sender (Remote) Management:** List, rename, delete, and teach-in remote controls.
- **Sensor Support:** Read values from Selve sensors (wind, rain, light, temperature).
- **Secure API:** Optional token-based authentication for the web dashboard and REST API.
- **MQTT TLS/SSL:** Optional encrypted connection to the MQTT broker (TLS 1.2/1.3, CA verification, mutual TLS/mTLS, self-signed certificates).
- **Command Serialisation:** Automatic queue delay between gateway commands to prevent "Command overwritten" races.
- **Keepalive / Reconnect:** Automatic pings and reconnection handling for the Selve gateway.
- **Docker / Podman ready:** Official container image with health checks.
- **i18n:** Fully translated UI and log messages in German and English.

## Hardware Requirements

- A **Selve USB-RF Stick** (Art. No. 297792).
- A host to run the bridge (Raspberry Pi, NAS, or any Linux/macOS/Windows machine).

## Installation

### Prerequisites
- Python 3.10+
- A running MQTT Broker (e.g., Mosquitto)

### Setup
1. Clone this repository:
   ```bash
   git clone https://github.com/sven-probst/selve2mqtt.git
   cd selve2mqtt
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example configuration and edit it:
   ```bash
   cp config.yaml.example config.yaml
   ```
4. Start the bridge:
   ```bash
   python selve2mqtt.py
   ```

### Docker / Podman

The bridge is available as a Docker image. You need to map your configuration file and the serial device of the USB stick into the container.

#### Docker Compose

Create a `docker-compose.yml` file:

```yaml
services:
  selve2mqtt:
    image: ghcr.io/sven-probst/selve2mqtt:latest
    container_name: selve2mqtt
    restart: unless-stopped
    # Persistent device path (check /dev/serial/by-id/)
    devices:
      - "/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM01F387-if00-port0:/dev/tty-selve"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      # TLS certificates (uncomment if using TLS with custom CA or mTLS)
      # - ./certs:/app/certs:ro
      # Required for serial device metadata and stable paths
      - /run/udev:/run/udev:ro
      - /dev/serial:/dev/serial:ro
    ports:
      - "8080:8080"
    group_add:
      - dialout
    security_opt:
      - label:disable
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
```

Run it with:
```bash
docker compose up -d
```

#### Podman Quadlet (Recommended for Fedora/RHEL/CoreOS)

Create a file named `selve2mqtt.container` in `~/.config/containers/systemd/` (for rootless) or `/etc/containers/systemd/` (for system-wide):

```ini
[Unit]
Description=Selve2MQTT Bridge
After=network-online.target

[Container]
Image=ghcr.io/sven-probst/selve2mqtt:latest
ContainerName=selve2mqtt
# Persistent device path (check /dev/serial/by-id/)
AddDevice=/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM01F387-if00-port0:/dev/tty-selve
Volume=%h/selve2mqtt/config.yaml:/app/config.yaml:ro
# TLS certificates (uncomment if using TLS with custom CA or mTLS)
# Volume=%h/selve2mqtt/certs:/app/certs:ro
# Required for serial device metadata and stable paths
Volume=/run/udev:/run/udev:ro
Volume=/dev/serial:/dev/serial:ro
PublishPort=8080:8080

# Permissions for serial access
GroupAdd=dialout
SecurityLabelDisable=true

[Service]
Restart=always

# Healthcheck using the internal API
HealthCmd=curl -f http://localhost:8080/health || exit 1
HealthInterval=30s
HealthTimeout=10s
HealthStartPeriod=15s

[Install]
WantedBy=default.target
```

Then reload systemd and start the service:
```bash
systemctl --user daemon-reload
systemctl --user start selve2mqtt
```

## Configuration

The `config.yaml` file allows you to configure your MQTT broker and gateway settings. Key settings include:

- `mqtt`: Connection details for your broker.
- `mqtt.tls_enabled`: Set to `true` to connect via TLS/SSL (see [MQTT TLS/SSL](#mqtt-tlsssl) below).
- `selve.port`: The serial port of your USB stick (e.g., `/dev/ttyUSB0`). Leave empty for auto-detection.
- `selve.open_close_fix`: If `true`, position endpoints are corrected (0-1% → 0%, 99-100% → 100%).
- `selve.command_delay_ms`: Delay (ms) between gateway commands to prevent "Command overwritten" races.
- `dashboard_token`: Set a password/token to protect your web dashboard.
- `discovery_interval`: Seconds between MQTT discovery runs (0 = disabled).
- `update_interval`: Seconds between periodic state updates.

## MQTT TLS/SSL

The bridge supports encrypted MQTT connections via TLS/SSL. Enable it by setting `tls_enabled: true` in your `config.yaml`. When enabled, the port is automatically switched from `1883` to `8883` (the standard MQTT-over-TLS port) unless you specify a custom port.

### Simple TLS (server certificate verification)

This is the most common setup. The bridge verifies the broker's certificate against the system's default CA bundle (or a custom CA file).

```yaml
mqtt:
  broker: "mqtt.example.com"
  port: 8883
  username: "selve"
  password: "secret"
  tls_enabled: true
```

### TLS with custom CA certificate

If your broker uses a self-signed certificate or a private CA, provide the CA file:

```yaml
mqtt:
  broker: "192.168.1.100"
  port: 8883
  tls_enabled: true
  tls_ca_certs: "/app/certs/ca.pem"
```

### TLS with self-signed certificate (skip verification)

For development or testing with self-signed certificates where hostname verification should be skipped:

```yaml
mqtt:
  broker: "192.168.1.100"
  port: 8883
  tls_enabled: true
  tls_insecure: true    # ⚠️ Reduces security – only for testing!
```

> **Warning:** `tls_insecure: true` disables hostname verification. Only use this for testing or with self-signed certificates on trusted networks. Production systems should always verify certificates.

### Mutual TLS (mTLS) with client certificate

For maximum security, the broker can require a client certificate. Provide both `tls_certfile` and `tls_keyfile`:

```yaml
mqtt:
  broker: "mqtt.example.com"
  port: 8883
  tls_enabled: true
  tls_ca_certs: "/app/certs/ca.pem"
  tls_certfile: "/app/certs/client.pem"
  tls_keyfile: "/app/certs/client-key.pem"
  tls_keyfile_password: "key-password"   # optional, for encrypted key files
```

> **Note:** `tls_certfile` and `tls_keyfile` must always be provided together. Setting only one will result in a configuration error.

### TLS configuration reference

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `tls_enabled` | bool | `false` | Enable TLS/SSL encrypted connection |
| `tls_ca_certs` | string | `null` | Path to CA certificate file (`null` = system default CA bundle) |
| `tls_certfile` | string | `null` | Client certificate path for mutual TLS (mTLS) |
| `tls_keyfile` | string | `null` | Client private key path for mutual TLS (mTLS) |
| `tls_keyfile_password` | string | `null` | Password for encrypted client private key |
| `tls_insecure` | bool | `false` | Skip hostname verification (only for self-signed certs / testing) |
| `tls_version` | string | `"auto"` | TLS protocol version: `"auto"`, `"tlsv1_2"`, `"tlsv1_3"` |

## Smart Home Integration

### Home Assistant
If your Home Assistant instance has MQTT Discovery enabled, your Selve devices will appear automatically as **Cover** entities. 

- **Positioning:** Supports setting and reporting position (0-100%).
- **Movement State (`is_opening` / `is_closing`):** Home Assistant's cover entities will correctly display **Opening**, **Closing**, **Open**, **Closed**, and **Stopped** states. This is achieved by publishing a cover state string on a dedicated `state_topic`.
- **Attributes:** Connectivity status, error flags (obstructed, overload), and raw Selve values are available as diagnostic sensors.
- **Groups:** Created as cover entities with position control (optimistic, no feedback).

#### How `is_opening` / `is_closing` works

Each device publishes its current cover state on the topic `selve/<device_id>/cover_state`. The payload is one of:

| Payload | Meaning | Home Assistant State |
|---------|---------|---------------------|
| `"open"` | Fully open (position ≥ 100%) | `is_closing=False, is_opening=False` |
| `"closed"` | Fully closed (position ≤ 0%) | `is_closing=False, is_opening=False` |
| `"opening"` | Currently moving up | `is_opening=True` |
| `"closing"` | Currently moving down | `is_closing=True` |
| `"stopped"` | Stopped at an intermediate position | `is_closing=False, is_opening=False` |

The state is derived from the Selve `MovementState` enum:
- `MovementState.UP_ON` (2) → `"opening"`
- `MovementState.DOWN_ON` (3) → `"closing"`
- `MovementState.STOPPED_OFF` (1) → `"stopped"` (or `"open"`/`"closed"` if position is at an endpoint)
- `MovementState.UNKOWN` (0) → inferred from position

When a command is sent (e.g. `OPEN`, `CLOSE`, `STOP`), an **optimistic** state is published immediately, followed by the real state from the gateway callback.

#### Discovery Configuration

The MQTT discovery payload for each cover entity includes:

```json
{
  "state_topic": "selve/<device_id>/cover_state",
  "state_open": "open",
  "state_opening": "opening",
  "state_closed": "closed",
  "state_closing": "closing",
  "state_stopped": "stopped",
  "command_topic": "selve/<device_id>/set",
  "position_topic": "selve/<device_id>/position",
  "set_position_topic": "selve/<device_id>/position/set",
  "position_open": 100,
  "position_closed": 0,
  "availability_topic": "selve/status",
  "payload_available": "online",
  "payload_not_available": "offline",
  "optimistic": false,
  "device_class": "shutter"
}
```

### Other Systems (openHAB, Node-RED, etc.)
You can interact with the bridge using standard MQTT topics:

#### Control Topics
| Topic | Payload | Description |
| :--- | :--- | :--- |
| `selve/<device_id>/set` | `OPEN`, `CLOSE`, `STOP` | Control a specific device |
| `selve/<device_id>/position/set` | `0-100` | Set device to specific position |
| `selve/group/<group_id>/set` | `OPEN`, `CLOSE`, `STOP` | Control a Selve group |
| `selve/group/<group_id>/position/set` | `0-100` | Set group to specific position |
| `selve/gateway/led/set` | `ON`, `OFF` | Toggle the Gateway LED |
| `selve/gateway/forward/set` | `ON`, `OFF` | Toggle gateway serial command forwarding |

#### State Topics
| Topic | Payload | Description |
| :--- | :--- | :--- |
| `selve/status` | `online`, `offline` | Bridge status (LWT) |
| `selve/<device_id>/cover_state` | `open`, `closed`, `opening`, `closing`, `stopped` | Cover state for Home Assistant `is_opening`/`is_closing` |
| `selve/<device_id>/position` | `0-100` | Current position (0=closed, 100=open) |
| `selve/<device_id>/moving` | `ON`, `OFF` | Device movement flag |
| `selve/<device_id>/unreachable` | `ON`, `OFF` | Connection status of the device |
| `selve/<device_id>/selve_raw_value` | `0-100` | Raw Selve position (0=open, 100=closed) |
| `selve/<device_id>/state` | JSON | Device status flags and properties |
| `selve/<device_id>/attributes` | JSON | Detailed device attributes (day mode, alarms, etc.) |
| `selve/sensor/<sensor_id>/state` | Value | Current sensor reading |
| `selve/sender/<sender_id>/state` | Event code | Last sender event code |
| `selve/gateway/duty_cycle` | `0-100` | Current gateway duty cycle in percent |
| `selve/gateway/duty_cycle_blocked` | `ON`, `OFF` | Gateway blocked state (exceeded duty cycle) |
| `selve/gateway/led/state` | `ON`, `OFF` | Current Gateway LED state |
| `selve/gateway/forward/state` | `ON`, `OFF` | Current Gateway forwarding state |
| `selve/gateway/last_log` | JSON | Last received gateway event log |

#### Device State JSON Format

The `selve/<device_id>/state` topic publishes a JSON object with the following fields:

```json
{
  "position": 75,
  "moving": false,
  "movement_direction": null,
  "name": "Living Room Shutter",
  "unreachable": false,
  "obstructed": false,
  "overload": false,
  "auto_mode": true,
  "selve_raw_value": 25
}
```

- `movement_direction`: `"opening"`, `"closing"`, `"stopped"`, or `null` if unknown.
- `position`: Home Assistant percentage (0 = closed, 100 = open).
- `selve_raw_value`: Selve raw value (0 = open, 100 = closed).

## Web Dashboard

Access the dashboard via `http://<your-ip>:8080`. If a `dashboard_token` is configured, append `?token=xxx` to the URL or set the `X-Access-Token` header.

- **Pairing:** Click "Actor Learning" to put the gateway into pair mode for up to 60 seconds.
- **Sensor Learning:** Click "Sensor Learning" to teach in Selve sensors.
- **Sender Teach:** Click "Start sender teach" to pair remote controls to the gateway.
- **Management:** Rename devices, create/delete groups, manage senders, control LED and forwarding.
- **Diagnostics:** View Gateway duty cycle, firmware version, and device status.

## REST API

The bridge provides a comprehensive HTTP API (all endpoints under `/api/`). Below is a summary:

### Device Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/device/{device_id}/{command}` | Send command (`open`, `close`, `stop`, `position`, `pos1`, `pos2`) |
| POST | `/api/device/{device_id}/rename?name=...` | Rename a device |
| POST | `/api/device/{device_id}/delete` | Delete a device |
| POST | `/api/device/{device_id}/learning?enabled=true` | Device learning mode (limited support) |

### Group Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/group/{group_id}/{command}` | Send command to a group |
| POST | `/api/group/save` | Create or update a group (JSON body: `{id, name, device_ids}`) |
| POST | `/api/group/{group_id}/delete` | Delete a group |

### Sender Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/senders` | List all senders |
| GET | `/api/sender/{sender_id}` | Get sender info |
| POST | `/api/sender/{sender_id}/rename?name=...` | Rename a sender |
| POST | `/api/sender/{sender_id}/delete` | Delete a sender globally |
| GET | `/api/sender/{sender_id}/values` | Get sender values |
| POST | `/api/sender/teach?timeout=60` | Start sender teach/pairing |
| POST | `/api/sender/teach/stop` | Stop sender teach |

### Gateway Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/gateway/reset` | Reset the gateway |
| POST | `/api/gateway/config/led?enabled=true/false` | Toggle LED |
| POST | `/api/gateway/config/forward?enabled=true/false` | Toggle Commeo Forwarding |

### Learning Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/learn?timeout=60` | Start actor learning mode |
| POST | `/api/learn_sensor?timeout=60` | Start sensor learning mode |

### Health Endpoint
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (returns `{"status": "healthy", "mqtt": true, "selve": true}`) |

## WebSocket Protocol

The bridge provides a real-time WebSocket endpoint at `/ws`. Optional token authentication via `?token=xxx`.

### Client → Server
Send a JSON message:
```json
{"type": "request_full_state"}
```
Returns a `full_state` snapshot with all devices, groups, sensors, senders, gateway info, and MQTT connection status.

### Server → Client (Events)
| Type | Fields | Description |
|------|--------|-------------|
| `full_state` | `devices`, `groups`, `sensors`, `senders`, `gateway`, `mqtt_connected` | Initial or requested full state |
| `device_update` | `id`, `position`, `moving`, `movement_direction`, `unreachable`, `obstructed`, `overload`, `auto_mode` | Device state change |
| `gateway_update` | `duty_cycle`, `duty_blocked` | Gateway diagnostics update |
| `sensor_update` | `id`, `value`, `unit` | Sensor value change |
| `sender_update` | `id`, `event` | Sender event |
| `mqtt_update` | `connected` | MQTT connection state change |

## Development

This project uses:
- [python-selve-new](https://github.com/Kannix2005/python-selve-new) for communication with the Selve USB stick.
- **FastAPI** for the web server and REST API.
- **paho-mqtt** for MQTT communication.
- **Pydantic v2** for all configuration and state models (validation, serialisation).
- **asyncio** for asynchronous I/O and command serialisation.
- **WebSocket** for real-time dashboard updates.

### Project Structure
```
├── selve2mqtt.py          # Main entry point (asyncio)
├── models.py              # Pydantic models (config, device state, API)
├── selve_manager.py       # Selve gateway orchestrator (core logic)
├── mqtt_client.py         # MQTT client wrapper (paho-mqtt)
├── web_app.py             # FastAPI web server & REST API
├── common.py              # Shared utilities (logging, base class)
├── translations.py        # i18n strings (DE / EN)
├── templates/
│   └── dashboard.html     # Web dashboard HTML template
├── config.yaml.example    # Example configuration
└── Dockerfile             # Container build
```

### Adding a new language
1. Add a new language dictionary to `translations.py` (copy the `en` or `de` structure).
2. Add the language code to `LANGUAGE_CODES` in `models.py:AppConfig`.
3. Set `language: "xx"` in your `config.yaml`.

## License
This project is licensed under the MIT License - see the LICENSE file for details.