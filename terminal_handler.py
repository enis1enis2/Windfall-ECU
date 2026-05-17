from flask import request, session
from server_manager import get_server_process


def setup_terminal_handlers(socketio):
    @socketio.on('connect_terminal')
    def handle_connect(data):
        if 'user_id' not in session:
            return
        server_id = data.get('server_id')
        server_proc = get_server_process(server_id)
        if server_proc:
            sid = request.sid

            def send_output(msg):
                socketio.emit('terminal_output', {'data': msg}, room=sid)

            server_proc.output_callback = send_output

    @socketio.on('terminal_input')
    def handle_input(data):
        if 'user_id' not in session:
            return
        server_id = data.get('server_id')
        command = data.get('data', '')
        server_proc = get_server_process(server_id)
        if server_proc:
            server_proc.write_input(command)

    @socketio.on('terminal_resize')
    def handle_resize(data):
        pass
