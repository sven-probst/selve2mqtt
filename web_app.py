import json
import logging
from typing import Set, Optional
from pathlib import Path
from functools import lru_cache
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Query, Header, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from translations import TRANSLATIONS
from common import setup_logger

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
    x_access_token: Optional[str] = Header(None, description="Access token via X-Access-Token header")
) -> bool:
    """
    Verify access token from query param or header.
    Returns True if authenticated or if no token is configured.
    """
    if not _dashboard_token:
        # No token configured - auth disabled
        return True
    
    # Check query param first, then header
    provided_token = token or x_access_token
    if provided_token and provided_token == _dashboard_token:
        return True
    
    return False

async def broadcast_status_update(message_type: str, data: dict):
    """Broadcasts a status update to all connected WebSockets."""
    if not active_websockets:
        return
    payload = {"type": message_type, **data}
    for ws in list(active_websockets):
        try:
            await ws.send_json(payload)
        except Exception:
            pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for ws in list(active_websockets):
        await ws.close()

app = FastAPI(title="Selve2MQTT Bridge", lifespan=lifespan)

async def require_auth(
    token: Optional[str] = Query(None),
    x_access_token: Optional[str] = Header(None, alias="X-Access-Token")
):
    """Dependency that raises 401 if token is required but invalid or missing."""
    if not verify_token(token, x_access_token):
        raise HTTPException(status_code=401, detail="Authentication required. Provide token via ?token=xxx or X-Access-Token header")


