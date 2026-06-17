#!/usr/bin/env python3
import asyncio
import logging
import signal
import os
import sys
import yaml
import uvicorn
from typing import Dict, Optional
from pydantic import BaseModel, Field, ValidationError

from mqtt_client import MQTTClient
from selve_manager import SelveManager
from web_app import app, active_websockets, broadcast_status_update

# --- Configuration Models ---

class SelveConfig(BaseModel):
    port: Optional[str] = None
    open_close_fix: bool = False
    min_firmware_version: str = "2.0.0"
    firmware_url: Optional[str] = None

class MQTTConfig(BaseModel):
    broker: str
    port: int = 1883
    username: str = ""
    password: str = ""
    client_id: str = "selve2mqtt"
    discovery_prefix: str = "homeassistant"

class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080

class AppConfig(BaseModel):
    mqtt: MQTTConfig
    selve: SelveConfig
    logging: Dict[str, str] = Field(default_factory=lambda: {"level": "INFO", "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"})
    language: str = "de"
    discovery_interval: int = 60
    update_interval: int = 30
    dashboard_token: Optional[str] = None  # Token for dashboard/API authentication - if empty or not set, no auth required
    web: WebConfig = Field(default_factory=WebConfig)

def load_config(config_file: str = "config.yaml"):
    try:
        with open(config_file, 'r') as f:
            raw_yaml = yaml.safe_load(f)
            if raw_yaml is None:
                raw_yaml = {}
            return AppConfig(**raw_yaml).model_dump()
    except FileNotFoundError:
        logging.error(f"Configuration file {config_file} not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML configuration {config_file}: {e}")
        sys.exit(1)
    except ValidationError as e:
        logging.error(f"Configuration validation failed:\n{e}")
        sys.exit(1)

logger = logging.getLogger("selve2mqtt.main")

async def run_fastapi(host: str, port: int):
    config_uv = uvicorn.Config(app, host=host, port=port, log_level="warning")
    await uvicorn.Server(config_uv).serve()

