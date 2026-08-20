import asyncio
import json
import logging
import threading
from typing import Set, Optional, Dict
from pathlib import Path
from functools import lru_cache
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Query, Header, status
from fastapi.security import HTTPBearer
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from translations import TRANSLATIONS
from common import setup_logger

from models import (
    DeviceCommand,
    DeviceRename,
    GroupSave,
    SensorRename,
    SenderRename,
    SenderTeachResult,
    LearningResult,
    StatusResponse,
)

logger = setup_logger("selve2mqtt.web")
active_websockets: Set[WebSocket] = set()
security = HTTPBearer(auto_error=False)

# Global token storage - will be set from main
_dashboard_token: Optional[str] = None

# Global version storage
_app_version: str = "dev"


def set_app_version(version: str):
    """Sets the application version to be displayed in the UI."""
    global _app_version
    _app_version = version


def set_dashboard_token(token: Optional[str]):
    """Sets the dashboard token from the main configuration."""
    global _dashboard_token
    _dashboard_token = token if token else None


def verify_token(
    token: Optional[str] = Query(None, description="Access token via query parameter"),
    x_access_token: Optional[str] = Header(None, description="Access token via X-Access-Token header"),
) -> bool:
    """
    Verify access token from query param or header.
    Returns True if authenticated or if no token is configured.
    """
    if not _dashboard_token:
        return True
    provided_token = token or x_access_token
    if provided_token and provided_token == _dashboard_token:
        return True
    return False


# Shared per-socket send locks so concurrent broadcasts never write to the
# same WebSocket at once (Starlette allows only one send at a time).
_ws_send_locks: Dict[WebSocket, "asyncio.Lock"] = {}
_ws_locks_guard = threading.Lock()


def _get_ws_lock(ws: WebSocket) -> "asyncio.Lock":
    with _ws_locks_guard:
        lock = _ws_send_locks.get(ws)
        if lock is None:
            lock = asyncio.Lock()
            _ws_send_locks[ws] = lock
        return lock


def _remove_ws(ws: WebSocket) -> None:
    """Drop a WebSocket from tracking (and its send lock).

    Only used at genuine connection teardown (endpoint exit / lifespan). A
    Broadcast must NOT remove a socket here: a transient send error does not
    mean the client is gone – removing it would silently kill live updates
    while the socket stays connected.
    """
    active_websockets.discard(ws)
    with _ws_locks_guard:
        _ws_send_locks.pop(ws, None)


async def safe_send_ws(ws: WebSocket, payload: dict) -> None:
    """Send a JSON payload to one WebSocket, serialized per socket.

    The sender acquires a per-socket lock so concurrent buffer overflows and
    interleaved frames are avoided. A single failed send does NOT remove the
    socket from tracking; real teardown is handled by the endpoint itself.
    """
    lock = _get_ws_lock(ws)
    async with lock:
        await ws.send_json(payload)


async def broadcast_status_update(message_type: str, data: dict):
    """Broadcasts a status update to all connected WebSockets."""
    if not active_websockets:
        return
    payload = {"type": message_type, **data}
    for ws in list(active_websockets):
        try:
            await safe_send_ws(ws, payload)
        except Exception:
            logger.debug("WebSocket send failed, socket left for endpoint cleanup", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for ws in list(active_websockets):
        _remove_ws(ws)
        try:
            await ws.close()
        except Exception:
            pass


app = FastAPI(title="Selve2MQTT Bridge", lifespan=lifespan)


# Custom validation error handler for Pydantic-powered endpoints
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a JSON 422 response with structured error details."""
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "detail": exc.errors(),
            "body": exc.body,
        },
    )


async def require_auth(
    token: Optional[str] = Query(None),
    x_access_token: Optional[str] = Header(None, alias="X-Access-Token"),
):
    """Dependency that raises 401 if token is required but invalid or missing."""
    if not verify_token(token, x_access_token):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide token via ?token=xxx or X-Access-Token header",
        )


# --- Middleware for global authentication (excludes websockets and /ws endpoint) ---

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Check authentication for all routes except /ws, static files, and health."""
    if not _dashboard_token:
        return await call_next(request)

    if request.url.path in ["/ws", "/favicon.ico", "/favicon.svg", "/health"]:
        return await call_next(request)

    if request.url.path == "/" and request.method == "GET":
        return await call_next(request)

    token = request.query_params.get("token") or request.headers.get("X-Access-Token")
    if token != _dashboard_token:
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Authentication required. Provide token via ?token=xxx or X-Access-Token header"
            },
        )
    return await call_next(request)


# --- Static files & dashboard ---

@app.get("/favicon.ico", include_in_schema=False)
async def get_favicon_ico():
    return FileResponse("Logo.svg", media_type="image/svg+xml")


@app.get("/favicon.svg", include_in_schema=False)
async def get_favicon_svg():
    return FileResponse("Logo.svg", media_type="image/svg+xml")


