import eventlet
eventlet.monkey_patch()

import os
import json
import shutil
from flask import Flask, render_template, request, jsonify, send_file, abort
from flask_socketio import SocketIO
from config import HOST, PORT, SECRET_KEY, SERVERS_DIR, BACKUPS_DIR
from models import init_db, get_servers, get_server, create_server, delete_server, update_server
from server_manager import (ServerProcess, get_server_process, register_server,
                            unregister_server, get_server_path, get_console_output)
from terminal_handler import setup_terminal_handlers
from backup_manager import list_backups, create_backup, restore_backup, delete_backup
from file_explorer import list_files, read_file, write_file, delete_entry, create_directory, upload_file
from zip_importer import import_zip
from docker_manager import check_docker
from server_downloader import get_types, get_versions, get_builds, download_server
from plugin_downloader import search_plugins, get_versions as plugin_get_versions, install_plugin, list_installed, delete_plugin

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024

socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

os.makedirs(SERVERS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)
init_db()

setup_terminal_handlers(socketio)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/servers', methods=['GET'])
def api_servers_list():
    servers = get_servers()
    result = []
    for s in servers:
        proc = get_server_process(s['id'])
        status = proc.get_status() if proc else {'running': False, 'pid': None}
        s['status'] = status
        result.append(s)
    return jsonify(result)


@app.route('/api/servers', methods=['POST'])
def api_servers_create():
    data = request.json
    name = data.get('name', 'New Server')
    java_args = data.get('java_args', '-Xmx1G -Xms1G')
    server_type = data.get('server_type', 'vanilla')

    safe_name = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in name)
    server_path = os.path.join(SERVERS_DIR, safe_name)
    os.makedirs(server_path, exist_ok=True)

    server_id = create_server(
        name=name,
        path=server_path,
        jar_file=data.get('jar_file'),
        java_args=java_args,
        server_type=server_type
    )
    return jsonify({'id': server_id, 'path': server_path}), 201


