import asyncio
import logging
import json
import urllib.request
from typing import Dict, Any, Set, Optional
from selve import Selve
from selve.util.protocol import MovementState, CommunicationType
from selve.util import SelveTypes
from translations import TRANSLATIONS
from common import BaseComponent, setup_logger, PendingResponse

from pydantic import BaseModel
from models import (
    AppConfig,
    DeviceState,
    GroupState,
    SensorState,
    GatewayState,
    SenderInfo,
)

logger = setup_logger("selve2mqtt.selve")

# Maximum number of bytes allowed for device/group/sensor labels (UTF-8)
LABEL_MAX_BYTES = 23

# Spec Page 31: Mapping Selve configuration IDs to HA cover device classes
DEVICE_CLASS_MAP = {1: "shutter", 2: "blind", 3: "awning", 4: "shutter", 5: "shutter", 6: "shutter", 7: "shutter", 10: "shutter"}

# Sensor metadata mapping: (HA class, unit, icon, i18n_key)
SENSOR_META_MAP = {
    1: ("wind_speed", "m/s", "mdi:weather-windy", "wind"),
    2: ("moisture", "", "mdi:weather-rainy", "rain"),
    3: ("illuminance", "lx", "mdi:brightness-5", "light"),
    4: ("temperature", "°C", "mdi:thermometer", "temp"),
}

