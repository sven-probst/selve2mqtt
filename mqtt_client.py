import json
import logging
import paho.mqtt.client as mqtt
from typing import Dict, Any, Callable, Optional

from common import BaseComponent, setup_logger

logger = setup_logger("selve2mqtt.mqtt")

class MQTTClient(BaseComponent):
    def __init__(self, config: Dict[str, Any], on_connect_cb=None, on_disconnect_cb=None, on_message_cb=None):
        # Let BaseComponent initialise the logger; store config references.
        super().__init__(config)
        self.broker = config['mqtt']['broker']
        self.port = config['mqtt'].get('port', 1883)
        self.username = config['mqtt'].get('username', '')
        self.password = config['mqtt'].get('password', '')
        self.client_id = config['mqtt'].get('client_id', 'selve2mqtt')
        self.discovery_prefix = config['mqtt'].get('discovery_prefix', 'homeassistant')

        self.on_connect_cb = on_connect_cb
        self.on_disconnect_cb = on_disconnect_cb
        self.on_message_cb = on_message_cb

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        # Configure automatic reconnect delays (min, max)
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
