# Selve2MQTT Bridge

Selve2MQTT is a bridge that connects a **Selve USB-RF Gateway** to an MQTT broker. It allows you to control Selve Commeo and Iveo radio-controlled motors (shutters, awnings, blinds) via Home Assistant, openHAB, Node-RED, or any other MQTT-capable smart home system.

## Features

- **MQTT Discovery:** Automatic integration into Home Assistant (Covers, Sensors, and Diagnostic switches).
- **Web Dashboard:** A built-in web interface for device management, pairing (learning mode), and renaming.
- **Commeo Support:** Bi-directional communication (position feedback, RSSI, status flags).
- **Iveo Support:** Basic uni-directional control.
- **Group Control:** Support for Selve hardware groups.
- **Gateway Diagnostics:** Monitoring of the Gateway Duty Cycle and system health.
- **Secure API:** Optional token-based authentication for the web dashboard and REST API.

## Hardware Requirements

- A **Selve USB-RF Stick** (Art. No. 297792).
- A host to run the bridge (Raspberry Pi, NAS, or any Linux/macOS/Windows machine).

## Installation

### Prerequisites
- Python 3.9+
- A running MQTT Broker (e.g., Mosquitto)

### Setup
1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/selve2mqtt.git
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

## Configuration

The `config.yaml` file allows you to configure your MQTT broker and gateway settings. Key settings include:

- `mqtt`: Connection details for your broker.
- `selve.port`: The serial port of your USB stick (e.g., `/dev/ttyUSB0`).
- `dashboard_token`: Set a password/token to protect your web dashboard.

## Smart Home Integration

### Home Assistant
If your Home Assistant instance has MQTT Discovery enabled, your Selve devices will appear automatically as **Cover** entities. 
- **Positioning:** Supports setting and reporting position (0-100%).
- **Attributes:** RSSI, connectivity status, and error flags (obstructed, overload) are available as diagnostic sensors.

### Other Systems (openHAB, Node-RED, etc.)
You can interact with the bridge using standard MQTT topics:

#### Control Topics
| Topic | Payload | Description |
| :--- | :--- | :--- |
| `selve/<device_id>/set` | `OPEN`, `CLOSE`, `STOP` | Control a specific device |
| `selve/<device_id>/position/set` | `0-100` | Set device to specific position |
| `selve/group/<group_id>/set` | `OPEN`, `CLOSE`, `STOP` | Control a Selve group |
| `selve/gateway/led/set` | `ON`, `OFF` | Toggle the Gateway LED |

#### State Topics
| Topic | Payload | Description |
| :--- | :--- | :--- |
| `selve/<device_id>/position` | `0-100` | Current position (0=closed, 100=open) |
| `selve/<device_id>/rssi` | `dBm` | Signal strength |
| `selve/<device_id>/unreachable` | `ON`, `OFF` | Connection status |
| `selve/status` | `online`, `offline` | Bridge status (LWT) |

## Web Dashboard

Access the dashboard via `http://<your-ip>:8080`. 

- **Pairing:** Click "Actor Learning" to put the gateway into pair mode for 30 seconds.
- **Management:** Rename devices, create/delete groups, or check the Gateway duty cycle.
- **API:** The bridge provides a REST API (see `web_app.py` for endpoints).

## Development

This project uses:
- FastAPI for the web server.
- paho-mqtt for MQTT communication.
- python-selve-new for communication with the Selve USB stick.

## License
This project is licensed under the MIT License - see the LICENSE file for details.