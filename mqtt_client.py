import json
import logging
import paho.mqtt.client as mqtt
from typing import Dict, Any, Callable, Optional

from common import BaseComponent, setup_logger
from models import AppConfig, MQTTConfig

logger = setup_logger("selve2mqtt.mqtt")


class MQTTClient(BaseComponent):
    """
    MQTT client wrapping paho-mqtt for the selve2mqtt bridge.

    Expects an AppConfig (or dict-like) instance as 'config'.  When a
    fully-typed AppConfig is passed, all values are accessed as model
    attributes; otherwise falls back to dict-style access for backward
    compatibility.
    """

    def __init__(
        self,
        config: Any,
        on_connect_cb: Optional[Callable] = None,
        on_disconnect_cb: Optional[Callable] = None,
        on_message_cb: Optional[Callable] = None,
    ):
        # Let BaseComponent initialise the logger
        super().__init__(config)

        # Extract MQTT configuration – support both AppConfig/MQTTConfig objects and raw dicts
        if isinstance(config, AppConfig):
            mqtt_cfg: MQTTConfig = config.mqtt
            self.broker = mqtt_cfg.broker
            self.port = mqtt_cfg.port
            self.username = mqtt_cfg.username
            self.password = mqtt_cfg.password
            self.client_id = mqtt_cfg.client_id
            self.discovery_prefix = mqtt_cfg.discovery_prefix
        elif isinstance(config, MQTTConfig):
            self.broker = config.broker
            self.port = config.port
            self.username = config.username
            self.password = config.password
            self.client_id = config.client_id
            self.discovery_prefix = config.discovery_prefix
        else:
            # Legacy dict-style access
            mqtt_section = config.get('mqtt', {}) if isinstance(config, dict) else {}
            self.broker = mqtt_section.get('broker', getattr(config, 'broker', 'localhost'))
            self.port = mqtt_section.get('port', getattr(config, 'port', 1883))
            self.username = mqtt_section.get('username', getattr(config, 'username', ''))
            self.password = mqtt_section.get('password', getattr(config, 'password', ''))
            self.client_id = mqtt_section.get('client_id', getattr(config, 'client_id', 'selve2mqtt'))
            self.discovery_prefix = mqtt_section.get('discovery_prefix', getattr(config, 'discovery_prefix', 'homeassistant'))

        self.on_connect_cb = on_connect_cb
        self.on_disconnect_cb = on_disconnect_cb
        self.on_message_cb = on_message_cb

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        # Configure automatic reconnect delays (min=1s, max=120s)
        self.safe_execute(
            lambda: self.client.reconnect_delay_set(1, 120),
            exc_msg="Older paho version – reconnect_delay_set not available",
            raises=False
        )

    @property
    def is_connected(self) -> bool:
        return self.client.is_connected()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        connected = not reason_code.is_failure if hasattr(reason_code, 'is_failure') else (reason_code == 0)
        if connected:
            logger.info("MQTT connected. Sending online status.")
            self.publish("selve/status", "online", retain=True)
            client.subscribe("selve/#")
        else:
            logger.error(f"MQTT connection error: {reason_code}")

        if self.on_connect_cb:
            self.safe_execute(
                lambda: self.on_connect_cb(connected, reason_code),
                exc_msg="Error in on_connect callback",
                raises=False
            )

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        is_fail = reason_code.is_failure if hasattr(reason_code, 'is_failure') else (reason_code != 0)
        if is_fail:
            logger.warning("Unexpected MQTT disconnection (reason_code=%s), attempting reconnect", reason_code)
        else:
            logger.info("MQTT disconnected cleanly")

        if self.on_disconnect_cb:
            self.safe_execute(
                lambda: self.on_disconnect_cb(reason_code),
                exc_msg="Error in on_disconnect callback",
                raises=False
            )

    def on_message(self, client, userdata, msg):
        if self.on_message_cb:
            self.safe_execute(
                lambda: self.on_message_cb(client, userdata, msg),
                exc_msg=f"Error in on_message callback for {msg.topic}",
                raises=False
            )
        else:
            logger.debug("MQTT message received but no handler is set for topic %s", msg.topic)

    def start(self):
        if self.username:
            self.client.username_pw_set(self.username, self.password)

        # Last Will and Testament
        self.client.will_set("selve/status", "offline", retain=True)

        self.safe_execute(
            lambda: (self.client.connect(self.broker, self.port, 60),
                     self.client.loop_start()),
            exc_msg="Failed to connect to MQTT broker",
            raises=False
        )

    def publish(self, topic: str, payload: Any, retain: bool = False):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload)
        self.safe_execute(
            lambda: self.client.publish(topic, payload, retain=retain),
            exc_msg=f"Failed to publish MQTT message to {topic}",
            raises=False
        )

    def stop(self):
        self.safe_execute(lambda: self.publish("selve/status", "offline", retain=True), raises=False)
        self.safe_execute(lambda: self.client.loop_stop(), raises=False)
        self.safe_execute(lambda: self.client.disconnect(), raises=False)
