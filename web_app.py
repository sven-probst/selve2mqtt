import json
import logging
from typing import Set, Optional
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Query, Header, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from translations import TRANSLATIONS

logger = logging.getLogger("selve2mqtt.web")
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
    
    mqtt_ok = mqtt_client.client.is_connected()
    # Basic check if gateway exists and is initialized
    selve_ok = manager.gateway is not None
    
    if not mqtt_ok or not selve_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "mqtt": mqtt_ok, "selve": selve_ok}
        )
    
    return {"status": "healthy"}

def get_dashboard_html(lang_code):
    t = TRANSLATIONS.get(lang_code, TRANSLATIONS['en'])['ui']
    html = """
<!DOCTYPE html>
<html lang="{lang_code}">
<head>
    <title>__TITLE__</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <style>
        body { font-family: Arial; margin: 20px; background-color: #f4f4f9; }
        .device { background: white; border: 1px solid #ccc; margin: 10px 0; padding: 15px; border-radius: 8px; }
        .sensor { background: #e9ecef; border: 1px solid #dee2e6; margin: 5px 0; padding: 10px; border-radius: 4px; display: inline-block; margin-right: 10px; min-width: 150px; }
        button { margin: 5px; padding: 8px 12px; cursor: pointer; background-color: #007bff; color: white; border: none; border-radius: 4px; }
        .delete-btn { background-color: #dc3545; }
        .delete-btn:hover { background-color: #c82333; }
        .pos { font-weight: bold; color: #28a745; }
        .rssi { font-style: italic; color: #6c757d; font-size: 0.9em; }
        .rssi-good { color: #28a745 !important; font-weight: bold; }
        .rssi-fair { color: #fd7e14 !important; font-weight: bold; }
        .rssi-poor { color: #dc3545 !important; font-weight: bold; }
        .status-online { color: #28a745; font-weight: bold; }
        .status-offline { color: #dc3545; font-weight: bold; }
        .sender-list { display: none; margin-top: 10px; font-size: 0.85em; background: #f8f9fa; padding: 10px; border: 1px dashed #ccc; border-radius: 4px; }
        .sender-list.active { display: block; }
        
        /* Modal Styles */
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
        .modal-content { background-color: white; margin: 10% auto; padding: 20px; border-radius: 8px; width: 400px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        .modal-header { border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-bottom: 15px; }
        .device-selection { max-height: 200px; overflow-y: auto; border: 1px solid #eee; padding: 10px; margin: 10px 0; }
        .device-item { display: block; padding: 5px; }
        .modal-footer { text-align: right; margin-top: 15px; }
        .auth-input { width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; margin: 8px 0; }
    </style>
    <style>
        /* Responsive tweaks for small screens */
        @media (max-width: 600px) {
            body { margin: 8px; font-size: 16px; }
            .device { padding: 12px; margin: 8px 0; }
            .device strong { display: block; margin-bottom: 8px; }
            .device button { display: block; width: 100%; box-sizing: border-box; margin: 6px 0; }
            .device input[type=range] { width: 100%; }
            .sensor { display: block; width: 100%; margin: 6px 0; }
            button { padding: 12px 14px; font-size: 16px; }
            .modal-content { width: 95%; margin: 8% auto; }
            .device-selection { max-height: 200px; }
            .rssi { display: block; margin-top: 6px; }
        }
    </style>
</head>
<body>
    <h1>__TITLE__</h1>
    <button onclick="startLearning()">{btn_learn_actor}</button>
    <button onclick="startSensorLearning()">{btn_learn_sensor}</button>
    <button onclick="startSenderTeach()">{btn_sender_teach_start}</button>
    <button onclick="stopSenderTeach()" class="delete-btn">{btn_sender_teach_stop}</button>
    <button onclick="resetGateway()" class="delete-btn">{btn_reset_gw}</button>
    <button onclick="setGatewayConfig('led', true)">{btn_led_on}</button>
    <button onclick="setGatewayConfig('led', false)">{btn_led_off}</button>
    <button onclick="saveGroupUI()">{btn_new_group}</button>
    
    <div class="device" style="background: #eee;">
        <strong>{gw_status}:</strong> <span id="gw-status">...</span> | 
        {duty_cycle}: <span id="gw-duty">0</span>% |
        MQTT: <span id="mqtt-status">...</span> |
        <span id="gw-info"></span> | <small>v{app_version}</small>
    </div>

    <p id="learning-status" style="font-weight: bold; color: #007bff;"></p>
    <p id="sender-learning-status" style="font-weight: bold; color: #007bff;"></p>

    <h3>{header_groups}</h3>
    <div id="groups-container"></div>

    <h3>{header_devices}</h3>
    <div id="devices-container"></div>

    <h3>{header_sensors}</h3>
    <div id="sensors-container"></div>

    <h3>{coupled_senders}</h3>
    <div id="senders-container"></div>

    <!-- Modal for Group Management -->
    <div id="group-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header"><h3>{btn_new_group}</h3></div>
            <label>{lbl_group_id}</label><br>
            <input type="number" id="group-id" min="0" max="63" style="width: 60px"><br><br>
            <label>{btn_rename}:</label><br>
            <input type="text" id="group-name" style="width: 100%"><br><br>
            <label>{header_devices}:</label>
            <div id="modal-device-list" class="device-selection"></div>
            <div class="modal-footer">
                <button onclick="closeModal()" class="delete-btn">{btn_stop}</button>
                <button onclick="submitGroup()">{btn_edit}</button>
            </div>
        </div>
    </div>
    <!-- Auth Modal -->
    <div id="auth-modal" class="modal" style="display:none; z-index:2000;">
        <div class="modal-content">
            <div class="modal-header"><h3>Authentication Required</h3></div>       
            <p>Please enter your access token:</p>
            <input type="password" id="token-input" class="auth-input" placeholder="Enter token...">
            <div id="auth-error" style="color:#dc3545; display:none; margin-top:10px;">Invalid token, please try again</div>
            <div class="modal-footer">
                <button onclick="login()">Login</button>
            </div>
        </div>
    </div>

    <script>
        let allDevices = {};
        const i18n = __I18N__;

        // Token handling for authenticated sessions
        const urlParams = new URLSearchParams(window.location.search);
        let AUTH_TOKEN = sessionStorage.getItem('selveToken') || urlParams.get('token') || '';
        let ws = null;

        function apiFetch(url, options = {}) {
            if (AUTH_TOKEN) {
                if (!options.headers) options.headers = {};
                options.headers['X-Access-Token'] = AUTH_TOKEN;
            }
            return fetch(url, options);
        }
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws${AUTH_TOKEN ? '?token=' + AUTH_TOKEN : ''}`;
            ws = new WebSocket(wsUrl);
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'full_state') {
                    renderFullState(data);
                } else if (data.type === 'device_update') {
                    updateDeviceUI(data);
                } else if (data.type === 'gateway_update') {
                    updateGateway(data.duty_cycle, data.duty_blocked);
                } else if (data.type === 'sensor_update') {
                    updateSensorUI(data);
                } else if (data.type === 'sender_update') {
                    updateSenderUI(data);
                } else if (data.type === 'mqtt_update') {
                    updateMqttStatus(data.connected);
                }
            };
            
            ws.onerror = (err) => {
                console.log('WebSocket error - showing auth modal');
                const modal = document.getElementById('auth-modal');
                console.log('Modal element:', modal);
                if (modal) {
                    modal.style.display = 'block';
                    console.log('Modal display set to block');
                } else {
                    console.error('auth-modal element not found in DOM!');
                }
            };
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                ws.send(JSON.stringify({type: 'request_full_state'}));
            };
        }

        // Start connection - auth modal will show on error
        connectWebSocket();

        function login() {
            AUTH_TOKEN = document.getElementById('token-input').value;
            if (AUTH_TOKEN) {
                sessionStorage.setItem('selveToken', AUTH_TOKEN);
                document.getElementById('auth-modal').style.display = 'none';
                // Reconnect WebSocket with new token
                if (ws) ws.close();
                connectWebSocket();
            }
        }

        

        function renderFullState(state) {
            const devCont = document.getElementById('devices-container');
            const grpCont = document.getElementById('groups-container');
            const sensCont = document.getElementById('sensors-container');
            
            allDevices = state.devices;
            devCont.innerHTML = '';
            Object.entries(state.devices).forEach(([id, dev]) => {
                devCont.innerHTML += `
                    <div class="device" id="dev-${id}">
                        <strong>${dev.name} (ID: ${id})</strong> 
                        [<span class="pos" id="pos-${id}">${dev.position}%</span>]
                        <span class="rssi" id="rssi-${id}">${dev.rssi !== null && dev.rssi !== undefined ? dev.rssi + ' ' + i18n.unit_dbm : 'N/A'}</span>
                        <br>
                        <button onclick="sendCommand('${id}', 'open')">${i18n.btn_open}</button>
                        <button onclick="sendCommand('${id}', 'stop')">${i18n.btn_stop}</button>
                        <button onclick="sendCommand('${id}', 'close')">${i18n.btn_close}</button>
                        <input type="range" min="0" max="100" value="${dev.position}"
                               id="slider-${id}"
                               onchange="sendPosition('${id}', this.value)">
                        <button onclick="renameDevice('${id}', '${dev.name}')">${i18n.btn_rename}</button>
                        <button onclick="deleteDevice('${id}')" class="delete-btn">${i18n.btn_delete}</button>
                    </div>`;
            });

            // Render Groups
            grpCont.innerHTML = '';
            Object.entries(state.groups).forEach(([id, grp]) => {
                grpCont.innerHTML += `
                    <div class="device" style="border-left: 5px solid #007bff">
                        <strong>${grp.name} (ID: ${id})</strong>
                        <br>
                        <button onclick="sendGroupCommand('${id}', 'open')">${i18n.btn_open}</button>
                        <button onclick="sendGroupCommand('${id}', 'stop')">${i18n.btn_stop}</button>
                        <button onclick="sendGroupCommand('${id}', 'close')">${i18n.btn_close}</button>
                        <button onclick="deleteGroup('${id}')" class="delete-btn">${i18n.btn_delete}</button>
                    </div>`;
            });

            // Render Sensors
            sensCont.innerHTML = '';
            Object.entries(state.sensors).forEach(([id, s]) => {
                sensCont.innerHTML += `
                    <div class="sensor" id="sens-${id}">
                        <strong>${s.name}</strong><br>
                        <span id="val-${id}">${s.value}</span> ${s.unit}
                        <br><small>${s.type}</small>
                    </div>`;
            });

            // Render Coupled Senders (gateway-taught only)
            const sendCont = document.getElementById('senders-container');
            sendCont.innerHTML = '';
            Object.entries(state.senders).forEach(([id, s]) => {
                sendCont.innerHTML += `
                    <div class="sensor" id="sender-${id}" style="border-left: 5px solid #28a745">
                        <strong>${s.name} (ID: ${id})</strong><br>
                        ${i18n.status}: <span id="s-evt-${id}">${s.last_event}</span>
                        <br>
                        <button onclick="renameSender('${id}', '${s.name}')">${i18n.btn_rename}</button>
                    </div>`;
            });

            updateGateway(state.gateway.duty_cycle, state.gateway.duty_blocked);
            
            if (state.mqtt_connected !== undefined) {
                updateMqttStatus(state.mqtt_connected);
            }

            document.getElementById('gw-info').innerText = `${i18n.hw_ver}: ${state.gateway.hardware} | ${i18n.fw_ver}: ${state.gateway.firmware}`;
        }

        function updateMqttStatus(connected) {
            const el = document.getElementById('mqtt-status');
            if (!el) return;
            el.innerText = connected ? (i18n.status_ok || 'OK') : (i18n.status_offline || 'Offline');
            el.className = connected ? 'status-online' : 'status-offline';
        }

        function viewSenders(id) {
            const div = document.getElementById(`senders-${id}`);
            div.classList.toggle('active');
            if (div.classList.contains('active')) {
                div.innerHTML = i18n.loading || 'Loading...';
                apiFetch(`/api/device/${id}/senders`)
                    .then(res => {
                        if (!res.ok && res.status === 401) {
                            div.innerHTML = 'Authentication required. Please provide token via ?token=xxx in URL.';
                            return null;
                        }
                        return res.json();
                    })
                    .then(senders => {
                        if (!senders) return;
                        if (senders && senders.length > 0) {
                            div.innerHTML = `<strong>${i18n.coupled_senders}:</strong><br>`;
                            senders.forEach(s => {
                                let sid = typeof s === 'object' ? (s.id || s.senderId) : s;
                                div.innerHTML += `ID: ${sid} <br>`;
                            });
                        } else {
                            div.innerHTML = i18n.no_senders || 'No senders found';
                        }
                    });
            }
        }

        function updateDeviceUI(dev) {
            const posEl = document.getElementById(`pos-${dev.id}`);
            if (posEl) posEl.innerText = dev.position + '%';
            const rssiEl = document.getElementById(`rssi-${dev.id}`);
            if (rssiEl) rssiEl.innerText = (dev.rssi !== null && dev.rssi !== undefined ? dev.rssi + ' ' + (i18n.unit_dbm || 'dBm') : 'N/A');
            // Update slider only when not actively dragged by the user
            const sliderEl = document.getElementById(`slider-${dev.id}`);
            if (sliderEl && document.activeElement !== sliderEl) {
                sliderEl.value = dev.position;
            }
        }

        function updateSenderUI(data) {
            const evtEl = document.getElementById(`s-evt-${data.id}`);
            if (evtEl) evtEl.innerText = data.event;
        }
        function updateSensorUI(data) {
            const valEl = document.getElementById(`val-${data.id}`);
            if (valEl) valEl.innerText = data.value;
        }

        function saveGroupUI() {
            const modal = document.getElementById('group-modal');
            const list = document.getElementById('modal-device-list');
            
            // Reset fields
            document.getElementById('group-id').value = '';
            document.getElementById('group-name').value = '';
            list.innerHTML = '';
            
            // Fill device list with checkboxes
            Object.entries(allDevices).forEach(([id, dev]) => {
                list.innerHTML += `
                    <label class="device-item">
                        <input type="checkbox" name="group-dev" value="${id}"> ${dev.name} (ID: ${id})
                    </label>`;
            });
            modal.style.display = 'block';
        }

        function closeModal() {
            document.getElementById('group-modal').style.display = 'none';
        }

        function submitGroup() {
            const id = document.getElementById('group-id').value;
            const name = document.getElementById('group-name').value;
            const device_ids = Array.from(document.querySelectorAll('input[name="group-dev"]:checked')).map(cb => cb.value);
            
            if(!id || !name) return alert(i18n.alert_id_name_required);

            apiFetch('/api/group/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: id, name: name, device_ids: device_ids})
            }).then(() => {
                closeModal();
                ws.send(JSON.stringify({type: 'request_full_state'}));
            });
        }

        function updateGateway(duty, blocked) {
            document.getElementById('gw-duty').innerText = duty;
            const status = document.getElementById('gw-status');
            status.innerText = blocked ? i18n.status_blocked || 'BLOCKED' : i18n.status_ok || 'OK';
            status.className = blocked ? 'status-offline' : 'status-online';
        }

        function sendCommand(id, cmd) { apiFetch("/api/device/" + id + "/" + cmd, {method: 'POST'}); }
        function sendPosition(id, pos) { apiFetch("/api/device/" + id + "/position?value=" + pos, {method: 'POST'}); }
        function sendGroupCommand(id, cmd) { apiFetch("/api/group/" + id + "/" + cmd, {method: 'POST'}); }
        function sendGroupPosition(id, pos) { apiFetch("/api/group/" + id + "/position?value=" + pos, {method: 'POST'}); }

        function deleteGroup(id) {
            if(confirm(i18n.confirm_del_group)) {
                apiFetch(`/api/group/${id}/delete`, {method: 'POST'})
                    .then(() => ws.send(JSON.stringify({type: 'request_full_state'})));
            }
        }

        function renameDevice(id, currentName) {
            const newName = prompt(i18n.prompt_new_name, currentName);
            if (newName && newName !== currentName) {
                apiFetch(`/api/device/${id}/rename?name=${encodeURIComponent(newName)}`, {method: 'POST'})
                    .then(() => ws.send(JSON.stringify({type: 'request_full_state'})));
            }
        }

        function renameSensor(id, currentName) {
            const newName = prompt(i18n.prompt_new_name, currentName);
            if (newName && newName !== currentName) {
                apiFetch(`/api/sensor/${id}/rename?name=${encodeURIComponent(newName)}`, {method: 'POST'})
                    .then(() => ws.send(JSON.stringify({type: 'request_full_state'})));
            }
        }

        function resetGateway() {
            if(confirm(i18n.confirm_reset)) {
                apiFetch('/api/gateway/reset', {method: 'POST'})
                    .then(res => res.json())
                    .then(data => alert(data.message || data.detail));
            }
        }

        function setGatewayConfig(setting, value) {
            apiFetch(`/api/gateway/config/${setting}?enabled=${value}`, {method: 'POST'});
        }

        function deleteDevice(id) { if(confirm(i18n.confirm_del_device)) apiFetch(`/api/device/${id}/delete`, {method: 'POST'}).then(() => ws.send(JSON.stringify({type: 'request_full_state'}))); }
        function deleteSensor(id) { if(confirm(i18n.confirm_del_sensor)) apiFetch(`/api/sensor/${id}/delete`, {method: 'POST'}).then(() => ws.send(JSON.stringify({type: 'request_full_state'}))); }

        function startLearning() {
            document.getElementById('learning-status').innerText = i18n.learning_active;
            apiFetch('/api/learn', {method: 'POST'}).then(() => {
                document.getElementById('learning-status').innerText = i18n.learning_finished || 'Done.';
                ws.send(JSON.stringify({type: 'request_full_state'}));
            });
        }

        function startSensorLearning() {
            document.getElementById('learning-status').innerText = i18n.learning_sensor_active;
            apiFetch('/api/learn_sensor', {method: 'POST'}).then(res => res.json()).then(data => {
                document.getElementById('learning-status').innerText = data.message;
                ws.send(JSON.stringify({type: 'request_full_state'}));
            });
        }

        function startSenderTeach(timeout=60) {
            document.getElementById('sender-learning-status').innerText = i18n.learning_sender_active || 'Sender teach active...';
            apiFetch(`/api/sender/teach?timeout=${timeout}`, {method: 'POST'})
                .then(res => res.json())
                .then(data => {
                    let msg = (i18n.result_prefix || 'Result: ') + (data.status || JSON.stringify(data));
                    if (data.sender) msg += ' - ' + data.sender;
                    document.getElementById('sender-learning-status').innerText = msg;
                    ws.send(JSON.stringify({type: 'request_full_state'}));
                }).catch(err => {
                    document.getElementById('sender-learning-status').innerText = i18n.error_start_sender || 'Error starting sender teach';
                });
        }

        function stopSenderTeach() {
            apiFetch('/api/sender/teach/stop', {method: 'POST'})
                .then(res => res.json())
                .then(data => {
                    document.getElementById('sender-learning-status').innerText = i18n.sender_teach_stopped || 'Sender teach stopped';
                    ws.send(JSON.stringify({type: 'request_full_state'}));
                }).catch(err => {
                    document.getElementById('sender-learning-status').innerText = i18n.error_stop_sender || 'Error stopping sender teach';
                });
        }
    </script>
</body>
</html>
"""
    # Fix JS/CSS braces (we used a raw template) and substitute i18n strings
    html = html.replace("{{", "{").replace("}}", "}")
    # Inject version into the translation dict scope for easy replacement
    t['lang_code'] = lang_code
    t['app_version'] = _app_version
    # Replace simple placeholders from the translation dict
    for key, val in t.items():
        try:
            html = html.replace("{" + key + "}", str(val))
        except Exception:
            pass
    html = html.replace("__TITLE__", t.get('title', 'Selve2MQTT'))
    html = html.replace("__I18N__", json.dumps(t))
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
                state['mqtt_connected'] = app.state.mqtt_client.client.is_connected()
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