# Map Selve attribute names to HA attribute keys (Spec Page 32)
ATTR_LOOKUP = {
    "automaticMode": "automatic_mode",
    "unreachable": "unreachable",
    "value": "selve_raw_value",
    "overload": "overload",
    "obstructed": "obstructed",
    "windAlarm": "alarm_wind",
    "rainAlarm": "alarm_rain",
    "freezingAlarm": "alarm_frost",
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

    def info(self, key: str, **kwargs):
        self._log(logging.INFO, key, **kwargs)

    def warning(self, key: str, **kwargs):
        self._log(logging.WARNING, key, **kwargs)

    def error(self, key: str, **kwargs):
        self._log(logging.ERROR, key, **kwargs)


class SelveManager(BaseComponent):
    """
    Central orchestrator for the Selve USB-RF gateway.

    Manages device/group/sensor discovery, state tracking, command dispatch,
    MQTT publishing, Home Assistant discovery, and WebSocket broadcasts.

    Accepts an AppConfig (or dict) for configuration and uses Pydantic models
    (DeviceState, GroupState, SensorState, GatewayState) for all state data.
    """

    def __init__(
        self,
        config: Any,
        mqtt_client,
        loop: asyncio.AbstractEventLoop,
        active_websockets: Optional[Set] = None,
    ):
        super().__init__(config)
        self.config = config  # AppConfig or dict
        self.mqtt = mqtt_client
        self.loop = loop
        self.active_websockets = active_websockets if active_websockets is not None else set()

        self.gateway: Any = None
        self.devices: Dict[str, Any] = {}
        self.groups: Dict[str, Any] = {}
        self.sensors: Dict[str, Any] = {}
        self.senders: Dict[str, Any] = {}

        # Resolve open_close_fix from typed config or dict fallback
        if isinstance(config, AppConfig):
            self.open_close_fix = config.selve.open_close_fix
        else:
            selve_cfg = config.get('selve', {}) if isinstance(config, dict) else {}
            self.open_close_fix = selve_cfg.get('open_close_fix', False)

        # State cache keyed by device ID, stores DeviceState instances
        self._state_cache: Dict[str, DeviceState] = {}

        self._keepalive_task: Optional[asyncio.Task] = None
        self._pending_responses = PendingResponse(default_timeout=10.0)

        # Language / i18n
        if isinstance(config, AppConfig):
            self.lang_code = config.language
        else:
            self.lang_code = config.get('language', 'en') if isinstance(config, dict) else 'en'
        self.i18n = TRANSLATIONS.get(self.lang_code, TRANSLATIONS['en'])

        self.log = SelveLogger(
            logger,
            self.i18n.get('logs', {}),
            fallback=TRANSLATIONS.get('en', {}).get('logs', {}),
        )

        # Command serialisation delay (s)
        if isinstance(config, AppConfig):
            self._cmd_delay: float = config.selve.command_delay_ms / 1000.0
        else:
            selve_section = config.get('selve', {}) if isinstance(config, dict) else {}
            self._cmd_delay = selve_section.get('command_delay_ms', 100) / 1000.0

        self._cmd_queue: asyncio.Queue = asyncio.Queue()
        self._cmd_worker_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Setup & teardown
    # ------------------------------------------------------------------

    async def setup(self):
        # Cancel any existing tasks to prevent leaks on reconnect
        await self._cancel_background_tasks()

        # Determine port
        if isinstance(self.config, AppConfig):
            port = self.config.selve.port
        else:
            selve_cfg = self.config.get('selve', {}) if isinstance(self.config, dict) else {}
            port = selve_cfg.get('port')

        self.gateway = Selve(port=port) if port else Selve()

        if hasattr(self.gateway, '_LOGGER') and self.gateway._LOGGER is None:
            self.gateway._LOGGER = logging.getLogger("selve.lib")

        try:
            await self.gateway.setup()
            await self.check_firmware()
            await self._refresh_gateway_state()
            self.gateway.register_callback(self.on_device_update)

            # Enable spontaneous events
            try:
                await self.gateway.setEvents(
                    eventDevice=True, eventSensor=False,
                    eventSender=False, eventLogging=False,
                    eventDuty=True,
                )
                self.gateway.register_event_callback(self.on_gateway_event)
                self.log.info('events_enabled')
            except Exception as e:
                self.log.warning('events_not_supported', e=str(e))

            # Start keepalive and command worker tasks
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            self._cmd_queue = asyncio.Queue()
            self._cmd_worker_task = asyncio.create_task(self._cmd_worker())
            logger.debug(f"Gateway command queue started (delay={self._cmd_delay*1000:.0f}ms)")
            self.log.info('gw_init', port=port if port else 'Auto-Discovery')
        except Exception as e:
            self.log.error('err_gw_setup', e=str(e))
            raise e

    async def _cancel_background_tasks(self):
        """Cancel background tasks (_keepalive_task, _cmd_worker_task)."""
        for attr in ('_keepalive_task', '_cmd_worker_task'):
            task = getattr(self, attr, None)
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
                setattr(self, attr, None)

    async def shutdown(self):
        """Graceful shutdown: cancel background workers and drain the command queue."""
        logger.info("Shutting down SelveManager...")

        # 1) Cancel background tasks
        await self._cancel_background_tasks()

        # 2) Drain the command queue (cancel all pending futures)
        while not self._cmd_queue.empty():
            try:
                _, future = self._cmd_queue.get_nowait()
                if not future.done():
                    future.cancel()
                self._cmd_queue.task_done()
            except asyncio.QueueEmpty:
                break

    async def _keepalive_loop(self):
        """Ping every 45 s to prevent the 60 s idle-reconnect in serial_transport."""
        while True:
            try:
                await asyncio.sleep(45)
                await self.gateway.pingGateway()
                logger.debug("Keepalive ping sent")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Keepalive ping failed: {e}")

    async def _cmd_worker(self):
        """
        Serialise gateway commands to prevent 'Command overwritten' races.

        The Comméo gateway has a single command slot.  Sending a second
        command before the first has been transmitted causes the gateway to
        log "Command overwritten" and silently drop one command.
        """
        while True:
            try:
                coro, future = await self._cmd_queue.get()
                try:
                    result = await coro
                    if not future.done():
                        future.set_result(result)
                except Exception as exc:
                    if not future.done():
                        future.set_exception(exc)
                finally:
                    self._cmd_queue.task_done()
                    await asyncio.sleep(self._cmd_delay)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Command worker error: {e}")

    async def _dispatch(self, coro):
        """Enqueue a gateway coroutine and await its result."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        await self._cmd_queue.put((coro, future))
        return await future

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def discover(self):
        self.log.info('discovery_start')
        await self.gateway.discover()
        await asyncio.sleep(3)

        raw_devs = getattr(self.gateway, 'devices', {})
        raw_grps = getattr(self.gateway, 'groups', {})
        raw_sens = getattr(self.gateway, 'sensors', {})

        def flatten_entities(raw_dict):
            """Extract entities indexed by ID, looking into namespace sub-dicts."""
            entities = {}
            if not isinstance(raw_dict, dict):
                return entities
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

        # Load senders
        try:
            if hasattr(self.gateway, 'senderGetIds'):
                result = await self.gateway.senderGetIds()
                sender_ids = result.ids if hasattr(result, 'ids') else result
                self.senders = {}
                for sid in sender_ids:
                    try:
                        info = await self.gateway.senderGetInfo(sid)
                        self.senders[str(sid)] = {
                            'id': sid,
                            'name': info.name if hasattr(info, 'name') else f'Sender {sid}',
                            'rfAddress': getattr(info, 'rfAddress', None),
                            'rfChannel': getattr(info, 'rfChannel', None),
                            'rfResetCount': getattr(info, 'rfResetCount', None),
                        }
                    except Exception as e:
                        logger.warning(f"Could not load sender {sid}: {e}")
                        self.senders[str(sid)] = {'id': sid, 'name': f'Sender {sid}'}
            else:
                raw_senders = getattr(self.gateway, 'senders', {})
                self.senders = flatten_entities(raw_senders)
        except Exception as e:
            logger.warning(f"Sender discovery failed: {e}")
            self.senders = {}

        self.log.info(
            'discovery_done',
            devices=len(self.devices),
            groups=len(self.groups),
            sensors=len(self.sensors),
            senders=len(self.senders),
        )

    # ------------------------------------------------------------------
    # Property extraction helpers (return Pydantic models)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_attr(obj, attr, default=None):
        """Safely get an attribute from an object or a key from a dictionary."""
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    @staticmethod
    def _get_movement_direction(state) -> Optional[str]:
        """Derive HA cover state string from Selve MovementState.

        Returns 'opening', 'closing', 'stopped', or None if unknown.
        """
        try:
            val = int(state.value) if hasattr(state, 'value') else int(state)
        except (ValueError, TypeError):
            return None
        if val == 2:  # MovementState.UP_ON
            return "opening"
        elif val == 3:  # MovementState.DOWN_ON
            return "closing"
        elif val == 1:  # MovementState.STOPPED_OFF
            return "stopped"
        return None  # UNKOWN (0) or anything else

    @staticmethod
    def _get_cover_state_string(state: DeviceState) -> str:
        """Derive the HA cover state string from a DeviceState.

        Uses movement_direction if set, otherwise falls back to position.
        """
        if state.movement_direction == "opening":
            return "opening"
        elif state.movement_direction == "closing":
            return "closing"
        elif state.movement_direction == "stopped":
            # Determine if we've reached a final position
            if state.position is not None:
                if state.position <= 0:
                    return "closed"
                elif state.position >= 100:
                    return "open"
            return "stopped"
        # movement_direction is None – infer from position
        if state.moving:
            # Shouldn't happen, but be safe
            return "stopped"
        if state.position is not None:
            if state.position <= 0:
                return "closed"
            elif state.position >= 100:
                return "open"
        return "stopped"

    def _get_sensor_metadata(self, sens) -> dict:
        """Return metadata dict (device_class, unit, icon, type_name) for a sensor."""
        meta = {"device_class": None, "unit": "", "icon": "mdi:sensor", "type_name": "Generic"}
        sens_type = self._get_attr(sens, 'type')
        if sens_type in SENSOR_META_MAP:
            ha_class, unit, icon, i18n_key = SENSOR_META_MAP[sens_type]
            meta.update({
                "device_class": ha_class,
                "unit": unit,
                "icon": icon,
                "type_name": self.i18n['sensors'].get(i18n_key, i18n_key.capitalize()),
            })
        return meta

    def _to_ha_position(self, selve_value):
        """Convert Selve position (0=open, 100=closed) to HA percent (100=open, 0=closed)."""
        try:
            val = int(selve_value)
        except (ValueError, TypeError):
            return None
        ha = 100 - val
        if self.open_close_fix:
            if ha <= 1:
                ha = 0
            elif ha >= 99:
                ha = 100
        return ha

    def _to_selve_position(self, ha_value: int) -> int:
        """Convert HA position to Selve position."""
        return 100 - ha_value

    def _get_device_properties(self, device) -> DeviceState:
        """Extract a validated DeviceState Pydantic model from a Selve device object."""
        selve_raw = self._get_attr(device, 'value', 0)
        dev_id = self._get_attr(device, 'id', self._get_attr(device, 'channel', 'unknown'))
        selve_state = getattr(device, 'state', None)
        return DeviceState(
            position=self._to_ha_position(selve_raw),
            moving=selve_state in (MovementState.UP_ON, MovementState.DOWN_ON),
            movement_direction=self._get_movement_direction(selve_state),
            name=self._get_attr(device, 'name', f"Aktor {dev_id}"),
            unreachable=self._get_attr(device, 'unreachable', False),
            obstructed=self._get_attr(device, 'obstructed', False),
            overload=self._get_attr(device, 'overload', False),
            auto_mode=self._get_attr(device, 'automaticMode', False),
            selve_raw_value=selve_raw,
        )

    def _get_group_properties(self, group) -> GroupState:
        """Extract a validated GroupState Pydantic model from a Selve group object."""
        grp_id = self._get_attr(group, 'id', self._get_attr(group, 'channel', 'unknown'))
        dev_coll = self._get_attr(group, 'devices', {})
        if isinstance(dev_coll, dict):
            device_ids = [str(self._get_attr(d, 'id')) for d in dev_coll.values()]
        else:
            device_ids = [str(self._get_attr(d, 'id')) for d in dev_coll]
        return GroupState(
            name=self._get_attr(group, 'name', f"Gruppe {grp_id}"),
            device_ids=device_ids,
        )

    def _get_sensor_properties(self, sensor) -> SensorState:
        """Extract a validated SensorState Pydantic model from a Selve sensor object."""
        meta = self._get_sensor_metadata(sensor)
        sens_id = self._get_attr(sensor, 'id', self._get_attr(sensor, 'channel', 'unknown'))
        return SensorState(
            value=self._get_attr(sensor, 'value', 'unknown'),
            type=meta["type_name"],
            unit=meta["unit"],
            name=self._get_attr(sensor, 'name', f"Sensor {sens_id}"),
        )

    def _get_sender_properties(self, sender) -> dict:
        """Extract a sender-info dict from a Selve sender object."""
        sender_id = self._get_attr(sender, 'id', self._get_attr(sender, 'channel', 'unknown'))
        return {
            "id": str(sender_id),
            "name": self._get_attr(sender, 'name', f"Sender {sender_id}"),
            "last_event": self._get_attr(sender, 'lastEvent', 0),
        }

    # ------------------------------------------------------------------
    # Gateway state
    # ------------------------------------------------------------------

    def get_gateway_state(self) -> GatewayState:
        """Return a validated GatewayState Pydantic model from the internal cache."""
        return GatewayState(
            duty_cycle=self._state_cache.get("gw_duty_cycle", 0),
            duty_blocked=self._state_cache.get("gw_duty_blocked", False),
            hardware=self._state_cache.get("gw_hardware", "N/A"),
            firmware=self._state_cache.get("gw_firmware", "N/A"),
            latest_firmware=self._state_cache.get("gw_latest_firmware", "N/A"),
            serial_number=self._state_cache.get("gw_serial", "Unknown"),
        )

    def get_full_state(self) -> dict:
        """Build the complete system state snapshot for the initial UI load."""
        gw_state = self.get_gateway_state()

        devices = {}
        for d_id, d in self.devices.items():
            try:
                devices[d_id] = self._get_device_properties(d).model_dump()
            except Exception as e:
                logger.debug(f"Could not build DeviceState for {d_id}: {e}")
                devices[d_id] = {"name": f"Device {d_id}", "error": str(e)}

        groups = {}
        for g_id, g in self.groups.items():
            try:
                groups[g_id] = self._get_group_properties(g).model_dump()
            except Exception as e:
                groups[g_id] = {"name": f"Group {g_id}", "error": str(e)}

        sensors = {}
        for s_id, s in self.sensors.items():
            try:
                sensors[s_id] = self._get_sensor_properties(s).model_dump()
            except Exception as e:
                sensors[s_id] = {"name": f"Sensor {s_id}", "error": str(e)}

        senders = {s_id: self._get_sender_properties(s) for s_id, s in self.senders.items()}

        result = {
            "type": "full_state",
            "devices": devices,
            "groups": groups,
            "sensors": sensors,
            "senders": senders,
            "gateway": gw_state.model_dump(),
        }
        logger.debug(
            f"Full state gateway: HW={gw_state.hardware}, "
            f"FW={gw_state.firmware}, Serial={gw_state.serial_number}"
        )
        return result

    # ------------------------------------------------------------------
    # MQTT / Home Assistant discovery
    # ------------------------------------------------------------------

    async def publish_discovery(self):
        """Publish Home Assistant MQTT discovery messages for all entities."""
        for dev_id, dev in self.devices.items():
            logger.debug(f"DEBUG_START: Analyzing device {dev_id}")
            logger.debug(f"DEBUG: Class: {dev.__class__.__name__}")
            logger.debug(f"DEBUG: Attributes: {dir(dev)}")
            if hasattr(dev, '__dict__'):
                logger.debug(f"DEBUG: Dict: {dev.__dict__}")

            # --------------------------------------------------------------
            # Communication type detection (bidirectional Commeo vs. one-way Iveo)
            # --------------------------------------------------------------
            # Primary: use device_type (SelveTypes enum — "device" or "iveo")
            is_iveo = False
            dev_type = self._get_attr(dev, 'device_type', None)
            if dev_type is not None:
                if hasattr(dev_type, 'value'):
                    is_iveo = dev_type.value == SelveTypes.IVEO.value
                else:
                    is_iveo = str(dev_type) == str(SelveTypes.IVEO.value)

            # Fallback: check communicationType attribute
            # (SelveDevice defaults to CommunicationType.COMMEO (0),
            #  IveoDevice defaults to CommunicationType.IVEO (1))
            if dev_type is None:
                comm_type = self._get_attr(dev, 'communicationType', None)
                if comm_type is not None:
                    if hasattr(comm_type, 'value'):
                        is_iveo = comm_type.value == CommunicationType.IVEO.value
                    else:
                        try:
                            is_iveo = int(comm_type) == CommunicationType.IVEO.value
                        except (ValueError, TypeError):
                            is_iveo = "iveo" in str(comm_type).lower()

            is_bidir = not is_iveo

            # --------------------------------------------------------------
            # Device sub-type for HA device class
            # --------------------------------------------------------------
            # device_sub_type is a DeviceType enum (values: 1=shutter, 2=blind, …).
            # Fallback: config attribute or default 1 (shutter).
            config_val = self._get_attr(
                dev, 'device_sub_type',
                self._get_attr(dev, 'config', 1),
        )
            if hasattr(config_val, 'value'):
                config_val = config_val.value

            friendly_name = self._get_attr(dev, 'name', f"Selve {dev_id}")
            topic = f"{self.mqtt.discovery_prefix}/cover/selve_{dev_id}/config"
            logger.debug(f"DEBUG: Device {dev_id} detected as {'COMMEO' if is_bidir else 'IVEO'}")

            bridge_info = {
                "identifiers": ["selve_gateway"],
                "name": "Selve Gateway",
                "manufacturer": "Selve",
            }
            cfg = {
                "name": None,
                "object_id": f"selve_{dev_id}",
                "unique_id": f"selve_device_{dev_id}",
                "command_topic": f"selve/{dev_id}/set",
                "state_topic": f"selve/{dev_id}/cover_state",
                "state_open": "open",
                "state_opening": "opening",
                "state_closed": "closed",
                "state_closing": "closing",
                "state_stopped": "stopped",
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
                    "via_device": "selve_gateway",
                },
                "json_attributes_topic": f"selve/{dev_id}/attributes",
            }

            if is_bidir:
                cfg.update({
                    "position_topic": f"selve/{dev_id}/position",
                    "set_position_topic": f"selve/{dev_id}/position/set",
                    "position_open": 100,
                    "position_closed": 0,
                })

                # Connectivity (Unreachable) binary sensor discovery
                unreach_topic = (
                    f"{self.mqtt.discovery_prefix}/binary_sensor/"
                    f"selve_{dev_id}_unreachable/config"
                )
                unreach_cfg = {
                    "name": self.i18n['ui'].get('connectivity', 'Connectivity'),
                    "unique_id": f"selve_device_{dev_id}_unreachable",
                    "state_topic": f"selve/{dev_id}/unreachable",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "device_class": "connectivity",
                    "entity_category": "diagnostic",
                    "device": cfg["device"],
                }
                self.mqtt.publish(unreach_topic, unreach_cfg, retain=True)

            self.mqtt.publish(topic, cfg, retain=True)

            # Programmatic attribute collection
            attrs = {
                ha_key: self._get_attr(dev, selve_key, False)
                for selve_key, ha_key in ATTR_LOOKUP.items()
            }
            day_mode = self._get_attr(dev, 'dayMode', 0)
            day_mode_map = {1: "Night", 2: "Dawn", 3: "Day", 4: "Dusk"}
            if day_mode in day_mode_map:
                attrs["day_mode"] = day_mode_map[day_mode]
            self.mqtt.publish(f"selve/{dev_id}/attributes", attrs, retain=True)
            await self._publish_state(dev_id)

        # Groups discovery
        for grp_id, grp in self.groups.items():
            friendly_name = getattr(grp, 'name', f"Selve Gruppe {grp_id}")
            topic = f"{self.mqtt.discovery_prefix}/cover/selve_group_{grp_id}/config"
            cfg = {
                "name": None,
                "object_id": f"selve_group_{grp_id}",
                "unique_id": f"selve_group_{grp_id}",
                "command_topic": f"selve/group/{grp_id}/set",
                "availability_topic": "selve/status",
                "payload_available": "online",
                "payload_not_available": "offline",
                "optimistic": True,
                "device_class": "shutter",
                "device": {
                    "identifiers": [f"selve_group_{grp_id}"],
                    "name": friendly_name,
                    "manufacturer": "Selve",
                    "model": "Group",
                    "via_device": "selve_gateway",
                },
                "set_position_topic": f"selve/group/{grp_id}/position/set",
            }
            self.mqtt.publish(topic, cfg, retain=True)

        # Sensors discovery
        for sens_id, sens in self.sensors.items():
            friendly_name = getattr(sens, 'name', f"Selve Sensor {sens_id}")
            meta = self._get_sensor_metadata(sens)
            topic = f"{self.mqtt.discovery_prefix}/sensor/selve_sens_{sens_id}/config"
            cfg = {
                "name": meta["type_name"],
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
                    "via_device": "selve_gateway",
                },
            }
            self.mqtt.publish(topic, cfg, retain=True)

        # Senders discovery
        for sender_id, sender in self.senders.items():
            if not sender:
                continue
            friendly_name = self._get_attr(sender, 'name', f"Remote {sender_id}")
            sender_type = self._get_attr(sender, 'type', 'Unknown')
            topic = f"{self.mqtt.discovery_prefix}/sensor/selve_sender_{sender_id}/config"
            cfg = {
                "name": None,
                "unique_id": f"selve_sender_{sender_id}",
                "state_topic": f"selve/sender/{sender_id}/state",
                "availability_topic": "selve/status",
                "icon": "mdi:remote",
                "device": {
                    "identifiers": [f"selve_sender_{sender_id}"],
                    "name": friendly_name,
                    "manufacturer": "Selve",
                    "model": f"Remote Control ({sender_type})",
                    "via_device": "selve_gateway",
                },
            }
            self.mqtt.publish(topic, cfg, retain=True)

        # Gateway discovery
        self._publish_gateway_discovery()
        self.mqtt.publish("selve/status", "online", retain=True)

        gw_state = self.get_gateway_state()
        self.mqtt.publish("selve/gateway/duty_cycle", gw_state.duty_cycle, retain=True)
        self.mqtt.publish(
            "selve/gateway/duty_cycle_blocked",
            "ON" if gw_state.duty_blocked else "OFF",
            retain=True,
        )

    def _publish_gateway_discovery(self):
        """Publish MQTT discovery for gateway-level entities."""
        # LED Switch
        led_topic = f"{self.mqtt.discovery_prefix}/switch/selve_gateway_led/config"
        self.mqtt.publish(led_topic, {
            "name": self.i18n['ui'].get('gw_led', 'Gateway LED'),
            "unique_id": "selve_gateway_led",
            "command_topic": "selve/gateway/led/set",
            "state_topic": "selve/gateway/led/state",
            "icon": "mdi:led-on",
            "device": {
                "identifiers": ["selve_gateway"],
                "name": "Selve Gateway",
                "manufacturer": "Selve",
            },
        }, retain=True)

        # Forwarding Switch
        fwd_topic = f"{self.mqtt.discovery_prefix}/switch/selve_gateway_forward/config"
        self.mqtt.publish(fwd_topic, {
            "name": self.i18n['ui'].get('gw_forwarding', 'Commeo Forwarding'),
            "unique_id": "selve_gateway_forward",
            "command_topic": "selve/gateway/forward/set",
            "state_topic": "selve/gateway/forward/state",
            "icon": "mdi:router-wireless",
            "device": {
                "identifiers": ["selve_gateway"],
                "name": "Selve Gateway",
                "manufacturer": "Selve",
            },
        }, retain=True)

        # Duty Cycle Sensor
        dc_topic = f"{self.mqtt.discovery_prefix}/sensor/selve_gateway_duty_cycle/config"
        self.mqtt.publish(dc_topic, {
            "name": self.i18n['ui'].get('gw_duty_cycle', 'Gateway Duty Cycle'),
            "unique_id": "selve_gateway_duty_cycle",
            "state_topic": "selve/gateway/duty_cycle",
            "unit_of_measurement": "%",
            "entity_category": "diagnostic",
            "device": {
                "identifiers": ["selve_gateway"],
                "name": "Selve Gateway",
                "manufacturer": "Selve",
            },
        }, retain=True)

        # Duty Cycle Blocked Binary Sensor
        dcb_topic = (
            f"{self.mqtt.discovery_prefix}/binary_sensor/"
            f"selve_gateway_duty_blocked/config"
        )
        self.mqtt.publish(dcb_topic, {
            "name": self.i18n['ui'].get('gw_duty_blocked', 'Gateway Duty Cycle Blocked'),
            "unique_id": "selve_gateway_duty_blocked",
            "state_topic": "selve/gateway/duty_cycle_blocked",
            "payload_on": "ON",
            "payload_off": "OFF",
            "device_class": "problem",
            "entity_category": "diagnostic",
            "device": {
                "identifiers": ["selve_gateway"],
                "name": "Selve Gateway",
                "manufacturer": "Selve",
            },
        }, retain=True)

    # ------------------------------------------------------------------
    # Gateway settings
    # ------------------------------------------------------------------

    async def set_gateway_led(self, enabled: bool):
        """Toggle the physical LED (Spec Page 17)."""
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
        """Toggle Commeo Forwarding (Spec Page 19)."""
        try:
            mode = 1 if enabled else 0
            logger.info(f"Setting Commeo Forwarding to {'ON' if enabled else 'OFF'}")
            await self.gateway.setForward(mode)
            self.mqtt.publish("selve/gateway/forward/state", "ON" if enabled else "OFF", retain=True)
            return True
        except Exception as e:
            logger.error(f"Failed to set Forwarding: {e}")
            return False

    # ------------------------------------------------------------------
    # Callbacks (device & gateway events)
    # ------------------------------------------------------------------

    def on_device_update(self, device=None, *args):
        """Entry point for Selve library callbacks."""
        self._process_gateway_events()
        if device:
            self._process_entity_update(device)
        else:
            for dev_obj in list(self.devices.values()):
                self._process_entity_update(dev_obj)
            for grp_obj in list(self.groups.values()):
                self._process_entity_update(grp_obj)

    def on_gateway_event(self, response=None):
        """Callback for spontaneous gateway events (duty cycle, logs)."""
        self._process_gateway_events()

    def _process_gateway_events(self):
        """Handle Duty Cycle and Log events from the gateway."""
        duty_val = getattr(self.gateway, 'utilization', None)
        duty_mode = getattr(self.gateway, 'sendingBlocked', None)
        duty_blocked = duty_mode.value in (1, 2) if duty_mode is not None else False

        if duty_val is not None:
            old_duty = self._state_cache.get("gw_duty_cycle")
            old_blocked = self._state_cache.get("gw_duty_blocked")
            if duty_val != old_duty or duty_blocked != old_blocked:
                self._state_cache["gw_duty_cycle"] = duty_val
                self._state_cache["gw_duty_blocked"] = duty_blocked

                status_key = 'status_blocked' if duty_blocked else 'status_ok'
                status_str = self.i18n.get('logs', {}).get(status_key, status_key.upper())
                self.log.info('duty_cycle_event', duty=duty_val, status=status_str)
                self.mqtt.publish("selve/gateway/duty_cycle", duty_val, retain=True)
                self.mqtt.publish(
                    "selve/gateway/duty_cycle_blocked",
                    "ON" if duty_blocked else "OFF",
                    retain=True,
                )
                if self.active_websockets:
                    asyncio.run_coroutine_threadsafe(
                        self.broadcast_gateway_ws(duty_val, duty_blocked), self.loop,
                    )

        # Gateway Logs (Spec Page 73)
        log_desc = getattr(self.gateway, 'last_log_description', None)
        if log_desc:
            log_type = getattr(self.gateway, 'last_log_type', 0)
            log_code = getattr(self.gateway, 'last_log_code', 'unknown')
            log_msg = f"GATEWAY LOG [Code {log_code}]: {log_desc}"
            if log_type == 2:
                self.log.error(log_msg)
            elif log_type == 1:
                self.log.warning(log_msg)
            else:
                self.log.info(log_msg)
            self.mqtt.publish(
                "selve/gateway/last_log",
                {"type": log_type, "code": log_code, "message": log_desc},
                retain=False,
            )
            self.gateway.last_log_description = None

    def _process_entity_update(self, device):
        """Delegate updates to sensor, sender, or device processors."""
        dev_id = str(device.id)
        try:
            if dev_id in self.sensors:
                val = getattr(device, 'value', 'unknown')
                self.mqtt.publish(f"selve/sensor/{dev_id}/state", val, retain=True)
                if self.active_websockets:
                    asyncio.run_coroutine_threadsafe(
                        self.broadcast_sensor_ws(device, val), self.loop,
                    )
            elif dev_id in self.senders:
                self._handle_sender_update(device)
            elif dev_id in self.devices:
                self._handle_device_state_change(device)
            self._pending_responses.signal(dev_id)
        except Exception as e:
            self.log.error(f"Entity update error for {dev_id}: {e}")

    def _handle_sender_update(self, sender):
        """Process incoming sender events."""
        sender_id = str(self._get_attr(sender, 'id'))
        last_event = self._get_attr(sender, 'lastEvent', 0)
        self.mqtt.publish(f"selve/sender/{sender_id}/state", last_event, retain=True)
        if self.active_websockets:
            asyncio.run_coroutine_threadsafe(
                self.broadcast_sender_ws(sender_id, last_event), self.loop,
            )

    def _handle_device_state_change(self, device):
        """Process changes in device state; publish MQTT and WebSocket."""
        dev_id = str(device.id)
        try:
            current_state = self._get_device_properties(device)
        except Exception as e:
            logger.warning(f"Could not build DeviceState for {dev_id}: {e}")
            return

        old_state = self._state_cache.get(dev_id)
        if old_state == current_state:
            return

        # While a command is awaiting its response, the gateway may echo the
        # pre-command position back. Publish such intermediate callbacks would
        # overwrite the optimistic value already broadcast by handle_command and
        # make the UI temporarily show the old position again. The pending
        # response is still signalled (see _process_entity_update), so
        # handle_command proceeds normally; the settled state is published once
        # the command has completed.
        if dev_id in self._pending_responses.active_device_ids:
            logger.debug(f"Ignoring intermediate device update for {dev_id} while command in flight")
            return

        if old_state and old_state.unreachable != current_state.unreachable:
            if current_state.unreachable:
                self.log.warning('device_unreachable', name=current_state.name, id=dev_id)
            else:
                self.log.info('device_online', name=current_state.name, id=dev_id)

        self._state_cache[dev_id] = current_state

        self._publish_device_state_mqtt_ws(dev_id, current_state)

        self.log.info(
            'update_received',
            id=dev_id,
            pos=current_state.position,
            moving=current_state.moving,
            raw=current_state.selve_raw_value,
        )

    # ------------------------------------------------------------------
    # WebSocket broadcasts
    # ------------------------------------------------------------------

    async def broadcast_ws(self, dev_id: str, state: DeviceState):
        """Send a device state update to all connected WebSocket clients."""
        payload = {
            "type": "device_update",
            "id": dev_id,
            "position": state.position,
            "moving": state.moving,
            "movement_direction": state.movement_direction,
            "unreachable": state.unreachable,
            "obstructed": state.obstructed,
            "overload": state.overload,
            "auto_mode": state.auto_mode,
        }
        dead = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_websockets.discard(ws)

    async def broadcast_gateway_ws(self, duty_cycle: int, duty_blocked: bool):
        """Send gateway diagnostics to all connected WebSocket clients."""
        dead = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json({
                    "type": "gateway_update",
                    "duty_cycle": duty_cycle,
                    "duty_blocked": duty_blocked,
                })
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_websockets.discard(ws)

    async def broadcast_sensor_ws(self, sensor, value):
        """Send sensor update to all connected WebSocket clients."""
        sens_id = str(sensor.id)
        meta = self._get_sensor_metadata(sensor)
        dead = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json({
                    "type": "sensor_update",
                    "id": sens_id,
                    "value": value,
                    "unit": meta["unit"],
                })
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_websockets.discard(ws)

    async def broadcast_sender_ws(self, sender_id: str, event_code: int):
        """Send sender event to all connected WebSocket clients."""
        dead = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json({
                    "type": "sender_update",
                    "id": sender_id,
                    "event": event_code,
                })
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_websockets.discard(ws)

    # ------------------------------------------------------------------
    # Gateway state refresh
    # ------------------------------------------------------------------

    async def _refresh_gateway_state(self):
        """Refresh gateway state from library-maintained cache."""
        try:
            self._state_cache["gw_duty_cycle"] = getattr(self.gateway, 'utilization', 0)
            duty_mode = getattr(self.gateway, 'sendingBlocked', None)
            if duty_mode is not None:
                self._state_cache["gw_duty_blocked"] = duty_mode.value in (1, 2)
            else:
                self._state_cache["gw_duty_blocked"] = False
            logger.debug(
                f"Gateway state refreshed from cache: "
                f"Duty={self._state_cache.get('gw_duty_cycle')}%, "
                f"Blocked={self._state_cache.get('gw_duty_blocked')}"
            )
        except Exception as e:
            logger.warning(f"Could not refresh gateway state: {e}")

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    async def handle_command(
        self,
        device_id: str,
        command: str,
        value: Optional[int] = None,
        is_group: bool = False,
    ):
        """Dispatch a command to a device or group via the gateway."""
        target_map = self.groups if is_group else self.devices
        device = target_map.get(device_id)
        if not device:
            logger.warning(f"Device/Group {device_id} not found for command {command}")
            return

        try:
            # Validate the position FIRST, so an invalid command never
            # registers a pending response that would otherwise leak.
            if command == "position" and value is not None:
                pos_val = int(value)
                if not (0 <= pos_val <= 100):
                    self.log.warning('err_pos_range', pos=pos_val, id=device_id)
                    return
                selve_pos = self._to_selve_position(pos_val)

            # Register the pending response BEFORE dispatching so an early
            # reply is still captured; wait() removes it again on exit.
            if not is_group:
                self._pending_responses.expect(device_id)

            # Log the command BEFORE dispatching it. The gateway callbacks
            # fire *during* the dispatch, so logging afterwards makes the
            # resulting state update appear before the command in the log.
            logs = self.i18n.get('logs', {})
            target_type = logs.get('type_group', 'group') if is_group else logs.get('type_device', 'device')
            log_params = dict(cmd=command, type=target_type, id=device_id)
            if command == "position" and value is not None:
                log_params['val'] = f" (Ziel: {int(value)}%)."
            else:
                log_params['val'] = "."
            self.log.info('cmd_sent', **log_params)

            if command == "position" and value is not None:
                try:
                    await self._dispatch(self.gateway.moveDevicePos(device, selve_pos))
                    logger.debug(f"Calling gateway.moveDevicePos(device {device_id}, {selve_pos})")
                except Exception as e:
                    logger.error(f"Position command on device {device_id} failed: {e}", exc_info=True)

            elif action := DEVICE_COMMANDS.get(command):
                logger.debug(f"Executing '{command}' -> '{action}' on {device_id}")
                try:
                    if is_group:
                        if command == "open":
                            logger.debug(f"Calling gateway.moveGroupUp(group {device_id})")
                            await self._dispatch(self.gateway.moveGroupUp(device))
                        elif command == "close":
                            logger.debug(f"Calling gateway.moveGroupDown(group {device_id})")
                            await self._dispatch(self.gateway.moveGroupDown(device))
                        elif command == "stop":
                            logger.debug(f"Calling gateway.stopGroup(group {device_id})")
                            await self._dispatch(self.gateway.stopGroup(device))
                        else:
                            logger.warning(f"Unknown group command '{command}' for {device_id}")
                    else:
                        if command == "open":
                            logger.debug(f"Calling gateway.moveDeviceUp(device {device_id})")
                            await self._dispatch(self.gateway.moveDeviceUp(device))
                        elif command == "close":
                            logger.debug(f"Calling gateway.moveDeviceDown(device {device_id})")
                            await self._dispatch(self.gateway.moveDeviceDown(device))
                        elif command == "stop":
                            logger.debug(f"Calling gateway.stopDevice(device {device_id})")
                            await self._dispatch(self.gateway.stopDevice(device))
                        elif command == "pos1":
                            logger.debug(f"Calling gateway.moveDevicePos1(device {device_id})")
                            await self._dispatch(self.gateway.moveDevicePos1(device))
                        elif command == "pos2":
                            logger.debug(f"Calling gateway.moveDevicePos2(device {device_id})")
                            await self._dispatch(self.gateway.moveDevicePos2(device))
                        else:
                            logger.warning(f"Unknown command '{command}' for device {device_id}")
                except Exception as e:
                    logger.error(
                        f"Gateway command '{command}' on "
                        f"{'group' if is_group else 'device'} {device_id} failed: {e}",
                        exc_info=True,
                    )

            # Publish optimistic state for devices
            if not is_group:
                try:
                    current = self._get_device_properties(device)
                except Exception:
                    current = None
                optimistic = None
                if current:
                    if command == "open":
                        optimistic = current.model_copy(
                            update={"position": 100, "moving": True, "movement_direction": "opening"}
                        )
                    elif command == "close":
                        optimistic = current.model_copy(
                            update={"position": 0, "moving": True, "movement_direction": "closing"}
                        )
                    elif command == "stop":
                        optimistic = current.model_copy(
                            update={"moving": False, "movement_direction": "stopped"}
                        )
                    elif command == "position" and value is not None:
                        # Derive direction from current vs. target position
                        target_pos = int(value)
                        if current.position is not None:
                            direction = "opening" if target_pos > current.position else "closing"
                        else:
                            direction = None
                        optimistic = current.model_copy(
                            update={"position": target_pos, "moving": True, "movement_direction": direction}
                        )
                    elif command in ("pos1", "pos2"):
                        optimistic = current.model_copy(
                            update={"moving": True, "movement_direction": None}
                        )

                if optimistic:
                    await self._publish_state(device_id, forced_state=optimistic)

                # Wait for callback response or fallback poll
                received = await self._pending_responses.wait(device_id)
                if not received:
                    logger.debug(f"No callback for {device_id} within timeout – fallback poll")
                    if hasattr(device, 'id'):
                        try:
                            await self.gateway.updateCommeoDeviceValues(device.id)
                        except Exception:
                            pass
                    await self._publish_state(device_id)

        except Exception as e:
            # On abnormal exit the pending `wait()` is never reached, so drop
            # any registered future to avoid a memory leak.
            if not is_group:
                self._pending_responses.remove(device_id)
            logger.error(
                f"Command error ({command}) on "
                f"{'group' if is_group else 'device'} {device_id}: {e}"
            )
            raise

    def _publish_device_state_mqtt_ws(self, device_id: str, state: DeviceState):
        """Publish a single device state to MQTT topics and broadcast via WebSocket.

        This is the single canonical implementation used by both
        ``_handle_device_state_change`` and ``_publish_state``.
        """
        if state.position is not None:
            self.mqtt.publish(f"selve/{device_id}/position", state.position, retain=True)
        self.mqtt.publish(
            f"selve/{device_id}/moving", "ON" if state.moving else "OFF", retain=True,
        )
        self.mqtt.publish(f"selve/{device_id}/selve_raw_value", state.selve_raw_value, retain=True)
        cover_state = self._get_cover_state_string(state)
        self.mqtt.publish(f"selve/{device_id}/cover_state", cover_state, retain=True)
        self.mqtt.publish(
            f"selve/{device_id}/unreachable",
            "OFF" if state.unreachable else "ON",
            retain=True,
        )
        self.mqtt.publish(f"selve/{device_id}/state", state.model_dump(), retain=True)

        if self.active_websockets:
            # Schedule the broadcast without blocking the gateway callback.
            # run_coroutine_threadsafe keeps a reference to the wrapping Future
            # so the task cannot be garbage-collected mid-send.
            asyncio.run_coroutine_threadsafe(self.broadcast_ws(device_id, state), self.loop)

    async def _publish_state(self, device_id: str, forced_state: Optional[DeviceState] = None):
        """Publish device state to MQTT and broadcast via WebSocket.

        When called with ``forced_state``, the state is published directly to
        MQTT/WebSocket *without* updating the internal cache. This ensures
        that subsequent real callbacks still detect a difference and publish
        the authoritative state.
        """
        try:
            device = self.devices.get(device_id)
            if not device:
                return

            if forced_state is not None:
                current_state = forced_state
            else:
                try:
                    current_state = self._get_device_properties(device)
                except Exception as e:
                    logger.warning(f"Could not get device state for {device_id}: {e}")
                    return

                if current_state.position is None:
                    return

                # Skip publishing if state hasn't changed (real updates only)
                if self._state_cache.get(device_id) == current_state:
                    return

            self._state_cache[device_id] = current_state

            self._publish_device_state_mqtt_ws(device_id, current_state)
        except Exception as e:
            logger.error(f"State publish error for {device_id}: {e}")

    async def update_all(self):
        """Periodic update task: refresh all device values."""
        try:
            for dev_id, device in self.devices.items():
                await asyncio.sleep(0.1)
                try:
                    if hasattr(device, 'update'):
                        await device.update()
                    elif hasattr(self.gateway, 'updateCommeoDeviceValues'):
                        await self.gateway.updateCommeoDeviceValues(
                            device.id if hasattr(device, 'id') else int(dev_id)
                        )
                    await self._publish_state(dev_id)
                except Exception as e:
                    logger.warning(f"Failed to update device {dev_id}: {e}")
        except Exception as e:
            logger.error(f"Global update error: {e}")

    # ------------------------------------------------------------------
    # Learning / pairing
    # ------------------------------------------------------------------

    async def start_learning_mode(self, timeout_seconds: int = 30) -> bool:
        """Device learning mode (Spec Page 24)."""
        self.log.info('pairing_start')
        try:
            await self.gateway.scanStart()
            found_anything = False
            for _ in range(timeout_seconds):
                await asyncio.sleep(1)
                result = await self.gateway.scanResult()
                scan_state = result.scanState
                count = result.noNewDevices
                discovered_ids = result.foundIds
                try:
                    state_value = int(scan_state.value) if hasattr(scan_state, 'value') else int(scan_state)
                except (ValueError, TypeError):
                    continue
                if state_value == 1:  # RUN
                    if count > 0:
                        self.log.info('scan_progress', count=count)
                elif state_value == 3:  # END_SUCCESS
                    self.log.info('scan_finished', count=count)
                    for dev_id in discovered_ids:
                        self.log.info('save_dev', id=dev_id)
                        await self.gateway.deviceSave(dev_id)
                    found_anything = True
                    break
                elif state_value == 4:  # END_FAILED
                    self.log.error('err_scan_failed')
                    break
            await self.gateway.scanStop()
            return found_anything
        except Exception as e:
            logger.error(f"Critical error during learning mode: {e}")
            try:
                await self.gateway.scanStop()
            except Exception:
                pass
            return False

    async def start_sensor_learning_mode(self, timeout_seconds: int = 60) -> bool:
        """Sensor teach-in mode (Spec Page 38)."""
        self.log.info('sensor_teach_start')
        try:
            await self.gateway.sensorTeachStart()
            found_anything = False
            for _ in range(timeout_seconds):
                await asyncio.sleep(1)
                result = await self.gateway.sensorTeachResult()
                teach_state = result.teachState
                time_left = result.timeLeft
                sensor_id = result.foundId
                try:
                    state_value = int(teach_state.value) if hasattr(teach_state, 'value') else int(teach_state)
                except (ValueError, TypeError):
                    continue
                if state_value == 1:  # RUN
                    if _ % 10 == 0:
                        self.log.info('sensor_teach_progress', time=time_left)
                elif state_value == 2:  # END_SUCCESS
                    self.log.info('sensor_teach_success', id=sensor_id)
                    found_anything = True
                    break
            await self.gateway.sensorTeachStop()
            return found_anything
        except Exception as e:
            logger.error(f"Critical error during sensor teach-in: {e}")
            try:
                await self.gateway.sensorTeachStop()
            except Exception:
                pass
            return False

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    async def delete_device(self, device_id: str) -> bool:
        """Delete a device (Spec Page 35)."""
        try:
            self.log.info('del_dev', id=device_id)
            await self.gateway.deviceDelete(int(device_id))
            await self.discover()
            return True
        except Exception as e:
            logger.error(f"Error deleting device {device_id}: {e}")
            return False

    async def delete_sensor(self, sensor_id: str) -> bool:
        """Delete a sensor (Spec Page 44)."""
        try:
            self.log.info('del_sens', id=sensor_id)
            await self.gateway.sensorDelete(int(sensor_id))
            await self.discover()
            return True
        except Exception as e:
            logger.error(f"Error deleting sensor {sensor_id}: {e}")
            return False

    async def set_device_learning_mode(self, device_id: str, state: bool) -> bool:
        """Not supported by python-selve-new."""
        logger.warning(f"Device-specific learning mode not supported by library. Ignored for device {device_id}")
        return False

    async def get_device_senders(self, device_id: str) -> list:
        """Not supported by SELVE API."""
        logger.warning(
            f"get_device_senders({device_id}): SELVE API does not support querying "
            "senders paired to motors. Teach senders to gateway instead."
        )
        return []

    async def get_sender_info(self, sender_id: str) -> dict:
        """Get gateway sender info."""
        try:
            self.log.info('get_sender_info', id=sender_id)
            info = await self.gateway.senderGetInfo(int(sender_id))
            return {
                'id': sender_id,
                'name': getattr(info, 'name', 'Unknown'),
                'rfAddress': getattr(info, 'rfAddress', None),
                'rfChannel': getattr(info, 'rfChannel', None),
                'rfResetCount': getattr(info, 'rfResetCount', None),
            }
        except Exception as e:
            logger.error(f"Error retrieving sender info for {sender_id}: {e}")
            return {}

    async def set_sender_label(self, sender_id: str, new_label: str) -> bool:
        """Set sender label."""
        if len(new_label.encode('utf-8')) > LABEL_MAX_BYTES:
            self.log.error('err_name_too_long')
            return False
        try:
            self.log.info('set_sender_label', id=sender_id, name=new_label)
            await self.gateway.senderSetLabel(int(sender_id), new_label)
            await self.discover()
            await self.publish_discovery()
            return True
        except Exception as e:
            logger.error(f"Error setting sender label {sender_id}: {e}")
            return False

    async def delete_device_sender(self, device_id: str, sender_index: int) -> bool:
        """Delete a sender from the gateway."""
        try:
            self.log.info('del_sender', index=sender_index, id=device_id)
            await self.gateway.senderDelete(int(sender_index))
            await self.discover()
            return True
        except Exception as e:
            logger.error(f"Error deleting sender {sender_index} from device {device_id}: {e}")
            return False

    async def get_all_senders(self) -> list:
        """Get all senders taught to the gateway."""
        try:
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
                        'rfResetCount': getattr(info, 'rfResetCount', None),
                    })
                except Exception:
                    result.append({'id': str(sid), 'name': 'Unknown'})
            return result
        except Exception as e:
            logger.error(f"Error listing all senders: {e}")
            return []

    async def delete_sender_global(self, sender_id: str) -> bool:
        """Delete a sender globally."""
        try:
            if hasattr(self.gateway, 'senderDelete'):
                await self.gateway.senderDelete(int(sender_id))
                await self.discover()
                return True
            for dev_id in list(self.devices.keys()):
                try:
                    senders = await self.get_device_senders(dev_id)
                    for idx, s in enumerate(senders):
                        sid = None
                        if isinstance(s, dict):
                            sid = str(s.get('id') or s.get('senderId') or s.get('sender_id'))
                        elif isinstance(s, (list, tuple)) and len(s) >= 2:
                            sid = str(s[1])
                        else:
                            sid = str(s)
                        if sid == str(sender_id):
                            return await self.delete_device_sender(dev_id, idx)
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.error(f"Error deleting sender {sender_id}: {e}")
            return False

    async def get_sender_values(self, sender_id: str) -> dict:
        """Get sender values."""
        try:
            response = await self.gateway.senderGetValues(int(sender_id))
            return {
                'id': sender_id,
                'values': getattr(response, 'values', None),
                'state': getattr(response, 'state', None),
                'event': getattr(response, 'event', None),
            }
        except Exception as e:
            logger.error(f"Error retrieving sender values for {sender_id}: {e}")
            return {}

    async def start_sender_teach(self, timeout_seconds: int = 30) -> dict:
        """Start gateway sender teach-in and poll for results."""
        self.log.info('sender_teach_start')
        try:
            await self.gateway.senderTeachStart()
            for _ in range(timeout_seconds):
                await asyncio.sleep(1)
                try:
                    res = await self.gateway.senderTeachResult()
                except Exception:
                    continue
                if not res:
                    continue
                if hasattr(res, 'teachState'):
                    teach_state = res.teachState
                    sender_id = getattr(res, 'senderId', None)
                else:
                    continue
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
                elif state_value == 4:
                    try:
                        await self.gateway.senderTeachStop()
                    except Exception:
                        pass
                    return {'status': 'failed'}
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
        """Stop ongoing sender teach."""
        try:
            await self.gateway.senderTeachStop()
            return True
        except Exception as e:
            logger.error(f"Error stopping sender teach: {e}")
            return False

    async def save_group(self, group_id: int, name: str, device_ids: list) -> bool:
        """Create or update a group (Spec Page 51)."""
        if len(name.encode('utf-8')) > LABEL_MAX_BYTES:
            self.log.error('err_name_too_long')
            return False
        try:
            self.log.info('save_group', id=group_id, name=name)
            int_id = int(group_id)
            int_device_ids = [int(did) for did in device_ids]
            await self.gateway.groupWrite(int_id, dict.fromkeys(int_device_ids, 1), name)
            await self.discover()
            await self.publish_discovery()
            return True
        except Exception as e:
            logger.error(f"Error saving group {group_id}: {e}")
            return False

    async def delete_group(self, group_id: str) -> bool:
        """Delete a group (Spec Page 52)."""
        try:
            self.log.info('del_group', id=group_id)
            await self.gateway.groupDelete(int(group_id))
            await self.discover()
            await self.publish_discovery()
            return True
        except Exception as e:
            logger.error(f"Error deleting group {group_id}: {e}")
            return False

    async def rename_device(self, device_id: str, new_name: str) -> bool:
        """Rename a device (Spec Page 34)."""
        if len(new_name.encode('utf-8')) > LABEL_MAX_BYTES:
            self.log.error('err_name_too_long')
            return False
        try:
            self.log.info('rename_dev', id=device_id, name=new_name)
            await self.gateway.deviceSetLabel(int(device_id), new_name)
            await self.discover()
            await self.publish_discovery()
            return True
        except Exception as e:
            logger.error(f"Error renaming device {device_id}: {e}")
            return False

    async def rename_sensor(self, sensor_id: str, new_name: str) -> bool:
        """Rename a sensor (Spec Page 43)."""
        if len(new_name.encode('utf-8')) > LABEL_MAX_BYTES:
            self.log.error('err_name_too_long')
            return False
        try:
            self.log.info('rename_sens', id=sensor_id, name=new_name)
            await self.gateway.sensorSetLabel(int(sensor_id), new_name)
            await self.discover()
            await self.publish_discovery()
            return True
        except Exception as e:
            logger.error(f"Error renaming sensor {sensor_id}: {e}")
            return False

    async def reset_gateway(self) -> bool:
        """Reset the gateway (Spec Page 16)."""
        try:
            self.log.info('reset_gw')
            await self.gateway.reset()
            return True
        except Exception as e:
            logger.error(f"Failed to reset gateway: {e}")
            return False

    async def rename_gateway(self, new_name: str) -> bool:
        """Set gateway label (Spec Page 16)."""
        if len(new_name.encode('utf-8')) > LABEL_MAX_BYTES:
            self.log.error('err_name_too_long')
            return False
        logger.warning("Gateway label renaming not supported by python-selve-new")
        return True

    async def check_firmware(self) -> bool:
        """Fetch gateway version and serial number."""
        try:
            if isinstance(self.config, AppConfig):
                selve_cfg = self.config.selve
            else:
                selve_cfg = self.config.get('selve', {}) if isinstance(self.config, dict) else {}

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

            min_fw = selve_cfg.min_firmware_version if isinstance(selve_cfg, BaseModel) else selve_cfg.get('min_firmware_version')
            if min_fw and fw != 'N/A':
                if str(fw) < str(min_fw):
                    self.log.warning('fw_warn', fw=fw, min=min_fw)
                else:
                    self.log.info('fw_ok')

            fw_url = selve_cfg.firmware_url if isinstance(selve_cfg, BaseModel) else selve_cfg.get('firmware_url')
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