# --- Middleware for global authentication (excludes websockets and /ws endpoint) ---

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Middleware that checks authentication for all routes except:
    - Static assets (if any)
    - /ws WebSocket endpoint (handled separately)
    """
    # Skip authentication if no token configured
    if not _dashboard_token:
        return await call_next(request)
    
    # Skip /ws endpoint and favicon assets
    if request.url.path in ["/ws", "/favicon.ico", "/favicon.svg", "/health"]:
        return await call_next(request)
    
    # Allow the root path so the dashboard can load its own auth modal
    if request.url.path == "/" and request.method == "GET":
        return await call_next(request)

    # Check token from query or header
    token = request.query_params.get("token") or request.headers.get("X-Access-Token")
    if token != _dashboard_token:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required. Provide token via ?token=xxx or X-Access-Token header"}
        )
    
    return await call_next(request)

@app.get("/favicon.ico", include_in_schema=False)
async def get_favicon_ico():
    # Serve the SVG as favicon.ico for broader compatibility
    return FileResponse("Logo.svg", media_type="image/svg+xml")

@app.get("/favicon.svg", include_in_schema=False)
async def get_favicon_svg():
    # Serve the SVG directly
    return FileResponse("Logo.svg", media_type="image/svg+xml")


@app.get("/health", include_in_schema=False)
async def health_check():
    """Health check endpoint for Docker/K8s."""
    manager = app.state.selve_manager
    mqtt_client = app.state.mqtt_client
    
    mqtt_ok = mqtt_client.is_connected
    # Basic check if gateway exists and is initialized
    selve_ok = manager.gateway is not None
    
    if not mqtt_ok or not selve_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "mqtt": mqtt_ok, "selve": selve_ok}
        )
    
    return {"status": "healthy"}

@lru_cache(maxsize=1)
def get_template() -> str:
    """Loads the dashboard HTML template from external file."""
    template_path = Path(__file__).parent / "templates" / "dashboard.html"
    return template_path.read_text(encoding="utf-8")

def get_dashboard_html(lang_code):
    # Nutze .copy(), um das globale TRANSLATIONS Dictionary nicht zu verändern
    t = TRANSLATIONS.get(lang_code, TRANSLATIONS['en'])['ui'].copy()

    # Metadaten injizieren, BEVOR das JSON für das Frontend generiert wird
    t['lang_code'] = lang_code
    t['app_version'] = _app_version

    html = get_template()
    # Replace placeholders
    html = html.replace("__TITLE__", t.get('title', 'Selve2MQTT'))
    html = html.replace("__I18N__", json.dumps(t))
    html = html.replace("{{", "{").replace("}}", "}")
    # Replace translation placeholders
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """WebSocket endpoint with optional token authentication."""
    # Check authentication if token is configured
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
                # Inject current MQTT status into the initial state
                state['mqtt_connected'] = app.state.mqtt_client.is_connected
                await websocket.send_json(state)
    except WebSocketDisconnect:
        active_websockets.remove(websocket)

@app.post("/api/device/{device_id}/{command}")
async def control_device(device_id: str, command: str, value: Optional[int] = None):
    await app.state.selve_manager.handle_command(device_id, command, value)
    return {"status": "ok"}

@app.post("/api/device/{device_id}/learning")
async def device_learning(device_id: str, enabled: bool):
    await app.state.selve_manager.set_device_learning_mode(device_id, enabled)
    return {"status": "ok"}

@app.post("/api/device/{device_id}/sender/{sender_index}/delete")
async def delete_device_sender(device_id: str, sender_index: int):
    if await app.state.selve_manager.delete_device_sender(device_id, sender_index):
        return {"status": "ok"}
    manager = app.state.selve_manager
    raise HTTPException(status_code=500, detail=manager.i18n['api'].get('err_generic_fail', "Sender deletion failed"))

@app.get("/api/device/{device_id}/senders")
async def get_device_senders(device_id: str):
    return await app.state.selve_manager.get_device_senders(device_id)


@app.get("/api/sender/{sender_id}")
async def get_sender(sender_id: str):
    info = await app.state.selve_manager.get_sender_info(sender_id)
    if info:
        return info
    manager = app.state.selve_manager
    raise HTTPException(status_code=404, detail=manager.i18n['api'].get('not_found', "Sender not found"))


@app.post("/api/sender/{sender_id}/rename")
async def rename_sender(sender_id: str, name: str):
    if await app.state.selve_manager.set_sender_label(sender_id, name):
        return {"status": "ok"}
    manager = app.state.selve_manager
    raise HTTPException(status_code=500, detail=manager.i18n['api'].get('err_generic_fail', "Sender rename failed"))


@app.get("/api/senders")
async def list_senders():
    return await app.state.selve_manager.get_all_senders()


@app.post("/api/sender/{sender_id}/delete")
async def delete_sender(sender_id: str):
    if await app.state.selve_manager.delete_sender_global(sender_id):
        return {"status": "ok"}
    manager = app.state.selve_manager
    raise HTTPException(status_code=500, detail=manager.i18n['api'].get('err_generic_fail', "Sender deletion failed"))


@app.get("/api/sender/{sender_id}/values")
async def sender_values(sender_id: str):
    vals = await app.state.selve_manager.get_sender_values(sender_id)
    if vals:
        return vals
    manager = app.state.selve_manager
    raise HTTPException(status_code=404, detail=manager.i18n['api'].get('not_found', "Sender values not available"))


@app.post("/api/sender/teach")
async def sender_teach(timeout: int = 60):
    """Starts a global sender teach/pairing mode. Returns status and discovered sender id on success."""
    res = await app.state.selve_manager.start_sender_teach(timeout)
    if res.get('status') == 'not_supported':
        raise HTTPException(status_code=501, detail=app.state.selve_manager.i18n['api'].get('not_supported', 'Not supported by gateway'))
    return res


@app.post("/api/sender/teach/stop")
async def sender_teach_stop():
    ok = await app.state.selve_manager.stop_sender_teach()
    if ok:
        return {"status": "ok"}
    manager = app.state.selve_manager
    raise HTTPException(status_code=500, detail=manager.i18n['api'].get('err_generic_fail', "Failed to stop sender teach or not supported"))

@app.post("/api/group/{group_id}/{command}")
async def control_group(group_id: str, command: str, value: Optional[int] = None):
    await app.state.selve_manager.handle_command(group_id, command, value, is_group=True)
    return {"status": "ok"}

@app.post("/api/group/save")
async def save_group(request: Request):
    data = await request.json()
    group_id = data.get("id")
    name = data.get("name")
    device_ids = data.get("device_ids", [])
    if await app.state.selve_manager.save_group(group_id, name, device_ids):
        return {"status": "ok"}
    manager = app.state.selve_manager
    raise HTTPException(status_code=500, detail=manager.i18n['api'].get('err_generic_fail', "Group save failed"))

@app.post("/api/group/{group_id}/delete")
async def delete_group(group_id: str):
    if await app.state.selve_manager.delete_group(group_id):
        return {"status": "ok"}
    manager = app.state.selve_manager
    raise HTTPException(status_code=500, detail=manager.i18n['api'].get('err_generic_fail', "Group deletion failed"))

@app.post("/api/gateway/reset")
async def reset_gateway():
    manager = app.state.selve_manager
    if await manager.reset_gateway():
        return {"status": "ok", "message": manager.i18n['api']['gw_reset_success']}
    raise HTTPException(status_code=500, detail=manager.i18n['api']['gw_reset_failed'])

@app.post("/api/gateway/config/{setting}")
async def set_gateway_config(setting: str, enabled: bool):
    if setting == "led":
        await app.state.selve_manager.set_gateway_led(enabled)
    elif setting == "forward":
        await app.state.selve_manager.set_gateway_forwarding(enabled)
    else:
        raise HTTPException(status_code=400, detail=app.state.selve_manager.i18n['api']['err_unknown_setting'])
    return {"status": "ok"}

@app.post("/api/sensor/{sensor_id}/rename")
async def rename_sensor(sensor_id: str, name: str):
    if await app.state.selve_manager.rename_sensor(sensor_id, name):
        return {"status": "ok"}
    manager = app.state.selve_manager
    raise HTTPException(status_code=500, detail=manager.i18n['api'].get('err_generic_fail', "Sensor renaming failed"))

@app.post("/api/device/{device_id}/rename")
async def rename_device(device_id: str, name: str):
    if await app.state.selve_manager.rename_device(device_id, name):
        return {"status": "ok"}
    manager = app.state.selve_manager
    raise HTTPException(status_code=500, detail=manager.i18n['api'].get('err_generic_fail', "Device renaming failed"))

@app.post("/api/device/{device_id}/delete")
async def delete_device(device_id: str):
    if await app.state.selve_manager.delete_device(device_id):
        return {"status": "ok"}
    manager = app.state.selve_manager
    raise HTTPException(status_code=500, detail=manager.i18n['api'].get('err_generic_fail', "Device deletion failed"))

@app.post("/api/sensor/{sensor_id}/delete")
async def delete_sensor(sensor_id: str):
    if await app.state.selve_manager.delete_sensor(sensor_id):
        return {"status": "ok"}
    manager = app.state.selve_manager
    raise HTTPException(status_code=500, detail=manager.i18n['api'].get('err_generic_fail', "Sensor deletion failed"))

@app.post("/api/learn")
async def start_learning(timeout: int = 60):
    manager = app.state.selve_manager
    # Triggering learning mode
    found = await manager.start_learning_mode(timeout)
    # Always refresh to ensure we have the latest state from the gateway
    await manager.discover()
    if found:
        return {"status": "success", "message": manager.i18n['api']['learn_success']}
    return {"status": "timeout", "message": manager.i18n['api']['learn_timeout']}

@app.post("/api/learn_sensor")
async def start_sensor_learning(timeout: int = 60):
    manager = app.state.selve_manager
    # Triggering sensor teach-in mode (Spec Page 38)
    found = await manager.start_sensor_learning_mode(timeout)
    await manager.discover()
    if found:
        return {"status": "success", "message": manager.i18n['api']['sensor_success']}
    return {"status": "timeout", "message": manager.i18n['api']['sensor_timeout']}
