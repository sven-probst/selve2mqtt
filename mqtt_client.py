import json
import logging
import ssl
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
            # TLS settings
            self.tls_enabled = mqtt_cfg.tls_enabled
            self.tls_ca_certs = mqtt_cfg.tls_ca_certs
            self.tls_certfile = mqtt_cfg.tls_certfile
            self.tls_keyfile = mqtt_cfg.tls_keyfile
            self.tls_keyfile_password = mqtt_cfg.tls_keyfile_password
            self.tls_insecure = mqtt_cfg.tls_insecure
            self.tls_version = mqtt_cfg.tls_version
        elif isinstance(config, MQTTConfig):
            self.broker = config.broker
            self.port = config.port
            self.username = config.username
            self.password = config.password
            self.client_id = config.client_id
            self.discovery_prefix = config.discovery_prefix
            # TLS settings
            self.tls_enabled = getattr(config, 'tls_enabled', False)
            self.tls_ca_certs = getattr(config, 'tls_ca_certs', None)
            self.tls_certfile = getattr(config, 'tls_certfile', None)
            self.tls_keyfile = getattr(config, 'tls_keyfile', None)
            self.tls_keyfile_password = getattr(config, 'tls_keyfile_password', None)
            self.tls_insecure = getattr(config, 'tls_insecure', False)
            self.tls_version = getattr(config, 'tls_version', 'auto')
        else:
            # Legacy dict-style access
            mqtt_section = config.get('mqtt', {}) if isinstance(config, dict) else {}
            self.broker = mqtt_section.get('broker', getattr(config, 'broker', 'localhost'))
            self.port = mqtt_section.get('port', getattr(config, 'port', 1883))
            self.username = mqtt_section.get('username', getattr(config, 'username', ''))
            self.password = mqtt_section.get('password', getattr(config, 'password', ''))
            self.client_id = mqtt_section.get('client_id', getattr(config, 'client_id', 'selve2mqtt'))
            self.discovery_prefix = mqtt_section.get('discovery_prefix', getattr(config, 'discovery_prefix', 'homeassistant'))
            # TLS settings from dict
            self.tls_enabled = mqtt_section.get('tls_enabled', False)
            self.tls_ca_certs = mqtt_section.get('tls_ca_certs', None)
            self.tls_certfile = mqtt_section.get('tls_certfile', None)
            self.tls_keyfile = mqtt_section.get('tls_keyfile', None)
            self.tls_keyfile_password = mqtt_section.get('tls_keyfile_password', None)
            self.tls_insecure = mqtt_section.get('tls_insecure', False)
            self.tls_version = mqtt_section.get('tls_version', 'auto')

        self.on_connect_cb = on_connect_cb
        self.on_disconnect_cb = on_disconnect_cb
        self.on_message_cb = on_message_cb

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id
        )
        # Bound the outgoing message queue so a broker outage cannot let
        # retained/periodic publishes pile up in memory (default is unbounded).
        try:
            self.client.max_queued_messages_set(1000)
        except (AttributeError, ValueError):
            logger.warning("Older paho version – max_queued_messages_set not available")
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

        # TLS / SSL configuration
        if self.tls_enabled:
            self._setup_tls()

        self.safe_execute(
            lambda: (self.client.connect(self.broker, self.port, 60),
                     self.client.loop_start()),
            exc_msg="Failed to connect to MQTT broker",
            raises=False
        )

    def _setup_tls(self):
        """Configure TLS/SSL on the paho MQTT client."""
        # Map string version identifiers to ssl constants
        tls_version_map = {
            "auto": None,  # Let paho / OpenSSL negotiate
            "tlsv1_2": ssl.PROTOCOL_TLSv1_2,
            "tlsv1_3": ssl.PROTOCOL_TLS,
        }
        tls_proto = tls_version_map.get(self.tls_version)

        try:
            self.client.tls_set(
                ca_certs=self.tls_ca_certs,
                certfile=self.tls_certfile,
                keyfile=self.tls_keyfile,
                keyfile_password=self.tls_keyfile_password,
                tls_version=tls_proto,
                # ciphers=None → use secure defaults
            )
            logger.info(
                "TLS enabled (ca_certs=%s, certfile=%s, insecure=%s)",
                self.tls_ca_certs or "system",
                self.tls_certfile or "none",
                self.tls_insecure,
            )
        except FileNotFoundError as e:
            logger.error("TLS certificate file not found: %s", e)
            raise
        except ssl.SSLError as e:
            logger.error("TLS configuration error: %s", e)
            raise

        if self.tls_insecure:
            self.client.tls_insecure_set(True)
            logger.warning(
                "TLS hostname verification disabled (tls_insecure=true) – "
                "use this only for testing or with self-signed certificates"
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