async def main():
    config = load_config()
    # Configure logging to output to stdout for container visibility
    log_cfg = config.get('logging', {}) or {}
    level_name = (log_cfg.get('level') or 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = log_cfg.get('format', "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logging.basicConfig(level=level, format=log_format, handlers=[logging.StreamHandler(sys.stdout)])

    loop = asyncio.get_running_loop()
    mqtt_client = MQTTClient(config)
    selve_manager = SelveManager(config, mqtt_client, loop, active_websockets)
    app.state.selve_manager = selve_manager
    app.state.mqtt_client = mqtt_client
    
    # Configure dashboard token and version
    from web_app import set_dashboard_token, set_app_version
    set_dashboard_token(config.get('dashboard_token'))
    set_app_version(os.environ.get("APP_VERSION", "dev"))

    def on_mqtt_message(client, userdata, msg):
        try:
            parts = msg.topic.split('/')
            payload_str = msg.payload.decode('utf-8').strip()
            payload_up = payload_str.upper()

            # Device command: selve/<device_id>/set or selve/<device_id>/position/set
            if len(parts) >= 3 and parts[0] == "selve" and parts[1] not in ("group", "gateway"):
                if parts[2] == "set":
                    cmd = {"OPEN": "open", "CLOSE": "close", "STOP": "stop"}.get(payload_up)
                    if cmd:
                        asyncio.run_coroutine_threadsafe(selve_manager.handle_command(parts[1], cmd), loop)
                elif parts[2] == "position" and len(parts) > 3 and parts[3] == "set":
                    try:
                        pos = int(payload_str)
                        asyncio.run_coroutine_threadsafe(selve_manager.handle_command(parts[1], "position", pos), loop)
                    except ValueError:
                        logger.warning("Invalid position payload for %s: %r", msg.topic, payload_str)

            # Group command: selve/group/<group_id>/... (expects at least 4 parts)
            elif len(parts) >= 4 and parts[0] == "selve" and parts[1] == "group":
                # selve/group/<group_id>/set
                if parts[3] == "set":
                    cmd = {"OPEN": "open", "CLOSE": "close", "STOP": "stop"}.get(payload_up)
                    if cmd:
                        asyncio.run_coroutine_threadsafe(selve_manager.handle_command(parts[2], cmd, is_group=True), loop)
                # selve/group/<group_id>/position/set
                elif parts[3] == "position" and len(parts) > 4 and parts[4] == "set":
                    try:
                        pos = int(payload_str)
                        asyncio.run_coroutine_threadsafe(selve_manager.handle_command(parts[2], "position", pos, is_group=True), loop)
                    except ValueError:
                        logger.warning("Invalid group position payload for %s: %r", msg.topic, payload_str)

            # Gateway commands: selve/gateway/<name>/set
            elif len(parts) >= 4 and parts[0] == "selve" and parts[1] == "gateway":
                enabled = payload_up == "ON"
                if parts[2] == "led" and parts[3] == "set":
                    asyncio.run_coroutine_threadsafe(selve_manager.set_gateway_led(enabled), loop)
                elif parts[2] == "forward" and parts[3] == "set":
                    asyncio.run_coroutine_threadsafe(selve_manager.set_gateway_forwarding(enabled), loop)
        except Exception:
            logger.exception("Error processing MQTT message on %s", msg.topic)

    def on_mqtt_connect(client, userdata, flags, rc, properties):
        connected = (rc == 0)
        if connected:
            logger.info("Connected to MQTT broker")
            client.subscribe("selve/#")
        else:
            logger.error(f"MQTT connection failed with error code {rc}")

        asyncio.run_coroutine_threadsafe(
            broadcast_status_update("mqtt_update", {"connected": connected}), 
            loop
        )

    def on_mqtt_disconnect(client, userdata, rc, properties):
        logger.warning(f"MQTT disconnected (rc: {rc})")
        asyncio.run_coroutine_threadsafe(
            broadcast_status_update("mqtt_update", {"connected": False}), 
            loop
        )

    # --- Initialization Sequence ---

    try:
        # Initialize Selve Connection
        await selve_manager.setup()
        await selve_manager.discover()

        # Setup MQTT (Set handler before starting)
        mqtt_client.client.on_message = on_mqtt_message
        mqtt_client.client.on_connect = on_mqtt_connect
        mqtt_client.client.on_disconnect = on_mqtt_disconnect
        mqtt_client.start()
        await selve_manager.publish_discovery()
    except Exception as e:
        logger.critical(f"Failed to initialize components: {e}", exc_info=True)
        if selve_manager.gateway: await selve_manager.gateway.stopWorker()
        sys.exit(1)

    # --- Running Tasks ---

    async def periodic_update():
        reconnecting = False
        try:
            while True:
                await asyncio.sleep(config.get('update_interval', 30))
                try:
                    await selve_manager.update_all()
                    if reconnecting:
                        logger.info("Connection to Selve Gateway restored.")
                        reconnecting = False
                except Exception as e:
                    reconnecting = True
                    logger.error(f"Selve Gateway connection lost: {e}. Attempting reconnect...")
                    # Inform UI that gateway is offline
                    await broadcast_status_update("gateway_update", {"duty_cycle": 0, "duty_blocked": True})
                    
                    try:
                        # Try to stop existing worker safely if it exists
                        if hasattr(selve_manager, 'gateway') and selve_manager.gateway:
                            try:
                                await selve_manager.gateway.stopWorker()
                            except Exception:
                                pass
                        
                        # Re-initialize the connection
                        await selve_manager.setup()
                        await selve_manager.discover()
                        await selve_manager.publish_discovery()
                        logger.info("Successfully reconnected to Selve Gateway")
                        reconnecting = False
                    except Exception as re_e:
                        logger.error(f"Reconnect attempt failed: {re_e}. Retrying in next cycle...")
        except asyncio.CancelledError:
            pass

    periodic_task = asyncio.create_task(periodic_update())

    # Web server configuration: environment variables take precedence over the config file
    web_port = int(os.environ.get("WEB_PORT", config['web']['port']))
    web_host = os.environ.get("WEB_HOST", config['web']['host'])
    fastapi_task = asyncio.create_task(run_fastapi(web_host, web_port))

    stop_event = asyncio.Event()
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down...")
        fastapi_task.cancel()
        try:
            periodic_task.cancel()
        except NameError:
            pass
        try:
            if selve_manager.gateway: await selve_manager.gateway.stopWorker()
        except Exception as e:
            logger.error(f"Error stopping Selve worker: {e}")
        mqtt_client.stop()
        await asyncio.sleep(1) # Allow tasks to settle

if __name__ == "__main__":
    asyncio.run(main())