@app.get("/health", include_in_schema=False)
async def health_check():
    """Health check endpoint for Docker/K8s."""
    manager = app.state.selve_manager
    mqtt_client = app.state.mqtt_client
    mqtt_ok = mqtt_client.is_connected
    selve_ok = manager.gateway is not None
    if not mqtt_ok or not selve_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "mqtt": mqtt_ok, "selve": selve_ok},
        )
    return {"status": "healthy", "mqtt": mqtt_ok, "selve": selve_ok}


@lru_cache(maxsize=1)
def get_template() -> str:
    """Load the dashboard HTML template from external file."""
    template_path = Path(__file__).parent / "templates" / "dashboard.html"
    return template_path.read_text(encoding="utf-8")


def get_dashboard_html(lang_code):
    t = TRANSLATIONS.get(lang_code, TRANSLATIONS['en'])['ui'].copy()
    t['lang_code'] = lang_code
    t['app_version'] = _app_version
    html = get_template()
    html = html.replace("__TITLE__", t.get('title', 'Selve2MQTT'))
    html = html.replace("__I18N__", json.dumps(t))
    html = html.replace("{{", "{").replace("}}", "}")
    for key, val in t.items():
        try:
            html = html.replace("{" + key + "}", str(val))
        except Exception:
            pass
    return html


@app.get("/", response_class=HTMLResponse)
async def index():
    manager = app.state.selve_manager
    return get_dashboard_html(manager.lang_code)


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """WebSocket endpoint with optional token authentication."""
    if _dashboard_token and token != _dashboard_token:
        await websocket.close(code=1008, reason="Authentication failed")
        return
    await websocket.accept()
    active_websockets.add(websocket)
    manager = app.state.selve_manager
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get('type') == 'request_full_state':
                state = manager.get_full_state()
                state['mqtt_connected'] = app.state.mqtt_client.is_connected
                await safe_send_ws(websocket, state)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("WebSocket handler error (removing socket)", exc_info=True)
    finally:
        _remove_ws(websocket)
        try:
            await websocket.close(code=1000)
        except Exception:
            pass


# --- Device endpoints ---

@app.post(
    "/api/device/{device_id}/{command}",
    response_model=StatusResponse,
)
async def control_device(device_id: str, command: str, value: Optional[int] = Query(None)):
    """Send a command to a device.

    - `command`: one of `open`, `close`, `stop`, `position`, `pos1`, `pos2`
    - `value`: required only for `position` (0–100)
    """
    # Validate with Pydantic before dispatching
    try:
        cmd = DeviceCommand(command=command, value=value)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    await app.state.selve_manager.handle_command(device_id, cmd.command, cmd.value)
    return StatusResponse(status="ok")


@app.post(
    "/api/device/{device_id}/learning",
    response_model=StatusResponse,
)
async def device_learning(device_id: str, enabled: bool):
    await app.state.selve_manager.set_device_learning_mode(device_id, enabled)
    return StatusResponse(status="ok")


@app.post(
    "/api/device/{device_id}/sender/{sender_index}/delete",
    response_model=StatusResponse,
)
async def delete_device_sender(device_id: str, sender_index: int):
    if await app.state.selve_manager.delete_device_sender(device_id, sender_index):
        return StatusResponse(status="ok")
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api'].get('err_generic_fail', "Sender deletion failed"),
    )


@app.get("/api/device/{device_id}/senders")
async def get_device_senders(device_id: str):
    return await app.state.selve_manager.get_device_senders(device_id)


# --- Sender endpoints ---

@app.get("/api/sender/{sender_id}", response_model=dict)
async def get_sender(sender_id: str):
    info = await app.state.selve_manager.get_sender_info(sender_id)
    if info:
        return info
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=404,
        detail=manager.i18n['api'].get('not_found', "Sender not found"),
    )


@app.post(
    "/api/sender/{sender_id}/rename",
    response_model=StatusResponse,
)
async def rename_sender(sender_id: str, name: str):
    # Validate with Pydantic
    try:
        SenderRename(name=name)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    if await app.state.selve_manager.set_sender_label(sender_id, name):
        return StatusResponse(status="ok")
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api'].get('err_generic_fail', "Sender rename failed"),
    )


@app.get("/api/senders")
async def list_senders():
    return await app.state.selve_manager.get_all_senders()


@app.post(
    "/api/sender/{sender_id}/delete",
    response_model=StatusResponse,
)
async def delete_sender(sender_id: str):
    if await app.state.selve_manager.delete_sender_global(sender_id):
        return StatusResponse(status="ok")
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api'].get('err_generic_fail', "Sender deletion failed"),
    )


@app.get("/api/sender/{sender_id}/values")
async def sender_values(sender_id: str):
    vals = await app.state.selve_manager.get_sender_values(sender_id)
    if vals:
        return vals
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=404,
        detail=manager.i18n['api'].get('not_found', "Sender values not available"),
    )


@app.post(
    "/api/sender/teach",
    response_model=SenderTeachResult,
)
async def sender_teach(timeout: int = Query(default=60, ge=10, le=300)):
    """Start a global sender teach/pairing mode."""
    res = await app.state.selve_manager.start_sender_teach(timeout)
    if res.get('status') == 'not_supported':
        raise HTTPException(
            status_code=501,
            detail=app.state.selve_manager.i18n['api'].get('not_supported', 'Not supported by gateway'),
        )
    return SenderTeachResult(**res)