@app.route('/api/servers/<int:server_id>', methods=['GET'])
def api_server_get(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    proc = get_server_process(server_id)
    server['status'] = proc.get_status() if proc else {'running': False, 'pid': None}
    return jsonify(server)


@app.route('/api/servers/<int:server_id>', methods=['DELETE'])
def api_server_delete(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    unregister_server(server_id)
    if os.path.isdir(server['path']):
        shutil.rmtree(server['path'], ignore_errors=True)
    delete_server(server_id)
    return jsonify({'status': 'deleted'})


@app.route('/api/servers/<int:server_id>/start', methods=['POST'])
def api_server_start(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)

    existing = get_server_process(server_id)
    if existing and existing.is_running:
        return jsonify({'status': 'already running'})

    jar_path = os.path.join(server['path'], server['jar_file']) if server['jar_file'] else None
    if not jar_path or not os.path.isfile(jar_path):
        return jsonify({'error': f'JAR file not found: {jar_path}'}), 400

    proc = ServerProcess(server_id, server['path'], server['jar_file'], server['java_args'])
    ok = proc.start()
    if ok:
        register_server(server_id, proc)
        return jsonify({'status': 'started', 'pid': proc.process.pid if proc.process else None})
    else:
        return jsonify({'error': 'Failed to start server'}), 500


@app.route('/api/servers/<int:server_id>/stop', methods=['POST'])
def api_server_stop(server_id):
    proc = get_server_process(server_id)
    if not proc:
        return jsonify({'status': 'not running'})
    proc.stop()
    unregister_server(server_id)
    return jsonify({'status': 'stopped'})


@app.route('/api/servers/<int:server_id>/status', methods=['GET'])
def api_server_status(server_id):
    proc = get_server_process(server_id)
    if proc:
        return jsonify(proc.get_status())
    return jsonify({'running': False, 'pid': None})


@app.route('/api/servers/<int:server_id>/files', methods=['GET'])
def api_files_list(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    rel_path = request.args.get('path', '')
    result, error = list_files(server['path'], rel_path)
    if error:
        return jsonify({'error': error}), 400
    return jsonify(result)


@app.route('/api/servers/<int:server_id>/files/read', methods=['GET'])
def api_files_read(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    rel_path = request.args.get('path', '')
    content, error = read_file(server['path'], rel_path)
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'content': content})


@app.route('/api/servers/<int:server_id>/files/write', methods=['POST'])
def api_files_write(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    data = request.json
    ok, msg = write_file(server['path'], data['path'], data['content'])
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/servers/<int:server_id>/files/delete', methods=['POST'])
def api_files_delete(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    data = request.json
    ok, msg = delete_entry(server['path'], data['path'])
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/servers/<int:server_id>/files/mkdir', methods=['POST'])
def api_files_mkdir(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    data = request.json
    ok, msg = create_directory(server['path'], data.get('path', ''), data['name'])
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/servers/<int:server_id>/files/upload', methods=['POST'])
def api_files_upload(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    rel_path = request.form.get('path', '')
    ok, msg = upload_file(server['path'], rel_path, file.filename, file.read())
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/servers/<int:server_id>/files/download', methods=['GET'])
def api_files_download(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    rel_path = request.args.get('path', '')
    full_path = os.path.normpath(os.path.join(server['path'], rel_path))
    if not full_path.startswith(os.path.normpath(server['path'])):
        abort(403)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, as_attachment=True)


@app.route('/api/servers/<int:server_id>/backups', methods=['GET'])
def api_backups_list(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    return jsonify(list_backups(server_id))


@app.route('/api/servers/<int:server_id>/backups', methods=['POST'])
def api_backups_create(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    data = request.json or {}
    backup_id, error = create_backup(server_id, data.get('name'))
    if error:
        return jsonify({'error': error}), 500
    return jsonify({'id': backup_id}), 201


@app.route('/api/backups/<int:backup_id>/restore', methods=['POST'])
def api_backups_restore(backup_id):
    ok, msg = restore_backup(backup_id)
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/backups/<int:backup_id>', methods=['DELETE'])
def api_backups_delete(backup_id):
    ok, msg = delete_backup(backup_id)
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/import/zip', methods=['POST'])
def api_import_zip():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'File must be a .zip'}), 400
    server_name = request.form.get('name')
    server_id, error = import_zip(file, server_name)
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'id': server_id, 'status': 'imported'}), 201


@app.route('/api/servers/<int:server_id>/console', methods=['GET'])
def api_console(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    proc = get_server_process(server_id)
    running = bool(proc and proc.is_running)
    output = ''
    pos = 0
    if proc:
        output, pos = get_console_output(server_id)
    if not output:
        log_file = os.path.join(server['path'], 'logs', 'latest.log')
        if os.path.isfile(log_file):
            try:
                with open(log_file, 'r', errors='replace') as f:
                    output = f.read()
                    pos = len(output)
            except (OSError, PermissionError):
                pass
    return jsonify({'output': output, 'pos': pos, 'running': running})


@app.route('/api/system/docker', methods=['GET'])
def api_docker_check():
    return jsonify({'available': check_docker()})


@app.route('/api/settings', methods=['GET'])
def api_settings_get():
    from models import get_setting
    return jsonify({
        'port': get_setting('port', '25565'),
        'docker_enabled': get_setting('docker_enabled', 'false')
    })


@app.route('/api/settings', methods=['POST'])
def api_settings_set():
    from models import set_setting
    data = request.json
    for key, value in data.items():
        set_setting(key, str(value))
    return jsonify({'status': 'saved'})


@app.route('/api/servers/<int:server_id>/java_args', methods=['PUT'])
def api_server_java_args(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    data = request.json
    java_args = data.get('java_args', '-Xmx1G -Xms1G')
    update_server(server_id, java_args=java_args)
    return jsonify({'status': 'updated', 'java_args': java_args})


@app.route('/api/download/types', methods=['GET'])
def api_download_types():
    return jsonify(get_types())


@app.route('/api/download/versions/<server_type>', methods=['GET'])
def api_download_versions(server_type):
    try:
        versions = get_versions(server_type)
        return jsonify(versions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/builds/<server_type>/<version>', methods=['GET'])
def api_download_builds(server_type, version):
    try:
        builds = get_builds(server_type, version)
        return jsonify(builds)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.json
    server_type = data.get('type')
    version = data.get('version')
    build = data.get('build')
    server_name = data.get('name')

    if not server_type or not version:
        return jsonify({'error': 'type and version required'}), 400

    try:
        server_id, error = download_server(server_type, version, build, server_name)
        if error:
            return jsonify({'error': error}), 400
        return jsonify({'id': server_id, 'status': 'downloaded'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plugins/search', methods=['GET'])
def api_plugins_search():
    q = request.args.get('q', '')
    provider = request.args.get('provider')
    if len(q) < 2:
        return jsonify([])
    try:
        results = search_plugins(q, provider)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plugins/versions/<provider>/<project_id>', methods=['GET'])
def api_plugin_versions(provider, project_id):
    try:
        versions = plugin_get_versions(provider, project_id)
        return jsonify(versions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plugins/install', methods=['POST'])
def api_plugin_install():
    data = request.json
    server_id = data.get('server_id')
    provider = data.get('provider')
    project_id = data.get('project_id')
    version_id = data.get('version_id')
    version_number = data.get('version_number')

    if not all([server_id, provider, project_id]):
        return jsonify({'error': 'server_id, provider, project_id required'}), 400

    ok, msg = install_plugin(server_id, provider, project_id, version_id, version_number)
    if ok:
        return jsonify({'status': msg})
    return jsonify({'error': msg}), 400


@app.route('/api/servers/<int:server_id>/plugins', methods=['GET'])
def api_plugins_list(server_id):
    return jsonify(list_installed(server_id))


@app.route('/api/servers/<int:server_id>/plugins/<filename>', methods=['DELETE'])
def api_plugin_delete(server_id, filename):
    ok, msg = delete_plugin(server_id, filename)
    if ok:
        return jsonify({'status': msg})
    return jsonify({'error': msg}), 400


if __name__ == '__main__':
    print(f'GreatPanel starting on {HOST}:{PORT}')
    socketio.run(app, host=HOST, port=PORT, allow_unsafe_werkzeug=True)
