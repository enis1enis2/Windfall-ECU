from flask import request, session
from server_manager import get_server_process

def setup_terminal_handlers(socketio):
    @socketio.on('connect_terminal')
    def handle_connect(data):
        if 'user_id' not in session: return
        sp = get_server_process(data.get('server_id'))
        if sp:
            sid = request.sid
            sp.output_callback = lambda msg: socketio.emit('terminal_output', {'data': msg}, room=sid)

    @socketio.on('terminal_input')
    def handle_input(data):
        if 'user_id' not in session: return
        sp = get_server_process(data.get('server_id'))
        if sp: sp.write_input(data.get('data', ''))

    @socketio.on('terminal_resize')
    def handle_resize(data): pass