@app.post(
    "/api/sender/teach/stop",
    response_model=StatusResponse,
)
async def sender_teach_stop():
    ok = await app.state.selve_manager.stop_sender_teach()
    if ok:
        return StatusResponse(status="ok")
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api'].get('err_generic_fail', "Failed to stop sender teach or not supported"),
    )


# --- Group endpoints ---

@app.post(
    "/api/group/{group_id}/{command}",
    response_model=StatusResponse,
)
async def control_group(group_id: str, command: str, value: Optional[int] = Query(None)):
    """Send a command to a group."""
    try:
        cmd = DeviceCommand(command=command, value=value)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    await app.state.selve_manager.handle_command(group_id, cmd.command, cmd.value, is_group=True)
    return StatusResponse(status="ok")


@app.post(
    "/api/group/save",
    response_model=StatusResponse,
)
async def save_group(request: Request):
    """Create or update a group."""
    try:
        body = await request.json()
        payload = GroupSave(**body)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")

    if await app.state.selve_manager.save_group(payload.id, payload.name, payload.device_ids):
        return StatusResponse(status="ok")
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api'].get('err_generic_fail', "Group save failed"),
    )


@app.post(
    "/api/group/{group_id}/delete",
    response_model=StatusResponse,
)
async def delete_group(group_id: str):
    if await app.state.selve_manager.delete_group(group_id):
        return StatusResponse(status="ok")
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api'].get('err_generic_fail', "Group deletion failed"),
    )


# --- Gateway endpoints ---

@app.post(
    "/api/gateway/reset",
    response_model=StatusResponse,
)
async def reset_gateway():
    manager = app.state.selve_manager
    if await manager.reset_gateway():
        return StatusResponse(status="ok", message=manager.i18n['api']['gw_reset_success'])
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api']['gw_reset_failed'],
    )


@app.post(
    "/api/gateway/config/{setting}",
    response_model=StatusResponse,
)
async def set_gateway_config(setting: str, enabled: bool = Query(...)):
    """Toggle a gateway setting (led, forward)."""
    if setting == "led":
        await app.state.selve_manager.set_gateway_led(enabled)
    elif setting == "forward":
        await app.state.selve_manager.set_gateway_forwarding(enabled)
    else:
        raise HTTPException(
            status_code=400,
            detail=app.state.selve_manager.i18n['api']['err_unknown_setting'],
        )
    return StatusResponse(status="ok")


# --- Sensor endpoints ---

@app.post(
    "/api/sensor/{sensor_id}/rename",
    response_model=StatusResponse,
)
async def rename_sensor(sensor_id: str, name: str):
    try:
        SensorRename(name=name)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    if await app.state.selve_manager.rename_sensor(sensor_id, name):
        return StatusResponse(status="ok")
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api'].get('err_generic_fail', "Sensor renaming failed"),
    )


@app.post(
    "/api/device/{device_id}/rename",
    response_model=StatusResponse,
)
async def rename_device(device_id: str, name: str):
    try:
        DeviceRename(name=name)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    if await app.state.selve_manager.rename_device(device_id, name):
        return StatusResponse(status="ok")
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api'].get('err_generic_fail', "Device renaming failed"),
    )


@app.post(
    "/api/device/{device_id}/delete",
    response_model=StatusResponse,
)
async def delete_device(device_id: str):
    if await app.state.selve_manager.delete_device(device_id):
        return StatusResponse(status="ok")
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api'].get('err_generic_fail', "Device deletion failed"),
    )


@app.post(
    "/api/sensor/{sensor_id}/delete",
    response_model=StatusResponse,
)
async def delete_sensor(sensor_id: str):
    if await app.state.selve_manager.delete_sensor(sensor_id):
        return StatusResponse(status="ok")
    manager = app.state.selve_manager
    raise HTTPException(
        status_code=500,
        detail=manager.i18n['api'].get('err_generic_fail', "Sensor deletion failed"),
    )


@app.post(
    "/api/learn",
    response_model=LearningResult,
)
async def start_learning(timeout: int = Query(default=60, ge=10, le=300)):
    """Start device learning (actor) mode."""
    manager = app.state.selve_manager
    found = await manager.start_learning_mode(timeout)
    await manager.discover()
    if found:
        return LearningResult(
            status="success",
            message=manager.i18n['api']['learn_success'],
        )
    return LearningResult(
        status="timeout",
        message=manager.i18n['api']['learn_timeout'],
    )


@app.post(
    "/api/learn_sensor",
    response_model=LearningResult,
)
async def start_sensor_learning(timeout: int = Query(default=60, ge=10, le=300)):
    """Start sensor learning (teach-in) mode."""
    manager = app.state.selve_manager
    found = await manager.start_sensor_learning_mode(timeout)
    await manager.discover()
    if found:
        return LearningResult(
            status="success",
            message=manager.i18n['api']['sensor_success'],
        )
    return LearningResult(
        status="timeout",
        message=manager.i18n['api']['sensor_timeout'],
    )
