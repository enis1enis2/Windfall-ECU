import eventlet
eventlet.monkey_patch()

import os
import json
import shutil
from flask import Flask, render_template, request, jsonify, send_file, abort, session
from flask_socketio import SocketIO
from config import HOST, PORT, SECRET_KEY, SERVERS_DIR, BACKUPS_DIR
from models import init_db, get_servers, get_server, create_server, delete_server, update_server
from server_manager import (ServerProcess, get_server_process, register_server,
                            unregister_server, get_server_path, clean_output)
from terminal_handler import setup_terminal_handlers
from backup_manager import list_backups, create_backup, restore_backup, delete_backup
from file_explorer import list_files, read_file, write_file, delete_entry, create_directory, upload_file
from zip_importer import import_zip
from docker_manager import check_docker
from server_downloader import get_types, get_versions, get_builds, download_server
from plugin_downloader import search_plugins, get_versions as plugin_get_versions, install_plugin, list_installed, delete_plugin
from auth import (login_required, require_permission, register_user, verify_user,
                   init_auth, get_users, get_user_by_id, change_password,
                   change_username, change_role, delete_user, create_user, ROLES)
from auto_backup import start_auto_backup_scheduler
from update_manager import check_updates, install_updates, schedule_restart

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024

socketio = SocketIO(app, cors_allowed_origins=os.environ.get('GREATPANEL_ORIGIN', 'http://localhost:8080'), async_mode='eventlet')

os.makedirs(SERVERS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

# Kill any leftover process on the same port
import subprocess as _sp
for _cmd in [['fuser', '-k', f'{PORT}/tcp'], ['lsof', '-ti', f'tcp:{PORT}']]:
    try:
        _r = _sp.run(_cmd, capture_output=True, text=True, timeout=5)
        if _cmd[0] == 'lsof' and _r.stdout.strip():
            for _pid in _r.stdout.strip().splitlines():
                _sp.run(['kill', '-9', _pid], capture_output=True, timeout=3)
        break
    except FileNotFoundError:
        continue
    except Exception:
        pass

init_db()
init_auth()

setup_terminal_handlers(socketio)

start_auto_backup_scheduler()


@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template('login.html')
    return render_template('index.html')


# --- Auth routes ---

@app.route('/api/auth/status', methods=['GET'])
def api_auth_status():
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'username': session.get('username'),
            'user_id': session.get('user_id'),
            'role': session.get('role', 'viewer')
        })
    return jsonify({'authenticated': False})


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    user_id, role = verify_user(username, password)
    if user_id:
        session['user_id'] = user_id
        session['username'] = username
        session['role'] = role
        return jsonify({'status': 'ok', 'username': username, 'role': role})
    return jsonify({'error': 'Invalid username or password'}), 401


@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    ok, msg = register_user(username, password)
    if ok:
        user_id, role = verify_user(username, password)
        session['user_id'] = user_id
        session['username'] = username
        session['role'] = role
        return jsonify({'status': 'ok', 'username': username, 'role': role}), 201
    return jsonify({'error': msg}), 400


@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    session.clear()
    return jsonify({'status': 'logged out'})


# --- User management ---

@app.route('/api/users', methods=['GET'])
@login_required
@require_permission('users:manage')
def api_users_list():
    return jsonify(get_users())


@app.route('/api/users', methods=['POST'])
@login_required
@require_permission('users:manage')
def api_users_create():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'viewer')
    ok, msg = create_user(username, password, role)
    if ok:
        return jsonify({'status': 'created'}), 201
    return jsonify({'error': msg}), 400


@app.route('/api/users/<int:user_id>', methods=['PATCH'])
@login_required
@require_permission('users:manage')
def api_user_update(user_id):
    user = get_user_by_id(user_id)
    if not user:
        abort(404)
    data = request.json
    if 'password' in data:
        ok, msg = change_password(user_id, data['password'])
        if not ok:
            return jsonify({'error': msg}), 400
    if 'username' in data:
        ok, msg = change_username(user_id, data['username'])
        if not ok:
            return jsonify({'error': msg}), 400
    if 'role' in data:
        ok, msg = change_role(user_id, data['role'])
        if not ok:
            return jsonify({'error': msg}), 400
    return jsonify({'status': 'updated'})


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@require_permission('users:manage')
def api_user_delete(user_id):
    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot delete your own account'}), 400
    ok, msg = delete_user(user_id)
    if not ok:
        return jsonify({'error': msg}), 400
    return jsonify({'status': 'deleted'})


@app.route('/api/users/roles', methods=['GET'])
@login_required
@require_permission('users:manage')
def api_users_roles():
    return jsonify({k: {'name': v['name'], 'permissions': sorted(v['permissions'])} for k, v in ROLES.items()})


# --- API routes ---

