import json
import logging
import paho.mqtt.client as mqtt
from typing import Dict, Any

logger = logging.getLogger("selve2mqtt.mqtt")

class MQTTClient:
    def __init__(self, config: Dict[str, Any]):
        self.broker = config['mqtt']['broker']
        self.port = config['mqtt'].get('port', 1883)
        self.username = config['mqtt'].get('username', '')
        self.password = config['mqtt'].get('password', '')
        self.client_id = config['mqtt'].get('client_id', 'selve2mqtt')
        self.discovery_prefix = config['mqtt'].get('discovery_prefix', 'homeassistant')

        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self.on_connect
        # Provide sensible defaults for other callbacks
        self.client.on_message = self._on_message_placeholder
        self.client.on_disconnect = self.on_disconnect
        # Configure automatic reconnect delays (min, max)
        try:
            self.client.reconnect_delay_set(1, 120)
        except Exception:
            # Older paho versions may not have reconnect_delay_set
            pass

    def _on_message_placeholder(self, client, userdata, msg):
        logger.debug("MQTT message received but no handler is set for topic %s", msg.topic)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT connected. Sending online status.")
            self.publish("selve/status", "online", retain=True)
            client.subscribe("selve/#")
        else:
            logger.error(f"MQTT connection error: {rc}")

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning("Unexpected MQTT disconnection (rc=%s), attempting reconnect", rc)
        else:
            logger.info("MQTT disconnected cleanly")

    def start(self):
        if self.username:
            self.client.username_pw_set(self.username, self.password)

        # Last Will and Testament
        self.client.will_set("selve/status", "offline", retain=True)

        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            logger.exception("Failed to connect to MQTT broker: %s", e)

    def publish(self, topic: str, payload: Any, retain: bool = False):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload)
        try:
            # Use QoS=0 by default; callers may change if needed
            self.client.publish(topic, payload, retain=retain)
        except Exception as e:
            logger.exception("Failed to publish MQTT message to %s: %s", topic, e)

    def stop(self):
        try:
            self.publish("selve/status", "offline", retain=True)
        except Exception:
            pass
        try:
            self.client.loop_stop()
        except Exception:
            pass
        try:
            self.client.disconnect()
        except Exception:
            pass
