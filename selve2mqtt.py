#!/usr/bin/env python3
import asyncio
import logging
import signal
import os
import sys
import yaml
import uvicorn
from typing import Dict, Optional
from pydantic import ValidationError

from models import AppConfig, LoggingConfig
from mqtt_client import MQTTClient
from selve_manager import SelveManager
from web_app import app, active_websockets, broadcast_status_update
from common import setup_logger


def load_config(config_file: str = "config.yaml") -> AppConfig:
    try:
        with open(config_file, 'r') as f:
            raw_yaml = yaml.safe_load(f)
            if raw_yaml is None:
                raw_yaml = {}
            return AppConfig(**raw_yaml)
    except FileNotFoundError:
        logging.error(f"Configuration file {config_file} not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML configuration {config_file}: {e}")
        sys.exit(1)
    except ValidationError as e:
        logging.error(f"Configuration validation failed:\n{e}")
        sys.exit(1)


logger = setup_logger("selve2mqtt.main")


# Global reference to the uvicorn server for graceful shutdown
_uvicorn_server: Optional[uvicorn.Server] = None


async def run_fastapi(host: str, port: int):
    """Run the FastAPI/uvicorn server and keep a global reference for shutdown."""
    global _uvicorn_server
    config_uv = uvicorn.Config(app, host=host, port=port, log_level="warning")
    _uvicorn_server = uvicorn.Server(config_uv)
    await _uvicorn_server.serve()


async def main():
    config = load_config()

    # Apply structured logging configuration from the validated model
    root_logger = logging.getLogger()
    root_logger.setLevel(config.logging.level)
    for handler in root_logger.handlers:
        handler.setLevel(config.logging.level)
        handler.setFormatter(logging.Formatter(config.logging.format))

    loop = asyncio.get_running_loop()

    # Configure dashboard token and version
    from web_app import set_dashboard_token, set_app_version
    set_dashboard_token(config.dashboard_token)
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

            # Group command: selve/group/<group_id>/...
            elif len(parts) >= 4 and parts[0] == "selve" and parts[1] == "group":
                if parts[3] == "set":
                    cmd = {"OPEN": "open", "CLOSE": "close", "STOP": "stop"}.get(payload_up)
                    if cmd:
                        asyncio.run_coroutine_threadsafe(selve_manager.handle_command(parts[2], cmd, is_group=True), loop)
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

    def on_mqtt_connect_cb(connected: bool, reason_code):
        asyncio.run_coroutine_threadsafe(
            broadcast_status_update("mqtt_update", {"connected": connected}), 
            loop
        )

    def on_mqtt_disconnect_cb(reason_code):
        asyncio.run_coroutine_threadsafe(
            broadcast_status_update("mqtt_update", {"connected": False}), 
            loop
        )

    mqtt_client = MQTTClient(
        config,
        on_connect_cb=on_mqtt_connect_cb,
        on_disconnect_cb=on_mqtt_disconnect_cb,
        on_message_cb=on_mqtt_message
    )
    selve_manager = SelveManager(config, mqtt_client, loop, active_websockets)
    app.state.selve_manager = selve_manager
    app.state.mqtt_client = mqtt_client

    # --- Initialization Sequence ---
    try:
        await selve_manager.setup()
        await selve_manager.discover()
        mqtt_client.start()
        await selve_manager.publish_discovery()
    except Exception as e:
        logger.critical(f"Failed to initialize components: {e}", exc_info=True)
        if selve_manager.gateway:
            await selve_manager.gateway.stopWorker()
        sys.exit(1)

    # --- Periodic update task ---
    async def periodic_update():
        reconnecting = False
        try:
            while True:
                await asyncio.sleep(config.update_interval)
                try:
                    await selve_manager.update_all()
                    if reconnecting:
                        logger.info("Connection to Selve Gateway restored.")
                        reconnecting = False
                except Exception as e:
                    reconnecting = True
                    logger.error(f"Selve Gateway connection lost: {e}. Attempting reconnect...")
                    await broadcast_status_update("gateway_update", {"duty_cycle": 0, "duty_blocked": True})
                    
                    try:
                        if hasattr(selve_manager, 'gateway') and selve_manager.gateway:
                            try:
                                await selve_manager.gateway.stopWorker()
                            except Exception:
                                pass
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
    web_port = int(os.environ.get("WEB_PORT", config.web.port))
    web_host = os.environ.get("WEB_HOST", config.web.host)
    fastapi_task = asyncio.create_task(run_fastapi(web_host, web_port))

    stop_event = asyncio.Event()
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down...")

        # 1) Gracefully stop the uvicorn web server
        # Signal should_exit so it stops its internal loop naturally
        if _uvicorn_server is not None:
            _uvicorn_server.should_exit = True
            try:
                await asyncio.wait_for(fastapi_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                # If graceful shutdown times out, cancel the task
                if not fastapi_task.done():
                    fastapi_task.cancel()
                    try:
                        await fastapi_task
                    except (asyncio.CancelledError, Exception):
                        pass

        # 2) Gracefully stop the periodic update task
        if not periodic_task.done():
            periodic_task.cancel()
            try:
                await periodic_task
            except (asyncio.CancelledError, Exception):
                pass

        # 3) Stop Selve manager background workers
        if selve_manager:
            try:
                await selve_manager.shutdown()
            except Exception as e:
                logger.error(f"Error stopping Selve manager: {e}")

        # 4) Stop the gateway worker
        try:
            if selve_manager.gateway:
                await selve_manager.gateway.stopWorker()
        except Exception as e:
            logger.error(f"Error stopping Selve worker: {e}")

        # 5) Stop MQTT client
        mqtt_client.stop()

        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())