@app.route('/api/servers', methods=['GET'])
@login_required
@require_permission('servers:list')
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
@login_required
@require_permission('servers:create')
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
@login_required
@require_permission('servers:get')
def api_server_get(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    proc = get_server_process(server_id)
    server['status'] = proc.get_status() if proc else {'running': False, 'pid': None}
    return jsonify(server)


@app.route('/api/servers/<int:server_id>', methods=['DELETE'])
@login_required
@require_permission('servers:delete')
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
@login_required
@require_permission('servers:start')
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
@login_required
@require_permission('servers:stop')
def api_server_stop(server_id):
    proc = get_server_process(server_id)
    if not proc:
        return jsonify({'status': 'not running'})
    proc.stop()
    unregister_server(server_id)
    return jsonify({'status': 'stopped'})


@app.route('/api/servers/<int:server_id>/restart', methods=['POST'])
@login_required
@require_permission('servers:restart')
def api_server_restart(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    proc = get_server_process(server_id)
    if proc:
        proc.stop()
        unregister_server(server_id)
        eventlet.sleep(1)
    jar_path = os.path.join(server['path'], server['jar_file']) if server['jar_file'] else None
    if not jar_path or not os.path.isfile(jar_path):
        return jsonify({'error': f'JAR file not found: {jar_path}'}), 400
    proc = ServerProcess(server_id, server['path'], server['jar_file'], server['java_args'])
    ok = proc.start()
    if ok:
        register_server(server_id, proc)
        return jsonify({'status': 'restarted', 'pid': proc.process.pid if proc.process else None})
    else:
        return jsonify({'error': 'Failed to restart server'}), 500


@app.route('/api/servers/<int:server_id>/status', methods=['GET'])
@login_required
@require_permission('servers:status')
def api_server_status(server_id):
    proc = get_server_process(server_id)
    if proc:
        return jsonify(proc.get_status())
    return jsonify({'running': False, 'pid': None})


@app.route('/api/servers/<int:server_id>/files', methods=['GET'])
@login_required
@require_permission('files:list')
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
@login_required
@require_permission('files:read')
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
@login_required
@require_permission('files:write')
def api_files_write(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    data = request.json
    ok, msg = write_file(server['path'], data['path'], data['content'])
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/servers/<int:server_id>/files/delete', methods=['POST'])
@login_required
@require_permission('files:delete')
def api_files_delete(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    data = request.json
    ok, msg = delete_entry(server['path'], data['path'])
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/servers/<int:server_id>/files/mkdir', methods=['POST'])
@login_required
@require_permission('files:mkdir')
def api_files_mkdir(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    data = request.json
    ok, msg = create_directory(server['path'], data.get('path', ''), data['name'])
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/servers/<int:server_id>/files/upload', methods=['POST'])
@login_required
@require_permission('files:upload')
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
@login_required
@require_permission('files:download')
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
@login_required
@require_permission('backups:list')
def api_backups_list(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    return jsonify(list_backups(server_id))


@app.route('/api/servers/<int:server_id>/backups', methods=['POST'])
@login_required
@require_permission('backups:create')
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
@login_required
@require_permission('backups:restore')
def api_backups_restore(backup_id):
    ok, msg = restore_backup(backup_id)
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/backups/<int:backup_id>', methods=['DELETE'])
@login_required
@require_permission('backups:delete')
def api_backups_delete(backup_id):
    ok, msg = delete_backup(backup_id)
    return jsonify({'status': msg}), 200 if ok else 400


@app.route('/api/import/zip', methods=['POST'])
@login_required
@require_permission('import:zip')
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
    from models import get_server
    srv = get_server(server_id)
    return jsonify({'id': server_id, 'name': srv['name'] if srv else server_name, 'status': 'imported'}), 201


@app.route('/api/servers/<int:server_id>/console', methods=['GET'])
@login_required
@require_permission('servers:console')
def api_console(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    proc = get_server_process(server_id)
    running = bool(proc and proc.is_running)

    since = request.args.get('since', 0, type=int)
    output = ''
    total = 0

    if proc:
        output, total = proc.buffer.get_since(since)
    else:
        MAX_CONSOLE_BYTES = 5 * 1024 * 1024
        log_file = os.path.join(server['path'], 'logs', 'latest.log')
        if os.path.isfile(log_file):
            try:
                file_size = os.path.getsize(log_file)
                with open(log_file, 'r', errors='replace') as f:
                    if file_size > MAX_CONSOLE_BYTES:
                        f.seek(file_size - MAX_CONSOLE_BYTES)
                        f.readline()
                    text = clean_output(f.read())
                    lines = text.splitlines(True)
                    total = len(lines)
                    output = ''.join(lines[since:])
            except (OSError, PermissionError):
                pass

    return jsonify({'output': output, 'total': total, 'running': running})


@app.route('/api/system/docker', methods=['GET'])
@login_required
@require_permission('system:docker')
def api_docker_check():
    return jsonify({'available': check_docker()})


@app.route('/api/system/metrics', methods=['GET'])
@login_required
def api_system_metrics():
    import psutil
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.2)
    disk = psutil.disk_usage('/')
    return jsonify({
        'ram': {
            'total': mem.total,
            'used': mem.used,
            'percent': mem.percent
        },
        'cpu': {
            'percent': cpu
        },
        'disk': {
            'total': disk.total,
            'used': disk.used,
            'percent': disk.percent
        }
    })


@app.route('/api/settings', methods=['GET'])
@login_required
@require_permission('settings:read')
def api_settings_get():
    from models import get_setting
    return jsonify({
        'port': get_setting('port', '25565'),
        'docker_enabled': get_setting('docker_enabled', 'false'),
        'auto_backup_enabled': get_setting('auto_backup_enabled', 'false'),
        'auto_backup_interval': get_setting('auto_backup_interval', '60'),
        'auto_backup_retention': get_setting('auto_backup_retention', '10')
    })


@app.route('/api/settings', methods=['POST'])
@login_required
@require_permission('settings:write')
def api_settings_set():
    from models import set_setting
    data = request.json
    for key, value in data.items():
        set_setting(key, str(value))
    return jsonify({'status': 'saved'})


@app.route('/api/servers/<int:server_id>/java_args', methods=['PUT'])
@login_required
@require_permission('servers:java_args')
def api_server_java_args(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    data = request.json
    java_args = data.get('java_args', '-Xmx1G -Xms1G')
    update_server(server_id, java_args=java_args)
    return jsonify({'status': 'updated', 'java_args': java_args})


@app.route('/api/download/types', methods=['GET'])
@login_required
@require_permission('download:types')
def api_download_types():
    return jsonify(get_types())


@app.route('/api/download/versions/<server_type>', methods=['GET'])
@login_required
@require_permission('download:versions')
def api_download_versions(server_type):
    try:
        versions = get_versions(server_type)
        return jsonify(versions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/builds/<server_type>/<version>', methods=['GET'])
@login_required
@require_permission('download:builds')
def api_download_builds(server_type, version):
    try:
        builds = get_builds(server_type, version)
        return jsonify(builds)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download', methods=['POST'])
@login_required
@require_permission('download:create')
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


@app.route('/api/servers/<int:server_id>/upgrade', methods=['POST'])
@login_required
@require_permission('servers:upgrade')
def api_server_upgrade(server_id):
    server = get_server(server_id)
    if not server:
        abort(404)
    proc = get_server_process(server_id)
    if proc and proc.is_running:
        return jsonify({'error': 'Stop the server before upgrading'}), 400
    server_type = server['server_type']
    from server_downloader import download_server
    versions = get_versions(server_type)
    if not versions:
        return jsonify({'error': f'No versions found for {server_type}'}), 400
    latest_ver = versions[-1] if isinstance(versions, list) else versions[0]
    build = None
    if server_type in ('paper', 'folia', 'purpur'):
        builds = get_builds(server_type, latest_ver)
        if builds:
            build = builds[-1]
    name = server['name']
    import shutil
    backup_path = os.path.join(server['path'], 'server.jar.backup')
    old_jar = os.path.join(server['path'], server['jar_file'])
    if os.path.isfile(old_jar):
        shutil.copy2(old_jar, backup_path)
    new_id, error = download_server(server_type, latest_ver, build, name)
    if error:
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, old_jar)
            os.remove(backup_path)
        return jsonify({'error': error}), 400
    if os.path.isfile(backup_path):
        os.remove(backup_path)
    return jsonify({'id': new_id, 'version': latest_ver, 'build': build, 'status': 'upgraded'})


@app.route('/api/plugins/search', methods=['GET'])
@login_required
@require_permission('plugins:search')
def api_plugins_search():
    q = request.args.get('q', '')
    provider = request.args.get('provider')
    server_type = request.args.get('server_type')
    if len(q) < 2:
        return jsonify([])
    try:
        results = search_plugins(q, provider, server_type=server_type)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plugins/versions/<provider>/<project_id>', methods=['GET'])
@login_required
@require_permission('plugins:search')
def api_plugin_versions(provider, project_id):
    try:
        versions = plugin_get_versions(provider, project_id)
        return jsonify(versions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plugins/install', methods=['POST'])
@login_required
@require_permission('plugins:install')
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
@login_required
@require_permission('plugins:list')
def api_plugins_list(server_id):
    return jsonify(list_installed(server_id))


@app.route('/api/servers/<int:server_id>/plugins/<filename>', methods=['DELETE'])
@login_required
@require_permission('plugins:delete')
def api_plugin_delete(server_id, filename):
    ok, msg = delete_plugin(server_id, filename)
    if ok:
        return jsonify({'status': msg})
    return jsonify({'error': msg}), 400


# --- Panel Auto-Update ---

@app.route('/api/update/check', methods=['GET'])
@login_required
@require_permission('system:update')
def api_update_check():
    result = check_updates()
    return jsonify(result)


@app.route('/api/update/install', methods=['POST'])
@login_required
@require_permission('system:update')
def api_update_install():
    result = install_updates()
    if not result['success']:
        return jsonify({'error': result['error']}), 400
    schedule_restart()
    return jsonify({'status': 'restarting'})


if __name__ == '__main__':
    print(f'Windfall ECU starting on {HOST}:{PORT}')
    socketio.run(app, host=HOST, port=PORT, allow_unsafe_werkzeug=True)
