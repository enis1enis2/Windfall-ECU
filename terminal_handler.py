def setup_terminal_handlers(socketio):
    @socketio.on('connect_terminal')
    def handle_connect(data):
        from flask import session, request
        if 'user_id' not in session: return
        from server_manager import get_server_process
        sp = get_server_process(data.get('server_id'))
        if sp:
            sid = request.sid
            sp.output_callback = lambda msg, _sid=sid: socketio.emit('terminal_output', {'data': msg}, room=_sid)

    @socketio.on('terminal_input')
    def handle_input(data):
        from flask import session
        if 'user_id' not in session: return
        from server_manager import get_server_process
        sp = get_server_process(data.get('server_id'))
        if sp: sp.write_input(data.get('data', ''))
