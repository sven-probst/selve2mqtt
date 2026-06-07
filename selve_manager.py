import asyncio
import logging
import json
import urllib.request
from dataclasses import dataclass, asdict, replace
from typing import Dict, Any, Set, Optional, List, Union
from selve import Selve
from selve.util.protocol import MovementState
from translations import TRANSLATIONS

logger = logging.getLogger("selve2mqtt.selve")

# Maximum number of bytes allowed for device/group/sensor labels (UTF-8)
LABEL_MAX_BYTES = 23

# Spec Page 31: Mapping Selve configuration IDs to HA cover device classes
DEVICE_CLASS_MAP = {1: "shutter", 2: "blind", 3: "awning", 4: "shutter", 5: "shutter", 6: "shutter", 7: "shutter", 10: "shutter"}

# Sensor metadata mapping: (HA class, unit, icon, i18n_key)
SENSOR_META_MAP = {
    1: ("wind_speed", "m/s", "mdi:weather-windy", "wind"),
    2: ("moisture", "", "mdi:weather-rainy", "rain"),
    3: ("illuminance", "lx", "mdi:brightness-5", "light"),
    4: ("temperature", "°C", "mdi:thermometer", "temp")
}

# Map Selve attribute names to HA attribute keys (Spec Page 32)
ATTR_LOOKUP = {
    "automaticMode": "automatic_mode", "unreachable": "unreachable", "value": "selve_raw_value",
    "overload": "overload", "obstructed": "obstructed", "windAlarm": "alarm_wind",
    "rainAlarm": "alarm_rain", "freezingAlarm": "alarm_frost"
}

# Map MQTT commands to Selve library method names (Command Pattern)
DEVICE_COMMANDS = {
    "open": "move_up",
    "close": "move_down",
    "stop": "stop",
    "pos1": "move_intermediate_pos1",
    "pos2": "move_intermediate_pos2",
}

class SelveLogger:
    """Helper to handle translated logging automatically."""
    def __init__(self, logger: logging.Logger, translations: Dict[str, str], fallback: Optional[Dict[str, str]] = None):
        self._logger = logger
        self._translations = translations
        self._fallback = fallback or {}

    def _log(self, level: int, key: str, **kwargs):
        template = self._translations.get(key, self._fallback.get(key, key))
        try:
            message = template.format(**kwargs)
        except Exception:
            message = template
        self._logger.log(level, message)

    def info(self, key: str, **kwargs): self._log(logging.INFO, key, **kwargs)
    def warning(self, key: str, **kwargs): self._log(logging.WARNING, key, **kwargs)
    def error(self, key: str, **kwargs): self._log(logging.ERROR, key, **kwargs)

@dataclass(frozen=True)
class DeviceState:
    position: Optional[int]
    moving: bool
    name: str
    unreachable: bool
    obstructed: bool
    overload: bool
    auto_mode: bool

@dataclass(frozen=True)
class GroupState:
    name: str
    device_ids: List[str]

@dataclass(frozen=True)
class SensorState:
    value: Union[int, float, str]
    type: str
    unit: str
    name: str

@dataclass(frozen=True)
class GatewayState:
    duty_cycle: int
    duty_blocked: bool
    hardware: str
    firmware: str
    latest_firmware: str
    serial_number: str = "Unknown"

class SelveManager:
    def __init__(self, config: Dict[str, Any], mqtt_client, loop: asyncio.AbstractEventLoop, active_websockets: Optional[Set] = None):
        self.config = config
        self.mqtt = mqtt_client
        self.loop = loop
        self.active_websockets = active_websockets if active_websockets is not None else set()
        self.gateway: Any = None
        self.devices: Dict[str, Any] = {}
        self.groups: Dict[str, Any] = {}
        self.sensors: Dict[str, Any] = {}
        self.senders: Dict[str, Any] = {}
        self.open_close_fix = config['selve'].get('open_close_fix', False)
        self._state_cache: Dict[str, Any] = {}
        self._keepalive_task: Optional[asyncio.Task] = None
        self.lang_code = config.get('language', 'en')
        self.i18n = TRANSLATIONS.get(self.lang_code, TRANSLATIONS['en'])
        self.log = SelveLogger(
            logger,
            self.i18n.get('logs', {}),
            fallback=TRANSLATIONS.get('en', {}).get('logs', {})
        )

    async def setup(self):
        port = self.config['selve'].get('port')
        self.gateway = Selve(port=port) if port else Selve()

        if hasattr(self.gateway, '_LOGGER') and self.gateway._LOGGER is None:
            self.gateway._LOGGER = logging.getLogger("selve.lib")

        try:
            await self.gateway.setup()
            # Attempt to retrieve firmware info; this is non-fatal for the overall setup process
            await self.check_firmware()
            # Force initial gateway state update to ensure values are available
            await self._refresh_gateway_state()
            self.gateway.register_callback(self.on_device_update)
            # Start keepalive task to prevent 60s idle reconnect
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            self.log.info('gw_init', port=port if port else 'Auto-Discovery')
        except Exception as e:
            self.log.error('err_gw_setup', e=str(e))
            raise e

    async def _keepalive_loop(self):
        """Sends a ping every 45s to prevent the 60s idle-reconnect in serial_transport."""
        while True:
            try:
                await asyncio.sleep(45)
                await self.gateway.pingGateway()
                logger.debug("Keepalive ping sent")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Keepalive ping failed: {e}")

    async def discover(self):
        self.log.info('discovery_start')
        await self.gateway.discover()
        await asyncio.sleep(3)

        raw_devs = getattr(self.gateway, 'devices', {})
        raw_grps = getattr(self.gateway, 'groups', {})
        raw_sens = getattr(self.gateway, 'sensors', {})

        def flatten_entities(raw_dict):
            """Extracts entities indexed by ID, looking into namespace sub-dicts if necessary."""
            entities = {}
            if not isinstance(raw_dict, dict): return entities
            for k, v in raw_dict.items():
                if str(k).isdigit():
                    entities[str(k)] = v
                elif isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        if str(sub_k).isdigit():
                            entities[str(sub_k)] = sub_v
            return entities

        self.devices = flatten_entities(raw_devs)
        self.groups = flatten_entities(raw_grps)
        self.sensors = flatten_entities(raw_sens)
        
        # Explicitly load senders if method exists (python-selve-new API)
        try:
            if hasattr(self.gateway, 'getSenderIds'):
                sender_ids = await self.gateway.getSenderIds()
                self.senders = {}
                for sid in sender_ids:
                    try:
                        sender_info = await self.gateway.getSenderInfo(sid)
                        self.senders[str(sid)] = sender_info
                    except Exception as e:
                        logger.warning(f"Could not load sender {sid}: {e}")
                        self.senders[str(sid)] = {'id': sid, 'name': f'Sender {sid}'}
            else:
                # Fallback: try to get from gateway attribute
                raw_senders = getattr(self.gateway, 'senders', {})
                self.senders = flatten_entities(raw_senders)
        except Exception as e:
            logger.warning(f"Sender discovery failed: {e}")
            self.senders = {}

        self.log.info('discovery_done', devices=len(self.devices), groups=len(self.groups), sensors=len(self.sensors), senders=len(self.senders))

    def _get_attr(self, obj, attr, default=None):
        """Helper to safely get an attribute from an object or a key from a dictionary."""
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    def _get_sensor_metadata(self, sens) -> dict:
        """Returns metadata based on sensor type for icons and units."""
        # Default values
        meta = {"device_class": None, "unit": "", "icon": "mdi:sensor", "type_name": "Generic"}
        sens_type = self._get_attr(sens, 'type')

        if sens_type in SENSOR_META_MAP:
            ha_class, unit, icon, i18n_key = SENSOR_META_MAP[sens_type]
            # Use the translation map for the type name, with a fallback
            meta.update({
                "device_class": ha_class,
                "unit": unit,
                "icon": icon,
                "type_name": self.i18n['sensors'].get(i18n_key, i18n_key.capitalize())
            })

        return meta

    def _to_ha_position(self, selve_value):
        try:
            val = int(selve_value)
        except (ValueError, TypeError):
            return None

        ha = 100 - val
        if self.open_close_fix:
            if ha <= 1: ha = 0
            elif ha >= 99: ha = 100
        return ha

    def _to_selve_position(self, ha_value: int) -> int:
        return 100 - ha_value

    def _get_device_properties(self, device) -> DeviceState:
        """Extracts standard properties from a Selve device object."""
        selve_raw = self._get_attr(device, 'value', 0)
        dev_id = self._get_attr(device, 'id', self._get_attr(device, 'channel', 'unknown'))
        return DeviceState(
            position=self._to_ha_position(selve_raw),
            moving=getattr(device, 'state', None) in (MovementState.UP_ON, MovementState.DOWN_ON),
            name=self._get_attr(device, 'name', f"Aktor {dev_id}"),
            unreachable=self._get_attr(device, 'unreachable', False),
            obstructed=self._get_attr(device, 'obstructed', False),
            overload=self._get_attr(device, 'overload', False),
            auto_mode=self._get_attr(device, 'automaticMode', False)
        )

    def _get_group_properties(self, group) -> GroupState:
        """Extracts properties from a Selve group object for the UI."""
        grp_id = self._get_attr(group, 'id', self._get_attr(group, 'channel', 'unknown'))
        
        # Extract device IDs from the group's device collection (dict or list)
        dev_coll = self._get_attr(group, 'devices', {})
        if isinstance(dev_coll, dict):
            device_ids = [str(self._get_attr(d, 'id')) for d in dev_coll.values()]
        else:
            device_ids = [str(self._get_attr(d, 'id')) for d in dev_coll]
            
        return GroupState(
            name=self._get_attr(group, 'name', f"Gruppe {grp_id}"),
            device_ids=device_ids
        )

    def _get_sensor_properties(self, sensor) -> SensorState:
        """Extracts properties from a Selve sensor object for the UI."""
        meta = self._get_sensor_metadata(sensor)
        sens_id = self._get_attr(sensor, 'id', self._get_attr(sensor, 'channel', 'unknown'))
        return SensorState(
            value=self._get_attr(sensor, 'value', 'unknown'),
            type=meta["type_name"],
            unit=meta["unit"],
            name=self._get_attr(sensor, 'name', f"Sensor {sens_id}")
        )

    def _get_sender_properties(self, sender) -> dict:
        """Extracts properties from a Selve sender object for the UI."""
        sender_id = self._get_attr(sender, 'id', self._get_attr(sender, 'channel', 'unknown'))
        return {
            "id": str(sender_id),
            "name": self._get_attr(sender, 'name', f"Sender {sender_id}"),
            "last_event": self._get_attr(sender, 'lastEvent', 0)
        }

    def get_gateway_state(self) -> GatewayState:
        """Returns the diagnostic state of the gateway."""
        return GatewayState(
            duty_cycle=self._state_cache.get("gw_duty_cycle", 0),
            duty_blocked=self._state_cache.get("gw_duty_blocked", False),
            hardware=self._state_cache.get("gw_hardware", "N/A"),
            firmware=self._state_cache.get("gw_firmware", "N/A"),
            latest_firmware=self._state_cache.get("gw_latest_firmware", "N/A"),
            serial_number=self._state_cache.get("gw_serial", "Unknown")
        )

    def get_full_state(self):
        """Builds the complete system state for the initial UI load."""
        gw_state = self.get_gateway_state()
        result = {
            "type": "full_state",
            "devices": {d_id: asdict(self._get_device_properties(d)) for d_id, d in self.devices.items()},
            "groups": {g_id: asdict(self._get_group_properties(g)) for g_id, g in self.groups.items()},
            "sensors": {s_id: asdict(self._get_sensor_properties(s)) for s_id, s in self.sensors.items()},
            "senders": {s_id: self._get_sender_properties(s) for s_id, s in self.senders.items()},
            "gateway": asdict(gw_state)
        }
        logger.debug(f"Full state gateway: HW={gw_state.hardware}, FW={gw_state.firmware}, Serial={gw_state.serial_number}")
        return result

    async def publish_discovery(self):
        for dev_id, dev in self.devices.items():
            # CRITICAL DEBUG: Print raw device info to see why it's detected as IVEO
            logger.debug(f"DEBUG_START: Analyzing device {dev_id}")
            logger.debug(f"DEBUG: Class: {dev.__class__.__name__}")
            logger.debug(f"DEBUG: Attributes: {dir(dev)}")
            if hasattr(dev, '__dict__'): logger.debug(f"DEBUG: Dict: {dev.__dict__}")

            # Better bidirectional detection (Commeo = 1)

            comm_type = self._get_attr(dev, 'communication_type')
            if comm_type is None:
                comm_type = self._get_attr(dev, 'communicationType')
            if comm_type is None:
                comm_type = self._get_attr(dev, 'comm_type', 1)
            
            # Ensure comm_type is an integer value, as it might be an enum object
            comm_type_int = 1 # Default to 1 (Commeo) if we can't determine
            if comm_type is not None:
                if hasattr(comm_type, 'value'): # Common for enum-like objects
                    comm_type_int = comm_type.value
                elif isinstance(comm_type, (int, str)): # Already an int or string representation
                    comm_type_int = int(comm_type)
            
            # Robust detection: check enum value and class name fallback
            comm_str = str(comm_type).upper()
            logger.debug(f"DEBUG: comm_type string: {comm_str}")
            is_bidir = ("COMMEO" in comm_str) or ("Commeo" in dev.__class__.__name__)
            
            # If string detection fails, use the numeric value from your log (Commeo=0)
            if not is_bidir and comm_type_int is not None:
                # Your log showed COMMEO: 0, Spec usually says 1. We check both.
                logger.debug(f"DEBUG: comm_type_int: {comm_type_int}")
                is_bidir = (comm_type_int == 0)

            config_val = self._get_attr(dev, 'device_sub_type', self._get_attr(dev, 'device_type', self._get_attr(dev, 'config', 1)))
            if hasattr(config_val, 'value'):
                config_val = config_val.value

            friendly_name = self._get_attr(dev, 'name', f"Selve {dev_id}")
            topic = f"{self.mqtt.discovery_prefix}/cover/selve_{dev_id}/config"
            logger.debug(f"DEBUG: Device {dev_id} detected as {'COMMEO' if is_bidir else 'IVEO'}")

            bridge_info = {
                "identifiers": ["selve_gateway"],
                "name": "Selve Gateway",
                "manufacturer": "Selve"
            }

            cfg = {
                "name": None,
                "object_id": f"selve_{dev_id}",
                "unique_id": f"selve_device_{dev_id}",
                "command_topic": f"selve/{dev_id}/set",
                "availability_topic": "selve/status",
                "payload_available": "online",
                "payload_not_available": "offline",
                "optimistic": not is_bidir,
                "device_class": DEVICE_CLASS_MAP.get(config_val, "shutter"),
                "device": {
                    "identifiers": [f"selve_{dev_id}"],
                    "name": friendly_name,
                    "manufacturer": "Selve",
                    "model": "Commeo" if is_bidir else "Iveo",
                    "via_device": "selve_gateway"
                },
                "json_attributes_topic": f"selve/{dev_id}/attributes"
            }

            if is_bidir:
                cfg.update({
                    "position_topic": f"selve/{dev_id}/position",
                    "set_position_topic": f"selve/{dev_id}/position/set",
                    "position_open": 100,
                    "position_closed": 0
                })

                # Connectivity (Unreachable) Sensor Discovery
                unreach_topic = f"{self.mqtt.discovery_prefix}/binary_sensor/selve_{dev_id}_unreachable/config"
                unreach_cfg = {
                    "name": f"{friendly_name} Connectivity",
                    "unique_id": f"selve_device_{dev_id}_unreachable",
                    "state_topic": f"selve/{dev_id}/unreachable",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "device_class": "connectivity",
                    "entity_category": "diagnostic",
                    "device": cfg["device"]
                }
                self.mqtt.publish(unreach_topic, unreach_cfg, retain=True)

            self.mqtt.publish(topic, cfg, retain=True)

            # Programmatic attribute collection
            attrs = {ha_key: self._get_attr(dev, selve_key, False) for selve_key, ha_key in ATTR_LOOKUP.items()}

            # DayMode (Spec Page 32): 1=Night, 2=Dawn, 3=Day, 4=Dusk
            day_mode = self._get_attr(dev, 'dayMode', 0)
            day_mode_map = {1: "Night", 2: "Dawn", 3: "Day", 4: "Dusk"}
            if day_mode in day_mode_map:
                attrs["day_mode"] = day_mode_map[day_mode]
            self.mqtt.publish(f"selve/{dev_id}/attributes", attrs, retain=True)
            await self._publish_state(dev_id)

        # Discovery for Groups
        for grp_id, grp in self.groups.items():
            friendly_name = getattr(grp, 'name', f"Selve Gruppe {grp_id}")
            topic = f"{self.mqtt.discovery_prefix}/cover/selve_group_{grp_id}/config"

            cfg = {
                "name": friendly_name,
                "object_id": f"selve_group_{grp_id}",
                "unique_id": f"selve_group_{grp_id}",
                "command_topic": f"selve/group/{grp_id}/set",
                "availability_topic": "selve/status",
                "payload_available": "online",
                "payload_not_available": "offline",
                "optimistic": True, # Groups usually don't provide reliable state feedback
                "device_class": "shutter",
                "device": {
                    "identifiers": [f"selve_group_{grp_id}"],
                    "name": friendly_name,
                    "manufacturer": "Selve",
                    "model": "Group",
                    "via_device": "selve_gateway"
                }
            }
            # Selve groups support basic commands and often position (though results vary)
            cfg["set_position_topic"] = f"selve/group/{grp_id}/position/set"

            self.mqtt.publish(topic, cfg, retain=True)

        # Discovery for Sensors
        for sens_id, sens in self.sensors.items():
            friendly_name = getattr(sens, 'name', f"Selve Sensor {sens_id}")
            meta = self._get_sensor_metadata(sens)

            topic = f"{self.mqtt.discovery_prefix}/sensor/selve_sens_{sens_id}/config"
            cfg = {
                "name": friendly_name,
                "unique_id": f"selve_sensor_{sens_id}",
                "state_topic": f"selve/sensor/{sens_id}/state",
                "availability_topic": "selve/status",
                "device_class": meta["device_class"],
                "unit_of_measurement": meta["unit"],
                "icon": meta["icon"],
                "device": {
                    "identifiers": [f"selve_sens_{sens_id}"],
                    "name": friendly_name,
                    "manufacturer": "Selve",
                    "via_device": "selve_gateway"
                }
            }
            self.mqtt.publish(topic, cfg, retain=True)

        # Discovery for Senders (Remote Controls)
        for sender_id, sender in self.senders.items():
            if not sender:
                continue
            friendly_name = self._get_attr(sender, 'name', f"Remote {sender_id}")
            sender_type = self._get_attr(sender, 'type', 'Unknown')
            
            # Main sender entity (event sensor)
            topic = f"{self.mqtt.discovery_prefix}/sensor/selve_sender_{sender_id}/config"
            cfg = {
                "name": f"{friendly_name}",
                "unique_id": f"selve_sender_{sender_id}",
                "state_topic": f"selve/sender/{sender_id}/state",
                "availability_topic": "selve/status",
                "icon": "mdi:remote",
                "device": {
                    "identifiers": [f"selve_sender_{sender_id}"],
                    "name": friendly_name,
                    "manufacturer": "Selve",
                    "model": f"Remote Control ({sender_type})",
                    "via_device": "selve_gateway"
                }
            }
            self.mqtt.publish(topic, cfg, retain=True)

        # Gateway level diagnostics and settings
        self._publish_gateway_discovery()
        self.mqtt.publish("selve/status", "online", retain=True)
        
        # Publish initial gateway state values so entities don't show "unknown"
        gw_state = self.get_gateway_state()
        self.mqtt.publish("selve/gateway/duty_cycle", gw_state.duty_cycle, retain=True)
        self.mqtt.publish("selve/gateway/duty_cycle_blocked", "ON" if gw_state.duty_blocked else "OFF", retain=True)

    def _publish_gateway_discovery(self):
        """Publishes MQTT discovery for gateway-level settings as switches."""
        # LED Switch
        led_topic = f"{self.mqtt.discovery_prefix}/switch/selve_gateway_led/config"
        self.mqtt.publish(led_topic, {
            "name": "Gateway LED",
            "unique_id": "selve_gateway_led",
            "command_topic": "selve/gateway/led/set",
            "state_topic": "selve/gateway/led/state",
            "icon": "mdi:led-on",
            "device": {"identifiers": ["selve_gateway"], "name": "Selve Gateway", "manufacturer": "Selve"}
        }, retain=True)

        # Forwarding Switch
        fwd_topic = f"{self.mqtt.discovery_prefix}/switch/selve_gateway_forward/config"
        self.mqtt.publish(fwd_topic, {
            "name": "Commeo Forwarding",
            "unique_id": "selve_gateway_forward",
            "command_topic": "selve/gateway/forward/set",
            "state_topic": "selve/gateway/forward/state",
            "icon": "mdi:router-wireless",
            "device": {"identifiers": ["selve_gateway"], "name": "Selve Gateway", "manufacturer": "Selve"}
        }, retain=True)

        # Duty Cycle Sensor
        dc_topic = f"{self.mqtt.discovery_prefix}/sensor/selve_gateway_duty_cycle/config"
        self.mqtt.publish(dc_topic, {
            "name": "Gateway Duty Cycle",
            "unique_id": "selve_gateway_duty_cycle",
            "state_topic": "selve/gateway/duty_cycle",
            "unit_of_measurement": "%",
            "entity_category": "diagnostic",
            "device": {"identifiers": ["selve_gateway"], "name": "Selve Gateway", "manufacturer": "Selve"}
        }, retain=True)

        # Duty Cycle Blocked Binary Sensor
        dcb_topic = f"{self.mqtt.discovery_prefix}/binary_sensor/selve_gateway_duty_blocked/config"
        self.mqtt.publish(dcb_topic, {
            "name": "Gateway Duty Cycle Blocked",
            "unique_id": "selve_gateway_duty_blocked",
            "state_topic": "selve/gateway/duty_cycle_blocked",
            "payload_on": "ON",
            "payload_off": "OFF",
            "device_class": "problem",
            "entity_category": "diagnostic",
            "device": {"identifiers": ["selve_gateway"], "name": "Selve Gateway", "manufacturer": "Selve"}
        }, retain=True)

    async def set_gateway_led(self, enabled: bool):
        """Toggles the physical LED according to Spec Page 17."""
        try:
            mode = 1 if enabled else 0
            logger.info(f"Setting Gateway LED to {'ON' if enabled else 'OFF'}")
            await self.gateway.setLED(mode)
            self.mqtt.publish("selve/gateway/led/state", "ON" if enabled else "OFF", retain=True)
            return True
        except Exception as e:
            logger.error(f"Failed to set LED: {e}")
            return False

    async def set_gateway_forwarding(self, enabled: bool):
        """Toggles Commeo Forwarding according to Spec Page 19."""
        try:
            mode = 1 if enabled else 0
            logger.info(f"Setting Commeo Forwarding to {'ON' if enabled else 'OFF'}")
            await self.gateway.setForward(mode)
            self.mqtt.publish("selve/gateway/forward/state", "ON" if enabled else "OFF", retain=True)
            return True
        except Exception as e:
            logger.error(f"Failed to set Forwarding: {e}")
            return False

    def on_device_update(self, device=None, *args):
        """Entry point for Selve library callbacks.

        Note: python-selve-new calls callback() without arguments.
        We therefore iterate all known devices to detect state changes.
        """
        self._process_gateway_events()
        if device:
            # Direct device passed (future-proof)
            self._process_entity_update(device)
        else:
            # No device passed: poll all known devices for state changes
            for dev_obj in list(self.devices.values()):
                self._process_entity_update(dev_obj)
            for grp_obj in list(self.groups.values()):
                self._process_entity_update(grp_obj)

    def _process_gateway_events(self):
        """Handles Duty Cycle and Log events from the gateway."""
        # Duty Cycle (Spec Page 74)
        duty_val = getattr(self.gateway, 'duty_cycle', None)
        duty_blocked = getattr(self.gateway, 'duty_cycle_blocked', None)

        if duty_val is not None:
            if (duty_val != self._state_cache.get("gw_duty_cycle") or
                duty_blocked != self._state_cache.get("gw_duty_blocked")):

                self._state_cache.update({"gw_duty_cycle": duty_val, "gw_duty_blocked": duty_blocked})
                status_key = 'status_blocked' if duty_blocked else 'status_ok'
                status_str = self.i18n.get('logs', {}).get(status_key, status_key.upper())

                self.log.info('duty_cycle_event', duty=duty_val, status=status_str)
                self.mqtt.publish("selve/gateway/duty_cycle", duty_val, retain=True)
                self.mqtt.publish("selve/gateway/duty_cycle_blocked", "ON" if duty_blocked else "OFF", retain=True)

                if self.active_websockets:
                    asyncio.run_coroutine_threadsafe(self.broadcast_gateway_ws(duty_val, duty_blocked), self.loop)

        # Gateway Logs (Spec Page 73)
        log_desc = getattr(self.gateway, 'last_log_description', None)
        if log_desc:
            log_type = getattr(self.gateway, 'last_log_type', 0)
            log_code = getattr(self.gateway, 'last_log_code', 'unknown')
            log_msg = f"GATEWAY LOG [Code {log_code}]: {log_desc}"

            if log_type == 2: self.log.error(log_msg)
            elif log_type == 1: self.log.warning(log_msg)
            else: self.log.info(log_msg)

            self.mqtt.publish("selve/gateway/last_log", {"type": log_type, "code": log_code, "message": log_desc}, retain=False)
            self.gateway.last_log_description = None

    def _process_entity_update(self, device):
        """Delegates updates to either sensor or device processors."""
        dev_id = str(device.id)
        try:
            if dev_id in self.sensors:
                val = getattr(device, 'value', 'unknown')
                self.mqtt.publish(f"selve/sensor/{dev_id}/state", val, retain=True)
                if self.active_websockets:
                    asyncio.run_coroutine_threadsafe(self.broadcast_sensor_ws(device, val), self.loop)
            elif dev_id in self.senders:
                self._handle_sender_update(device)
            elif dev_id in self.devices:
                self._handle_device_state_change(device)
        except Exception as e:
            self.log.error(f"Entity update error for {dev_id}: {e}")

    def _handle_sender_update(self, sender):
        """Processes incoming sender events."""
        sender_id = str(self._get_attr(sender, 'id'))
        last_event = self._get_attr(sender, 'lastEvent', 0)
        self.mqtt.publish(f"selve/sender/{sender_id}/state", last_event, retain=True)
        if self.active_websockets:
            asyncio.run_coroutine_threadsafe(self.broadcast_sender_ws(sender_id, last_event), self.loop)

    async def broadcast_sender_ws(self, sender_id, event_code):
        for ws in list(self.active_websockets):
            try:
                await ws.send_json({"type": "sender_update", "id": sender_id, "event": event_code})
            except Exception: pass

    def _handle_device_state_change(self, device):
        """Processes changes in device state, logging and publishing as needed."""
        dev_id = str(device.id)
        current_state = self._get_device_properties(device)
        old_state = self._state_cache.get(dev_id)

        if old_state == current_state:
            return

        if old_state and old_state.unreachable != current_state.unreachable:
            log_key = 'device_unreachable' if current_state.unreachable else 'device_online'
            self.log.warning(log_key, name=current_state.name, id=dev_id) if current_state.unreachable else self.log.info(log_key, name=current_state.name, id=dev_id)

        self._state_cache[dev_id] = current_state
        props_dict = asdict(current_state)

        # Publish MQTT
        if current_state.position is not None:
            self.mqtt.publish(f"selve/{dev_id}/position", current_state.position, retain=True)
        self.mqtt.publish(f"selve/{dev_id}/unreachable", "OFF" if current_state.unreachable else "ON", retain=True)
        self.mqtt.publish(f"selve/{dev_id}/state", props_dict, retain=True)

        self.log.info('update_received', id=dev_id, pos=current_state.position)
        if self.active_websockets:
            asyncio.run_coroutine_threadsafe(self.broadcast_ws(dev_id, **props_dict), self.loop)

    async def broadcast_ws(self, dev_id, position, moving, unreachable, obstructed, overload, **kwargs):
        for ws in list(self.active_websockets):
            try:
                await ws.send_json({
                    "type": "device_update",
                    "id": dev_id,
                    "position": position,
                    "moving": moving,
                    "unreachable": unreachable,
                    "obstructed": obstructed,
                    "overload": overload
                })
            except Exception:
                pass

    async def broadcast_gateway_ws(self, duty_cycle, duty_blocked):
        """Sends gateway diagnostics updates to all connected web clients."""
        for ws in list(self.active_websockets):
            try:
                await ws.send_json({
                    "type": "gateway_update",
                    "duty_cycle": duty_cycle,
                    "duty_blocked": duty_blocked
                })
            except Exception:
                pass

    async def broadcast_sensor_ws(self, sensor, value):
        sens_id = str(sensor.id)
        meta = self._get_sensor_metadata(sensor)
        for ws in list(self.active_websockets):
            try:
                await ws.send_json({
                    "type": "sensor_update",
                    "id": sens_id,
                    "value": value,
                    "unit": meta["unit"]
                })
            except Exception:
                pass

    async def _refresh_gateway_state(self):
        """Refresh gateway state from library-maintained cache.
        
        The python-selve-new library automatically updates these attributes
        when duty cycle events are received from the gateway.
        """
        try:
            # Use cached values maintained by the library (updated via DutyCycle events)
            self._state_cache["gw_duty_cycle"] = getattr(self.gateway, 'utilization', 0)
            
            # sendingBlocked is a DutyMode enum (0=NOT_BLOCKED, 1=BLOCKED, 2=CRITICAL)
            duty_mode = getattr(self.gateway, 'sendingBlocked', None)
            if duty_mode is not None:
                # Consider gateway blocked if mode is 1 or 2
                self._state_cache["gw_duty_blocked"] = duty_mode.value in (1, 2)
            else:
                self._state_cache["gw_duty_blocked"] = False
            
            logger.debug(f"Gateway state refreshed from cache: "
                        f"Duty={self._state_cache.get('gw_duty_cycle')}%, "
                        f"Blocked={self._state_cache.get('gw_duty_blocked')}")
            
        except Exception as e:
            logger.warning(f"Could not refresh gateway state: {e}")

    async def _poll_until_stopped(self, device_id: str, device, max_retries: int = 10, delay: float = 0.5):
        """Polls device until is_moving=False or max_retries reached."""
        stable_count = 0
        
        for i in range(max_retries):
            await asyncio.sleep(delay)
            
            try:
                # Use correct python-selve-new API: updateCommeoDeviceValues with device ID
                if hasattr(device, 'id'):
                    await self.gateway.updateCommeoDeviceValues(device.id)
                else:
                    # Fallback: device is the ID itself
                    await self.gateway.updateCommeoDeviceValues(int(device_id))
                
                props = self._get_device_properties(device)
                
                # Publish intermediate state (for UI feedback)
                await self._publish_state(device_id)
                
                # Check if stopped (not moving)
                if not props.moving:
                    stable_count += 1
                    if stable_count >= 2:  # Must be stable for 2 consecutive checks
                        logger.info(f"Device {device_id} confirmed stopped at position {props.position}%")
                        return True
                else:
                    stable_count = 0
                    
            except Exception as e:
                logger.warning(f"Polling error for {device_id} (attempt {i+1}): {e}")
        
        logger.warning(f"Device {device_id} stop confirmation timeout")
        return False

    async def handle_command(self, device_id: str, command: str, value: Optional[int] = None, is_group: bool = False):
        target_map = self.groups if is_group else self.devices
        device = target_map.get(device_id)
        if not device:
            logger.warning(f"Device/Group {device_id} not found for command {command}")
            return

        try:
            if command == "position" and value is not None:
                # Validate position range (0-100)
                pos_val = int(value)
                if not (0 <= pos_val <= 100):
                    self.log.warning('err_pos_range', pos=pos_val, id=device_id)
                    return

                selve_pos = self._to_selve_position(pos_val)

                # Use gateway.moveDevicePos() - the correct python-selve-new API
                # SelveDevice has no movement methods; all control is via the gateway
                try:
                    await self.gateway.moveDevicePos(device, selve_pos)
                    logger.debug(f"Calling gateway.moveDevicePos(device {device_id}, {selve_pos})")
                except Exception as e:
                    logger.error(f"Position command on device {device_id} failed: {e}", exc_info=True)

            elif action := DEVICE_COMMANDS.get(command):
                logger.debug(f"Executing '{command}' -> '{action}' on {device_id}")
                
                # Gateway methods per python-selve-new API
                # Devices: moveDeviceUp/Down, stopDevice, moveDevicePos1/2
                # Groups:  moveGroupUp/Down, stopGroup
                try:
                    if is_group:
                        if command == "open":
                            logger.debug(f"Calling gateway.moveGroupUp(group {device_id})")
                            await self.gateway.moveGroupUp(device)
                        elif command == "close":
                            logger.debug(f"Calling gateway.moveGroupDown(group {device_id})")
                            await self.gateway.moveGroupDown(device)
                        elif command == "stop":
                            logger.debug(f"Calling gateway.stopGroup(group {device_id})")
                            await self.gateway.stopGroup(device)
                        else:
                            logger.warning(f"Unknown group command '{command}' for {device_id}")
                    else:
                        if command == "open":
                            logger.debug(f"Calling gateway.moveDeviceUp(device {device_id})")
                            await self.gateway.moveDeviceUp(device)
                        elif command == "close":
                            logger.debug(f"Calling gateway.moveDeviceDown(device {device_id})")
                            await self.gateway.moveDeviceDown(device)
                        elif command == "stop":
                            logger.debug(f"Calling gateway.stopDevice(device {device_id})")
                            await self.gateway.stopDevice(device)
                        elif command == "pos1":
                            logger.debug(f"Calling gateway.moveDevicePos1(device {device_id})")
                            await self.gateway.moveDevicePos1(device)
                        elif command == "pos2":
                            logger.debug(f"Calling gateway.moveDevicePos2(device {device_id})")
                            await self.gateway.moveDevicePos2(device)
                        else:
                            logger.warning(f"Unknown command '{command}' for device {device_id}")
                except Exception as e:
                    logger.error(f"Gateway command '{command}' on {'group' if is_group else 'device'} {device_id} failed: {e}", exc_info=True)

            logs = self.i18n.get('logs', {})
            target_type = logs.get('type_group', 'group') if is_group else logs.get('type_device', 'device')
            self.log.info('cmd_sent', cmd=command, type=target_type, id=device_id)

            if not is_group:
                # Publish optimistic state
                current = self._get_device_properties(device)
                optimistic = None

                if command == "open":
                    optimistic = replace(current, position=100, moving=True)
                elif command == "close":
                    optimistic = replace(current, position=0, moving=True)
                elif command == "stop":
                    optimistic = replace(current, moving=False)
                elif command == "position" and value is not None:
                    # DON'T set position optimistically - wait for real device updates
                    # Only mark as moving to indicate the command was received
                    optimistic = replace(current, moving=True)

                if optimistic:
                    await self._publish_state(device_id, forced_state=optimistic)

                # For STOP command: poll until actually stopped (fix for position reporting)
                if command == "stop":
                    await self._poll_until_stopped(device_id, device, max_retries=12, delay=0.5)
                else:
                    # Brief wait for other commands then refresh once
                    await asyncio.sleep(0.5)
                    # Refresh device values using python-selve-new API
                    if hasattr(device, 'id'):
                        await self.gateway.updateCommeoDeviceValues(device.id)
                    await self._publish_state(device_id)
                    
        except Exception as e:
            logger.error(f"Command error ({command}) on {'group' if is_group else 'device'} {device_id}: {e}")
            raise

    async def _publish_state(self, device_id: str, forced_state: Optional[DeviceState] = None):
        try:
            device = self.devices.get(device_id)
            if not device: return

            # Use the optimistic state if provided, otherwise fetch the current library state
            current_state = forced_state or self._get_device_properties(device)
            if current_state.position is None: return

            if self._state_cache.get(device_id) == current_state:
                return

            self._state_cache[device_id] = current_state
            props_dict = asdict(current_state)
            self.mqtt.publish(f"selve/{device_id}/position", current_state.position, retain=True)

            self.mqtt.publish(f"selve/{device_id}/unreachable", "OFF" if current_state.unreachable else "ON", retain=True)

            self.mqtt.publish(f"selve/{device_id}/state", props_dict, retain=True)

            if self.active_websockets:
                asyncio.create_task(self.broadcast_ws(device_id, **props_dict))
        except Exception as e:
            logger.error(f"State publish error for {device_id}: {e}")

    async def update_all(self):
        """Periodic update task: refreshes device values."""
        try:
            # Refresh all device values explicitly to get current position
            for dev_id, device in self.devices.items():
                await asyncio.sleep(0.1)  # Rate limiting
                try:
                    # Try python-selve-new API methods
                    if hasattr(device, 'update'):
                        await device.update()
                    elif hasattr(self.gateway, 'getDeviceValues'):
                        await self.gateway.getDeviceValues(device)
                    elif hasattr(self.gateway, 'get_device_values'):
                        await self.gateway.get_device_values(device)
                    
                    # Force publish even if no state change
                    await self._publish_state(dev_id)
                        
                except Exception as e:
                    logger.warning(f"Failed to update device {dev_id}: {e}")
            
            # Refresh gateway state (duty cycle, etc.)
            await self.check_firmware()
            
        except Exception as e:
            logger.error(f"Global update error: {e}")

    async def start_learning_mode(self, timeout_seconds: int = 30) -> bool:
        """
        Implements the pairing process according to Spec Page 24.
        Starts scan, polls for results, saves found devices, and stops scan.
        """
        self.log.info('pairing_start')
        try:
            await self.gateway.scan_start()

            found_anything = False
            # Poll scan results instead of blind sleep (Spec Page 29)
            for _ in range(timeout_seconds):
                await asyncio.sleep(1)
                # scan_result returns (status, count, discovered_ids)
                status, count, discovered_ids = await self.gateway.scan_result()

                if status == 1: # Run
                    if count > 0:
                        self.log.info('scan_progress', count=count)

                elif status == 3: # End_Success
                    self.log.info('scan_finished', count=count)
                    for dev_id in discovered_ids:
                        self.log.info('save_dev', id=dev_id)
                        await self.gateway.save_device(dev_id)
                    found_anything = True
                    break

                elif status == 4: # End_Failed
                    self.log.error('err_scan_failed')
                    break

            # Spec Page 28: scanStop clears the temporary list
            await self.gateway.scan_stop()
            return found_anything
        except Exception as e:
            logger.error(f"Critical error during learning mode: {e}")
            try:
                await self.gateway.scan_stop()
            except:
                pass
            return False

    async def start_sensor_learning_mode(self, timeout_seconds: int = 60) -> bool:
        """
        Implements the teach-in process for Commeo sensors according to Spec Page 38.
        Starts teach-in, polls for results, and stops.
        """
        self.log.info('sensor_teach_start')
        try:
            await self.gateway.sensorTeachStart()

            found_anything = False
            # Poll teach results periodically (Spec Page 41)
            for _ in range(timeout_seconds):
                await asyncio.sleep(1)
                # sensor_teach_result returns (status, time_left, sensor_id)
                status, time_left, sensor_id = await self.gateway.sensorTeachResult()

                if status == 1: # Run
                    if _ % 10 == 0:
                        self.log.info('sensor_teach_progress', time=time_left)
                elif status == 2: # End_Success
                    self.log.info('sensor_teach_success', id=sensor_id)
                    found_anything = True
                    break

            await self.gateway.sensorTeachStop()
            return found_anything
        except Exception as e:
            logger.error(f"Critical error during sensor teach-in: {e}")
            try:
                await self.gateway.sensorTeachStop()
            except:
                pass
            return False

    async def delete_device(self, device_id: str) -> bool:
        """
        Deletes a device from the gateway according to Spec Page 35.
        """
        try:
            self.log.info('del_dev', id=device_id)
            await self.gateway.delete_device(int(device_id))
            await self.discover() # Refresh internal device list
            return True
        except Exception as e:
            logger.error(f"Error deleting device {device_id}: {e}")
            return False

    async def delete_sensor(self, sensor_id: str) -> bool:
        """
        Deletes a sensor from the gateway according to Spec Page 44.
        """
        try:
            self.log.info('del_sens', id=sensor_id)
            await self.gateway.delete_sensor(int(sensor_id))
            await self.discover() # Refresh internal sensor list
            return True
        except Exception as e:
            logger.error(f"Error deleting sensor {sensor_id}: {e}")
            return False

    async def set_device_learning_mode(self, device_id: str, state: bool) -> bool:
        """Not supported by python-selve-new library. Use global scan/teach instead."""
        logger.warning(f"Device-specific learning mode not supported by library. Ignored for device {device_id}")
        return False

    async def get_device_senders(self, device_id: str) -> list:
        """
        LIMITATION: This feature is NOT supported by the SELVE API specification.
        
        Senders (remotes) taught directly to motors/devices are stored in the motor's
        internal memory and CANNOT be queried through the gateway. The SELVE USB-RF
        Stick protocol has no method to retrieve paired senders from a specific device.
        
        To make senders visible in the system, you must teach them to the GATEWAY:
        - Use "Start sender teach" button to teach remotes to gateway
        - Then they appear in the "Coupled Senders" list (get_all_senders)
        
        The "Show Senders" button in the UI will show this explanatory message.
        
        Args:
            device_id: Device/motor ID (ignored - kept for API compatibility)
            
        Returns:
            Always empty list - SELVE API limitation
        """
        logger.warning(f"get_device_senders({device_id}): SELVE API does not support querying "
                      "senders paired to motors. Teach senders to gateway instead.")
        return []

    async def get_sender_info(self, sender_id: str) -> dict:
        """
        Retrieves information about a sender taught into the GATEWAY.
        
        LIMITATION: Only returns info for senders taught to the gateway, not for 
        senders paired directly to motors. Those remain invisible to the API.
        
        Uses python-selve-new API: senderGetInfo(id)
        """
        try:
            self.log.info('get_sender_info', id=sender_id)
            # Use correct library method: senderGetInfo
            info = await self.gateway.senderGetInfo(int(sender_id))
            # Convert response to dict
            return {
                'id': sender_id,
                'name': getattr(info, 'name', 'Unknown'),
                'rfAddress': getattr(info, 'rfAddress', None),
                'rfChannel': getattr(info, 'rfChannel', None),
                'rfResetCount': getattr(info, 'rfResetCount', None)
            }
        except Exception as e:
            logger.error(f"Error retrieving sender info for {sender_id}: {e}")
            return {}

    async def set_sender_label(self, sender_id: str, new_label: str) -> bool:
        """
        Sets the label/name for a sender (if supported by the gateway/library).
        """
        # Validate length per LABEL_MAX_BYTES
        if len(new_label.encode('utf-8')) > LABEL_MAX_BYTES:
            self.log.error('err_name_too_long')
            return False

        try:
            self.log.info('set_sender_label', id=sender_id, name=new_label)
            # Library call for selve.GW.sender.setLabel (if available)
            await self.gateway.senderSetLabel(int(sender_id), new_label)
            # Refresh state
            await self.discover()
            self.publish_discovery()
            return True
        except Exception as e:
            logger.error(f"Error setting sender label {sender_id}: {e}")
            return False

    async def delete_device_sender(self, device_id: str, sender_index: int) -> bool:
        """
        LIMITATION: Cannot delete senders from device/motor memory.
        
        The SELVE API provides no method to remove a sender from a specific device's
        paired remote list. This function instead deletes a sender from the GATEWAY's
        sender list using senderDelete().
        
        Senders taught directly to motors remain in motor memory until:
        - Motor is factory reset physically, OR
        - Same remote ID is re-paired (overwrites old pairing)
        
        Args:
            device_id: Ignored - kept for API compatibility
            sender_index: The sender ID to delete from gateway
        """
        try:
            self.log.info('del_sender', index=sender_index, id=device_id)
            # NOTE: Deletes from gateway, not from device. SELVE API limitation.
            await self.gateway.senderDelete(int(sender_index))
            await self.discover()
            return True
        except Exception as e:
            logger.error(f"Error deleting sender {sender_index} from device {device_id}: {e}")
            return False

    async def get_all_senders(self) -> list:
        """
        Returns a list of senders taught into the GATEWAY.
        
        IMPORTANT LIMITATION: Only returns senders taught to the GATEWAY itself
        (max 63 channels). Senders paired directly to motors are NOT visible -
        they are stored in motor memory and cannot be queried via SELVE API.
        
        To make senders visible:
        1. Use "Start sender teach" to teach remotes to the gateway
        2. They will appear in this list with their ID
        3. These gateway-taught senders can trigger external systems (like MQTT)
        
        Direct motor pairings remain invisible to this API.
        
        Uses python-selve-new API: senderGetIds() and senderGetInfo(id).
        """
        try:
            # Get all sender IDs
            response = await self.gateway.senderGetIds()
            sender_ids = getattr(response, 'ids', [])
            
            result = []
            for sid in sender_ids:
                try:
                    info = await self.gateway.senderGetInfo(sid)
                    result.append({
                        'id': str(sid),
                        'name': getattr(info, 'name', 'Unknown'),
                        'rfAddress': getattr(info, 'rfAddress', None),
                        'rfChannel': getattr(info, 'rfChannel', None),
                        'rfResetCount': getattr(info, 'rfResetCount', None)
                    })
                except Exception:
                    result.append({'id': str(sid), 'name': 'Unknown'})
            return result
        except Exception as e:
            logger.error(f"Error listing all senders: {e}")
            return []

    async def delete_sender_global(self, sender_id: str) -> bool:
        """
        Attempts to delete a sender globally. If the gateway provides a direct delete method, use it.
        Otherwise, returns False.
        """
        try:
            if hasattr(self.gateway, 'delete_sender'):
                await self.gateway.delete_sender(int(sender_id))
                await self.discover()
                return True

            # If no global delete, try to find sender on devices and remove by index
            for dev_id in list(self.devices.keys()):
                try:
                    senders = await self.get_device_senders(dev_id)
                    # senders may be list of dicts or tuples; try to match id
                    for idx, s in enumerate(senders):
                        sid = None
                        if isinstance(s, dict):
                            sid = str(s.get('id') or s.get('senderId') or s.get('sender_id'))
                        elif isinstance(s, (list, tuple)) and len(s) >= 2:
                            sid = str(s[1])
                        else:
                            # If it's a plain int
                            sid = str(s)

                        if sid == str(sender_id):
                            # Found it; delete by device sender index
                            return await self.delete_device_sender(dev_id, idx)
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.error(f"Error deleting sender {sender_id}: {e}")
            return False

    async def get_sender_values(self, sender_id: str) -> dict:
        """
        Retrieves values or capabilities offered by a sender (if supported).
        """
        try:
            # Use correct python-selve-new API: senderGetValues(id)
            response = await self.gateway.senderGetValues(int(sender_id))
            # Convert response to dict with sender state info
            return {
                'id': sender_id,
                'values': getattr(response, 'values', None),
                'state': getattr(response, 'state', None),
                'event': getattr(response, 'event', None)
            }
        except Exception as e:
            logger.error(f"Error retrieving sender values for {sender_id}: {e}")
            return {}

    async def start_sender_teach(self, timeout_seconds: int = 30) -> dict:
        """
        Starts gateway sender teach-in (pairing) mode and polls for results.
        Returns a dict with 'status' and optional details on success.
        """
        self.log.info('sender_teach_start')
        try:
            # Use correct python-selve-new API: senderTeachStart()
            await self.gateway.senderTeachStart()

            for _ in range(timeout_seconds):
                await asyncio.sleep(1)
                try:
                    # Use correct python-selve-new API: senderTeachResult()
                    res = await self.gateway.senderTeachResult()
                except Exception:
                    continue

                if not res:
                    continue

                # SenderTeachResultResponse attributes: teachState, timeLeft, senderId, senderEvent
                if hasattr(res, 'teachState'):
                    teach_state = res.teachState
                    time_left = getattr(res, 'timeLeft', 0)
                    sender_id = getattr(res, 'senderId', None)
                    sender_event = getattr(res, 'senderEvent', None)
                else:
                    # Unknown shape — skip
                    continue

                # TeachState enum: RUN=1, END_SUCCESS=2, END_FAILED=4
                # Get enum value if it's an enum, otherwise assume it's already a value
                try:
                    state_value = int(teach_state.value) if hasattr(teach_state, 'value') else int(teach_state)
                except (ValueError, TypeError):
                    continue

                if state_value == 2:  # END_SUCCESS
                    try:
                        await self.gateway.senderTeachStop()
                    except Exception:
                        pass
                    await self.discover()
                    return {'status': 'success', 'sender': sender_id}
                elif state_value == 4:  # END_FAILED
                    try:
                        await self.gateway.senderTeachStop()
                    except Exception:
                        pass
                    return {'status': 'failed'}

            # Timeout
            try:
                await self.gateway.senderTeachStop()
            except Exception:
                pass
            return {'status': 'timeout'}
        except Exception as e:
            logger.error(f"Error during sender teach: {e}")
            try:
                await self.gateway.senderTeachStop()
            except Exception:
                pass
            return {'status': 'error', 'error': str(e)}

    async def stop_sender_teach(self) -> bool:
        """Stops an ongoing sender teach operation."""
        try:
            await self.gateway.senderTeachStop()
            return True
        except Exception as e:
            logger.error(f"Error stopping sender teach: {e}")
            return False

    async def save_group(self, group_id: int, name: str, device_ids: list) -> bool:
        """
        Creates or updates a group according to Spec Page 51.
        """
        # Specification: Max LABEL_MAX_BYTES bytes in UTF-8
        if len(name.encode('utf-8')) > LABEL_MAX_BYTES:
            self.log.error('err_name_too_long')
            return False

        try:
            self.log.info('save_group', id=group_id, name=name)
            # Ensure IDs are integers
            int_id = int(group_id)
            int_device_ids = [int(did) for did in device_ids]

            # Library call to write group configuration (name and membership)
            await self.gateway.write_group(int_id, name, int_device_ids)

            # Refresh internal state and notify HA
            await self.discover()
            self.publish_discovery()
            return True
        except Exception as e:
            logger.error(f"Error saving group {group_id}: {e}")
            return False

    async def delete_group(self, group_id: str) -> bool:
        """
        Deletes a group according to Spec Page 52.
        """
        try:
            self.log.info('del_group', id=group_id)
            await self.gateway.delete_group(int(group_id))
            await self.discover()
            self.publish_discovery()
            return True
        except Exception as e:
            logger.error(f"Error deleting group {group_id}: {e}")
            return False

    async def rename_device(self, device_id: str, new_name: str) -> bool:
        """
        Renames a device according to Spec Page 34.
        The name is stored directly in the actor via RF.
        """
        # Specification: Max LABEL_MAX_BYTES bytes in UTF-8
        if len(new_name.encode('utf-8')) > LABEL_MAX_BYTES:
            self.log.error('err_name_too_long')
            return False

        try:
            self.log.info('rename_dev', id=device_id, name=new_name)
            await self.gateway.deviceSetLabel(int(device_id), new_name)
            # Refresh internal state and notify HA via new discovery payload
            await self.discover()
            self.publish_discovery()
            return True
        except Exception as e:
            logger.error(f"Error renaming device {device_id}: {e}")
            return False

    async def rename_sensor(self, sensor_id: str, new_name: str) -> bool:
        """
        Renames a sensor according to Spec Page 43.
        The name is stored locally in the gateway.
        """
        # Specification: Max LABEL_MAX_BYTES bytes in UTF-8
        if len(new_name.encode('utf-8')) > LABEL_MAX_BYTES:
            self.log.error('err_name_too_long')
            return False

        try:
            self.log.info('rename_sens', id=sensor_id, name=new_name)
            await self.gateway.sensorSetLabel(int(sensor_id), new_name)
            # Refresh internal state and notify HA
            await self.discover()
            self.publish_discovery()
            return True
        except Exception as e:
            logger.error(f"Error renaming sensor {sensor_id}: {e}")
            return False

    async def reset_gateway(self) -> bool:
        """
        Performs a software reset of the gateway according to Spec Page 16.
        """
        try:
            self.log.info('reset_gw')
            await self.gateway.reset()
            return True
        except Exception as e:
            logger.error(f"Failed to reset gateway: {e}")
            return False

    async def rename_gateway(self, new_name: str) -> bool:
        """
        Sets the label for the gateway itself (Spec Page 16).
        """
        if len(new_name.encode('utf-8')) > LABEL_MAX_BYTES:
            self.log.error('err_name_too_long')
            return False
        try:
            # Gateway label setting not supported by library\n            logger.warning("Gateway label renaming not supported by python-selve-new")
            return True
        except Exception as e:
            logger.error(f"Error renaming gateway: {e}")
            return False

    async def check_firmware(self) -> bool:
        """
        Fetches gateway version and serial using the correct python-selve-new API.
        Uses getGatewayFirmwareVersion() and getGatewaySerial() which call
        ServiceGetVersion internally (selve.GW.service.getVersion).
        """
        try:
            selve_cfg = self.config.get('selve', {})

            # Correct API: getGatewayFirmwareVersion() returns "24.6.4.2" string
            fw = await self.gateway.getGatewayFirmwareVersion()
            serial = await self.gateway.getGatewaySerial()
            hw = "USB-RF Gateway"

            if not fw:
                fw = "N/A"
            if not serial:
                serial = "Unknown"

            self._state_cache["gw_hardware"] = hw
            self._state_cache["gw_firmware"] = fw
            self._state_cache["gw_serial"] = serial

            logger.info("=" * 50)
            logger.info("Selve Gateway Identified")
            logger.info("=" * 50)
            logger.info(f"  Hardware: {hw}")
            logger.info(f"  Firmware: {fw}")
            logger.info(f"  Serial:   {serial}")
            logger.info("=" * 50)

            self.log.info('gw_id', hw=hw, fw=fw)

            min_fw = selve_cfg.get('min_firmware_version')
            if min_fw and fw != 'N/A':
                if str(fw) < str(min_fw):
                    self.log.warning('fw_warn', fw=fw, min=min_fw)
                else:
                    self.log.info('fw_ok')

            # Online firmware check
            fw_url = selve_cfg.get('firmware_url')
            if fw_url and fw != 'N/A':
                try:
                    def fetch_online_fw():
                        headers = {'User-Agent': 'Selve2MQTT-Bridge'}
                        req = urllib.request.Request(fw_url, headers=headers)
                        with urllib.request.urlopen(req, timeout=5) as response:
                            return json.loads(response.read().decode('utf-8'))
                    data = await self.loop.run_in_executor(None, fetch_online_fw)
                    latest_fw = data.get('version')
                    if latest_fw:
                        self._state_cache["gw_latest_firmware"] = latest_fw
                        if str(fw) != str(latest_fw) and str(fw) < str(latest_fw):
                            self.log.warning('fw_online', latest=latest_fw, fw=fw)
                except Exception as e:
                    logger.warning(f"Could not check latest firmware online: {e}")

            return True
        except Exception as e:
            self.log.warning('err_fw_fetch', e=e)
            return False
