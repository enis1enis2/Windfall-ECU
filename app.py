import eventlet; eventlet.monkey_patch()
import os, json, shutil, subprocess as _sp, psutil, gzip, time
from flask import Flask, render_template, request, jsonify, send_file, abort, session
from flask_socketio import SocketIO
from config import HOST, PORT, SECRET_KEY, SERVERS_DIR, BACKUPS_DIR
from path_util import safe_join, safe_path
from models import init_db, get_servers, get_server, create_server, delete_server, update_server, get_setting, set_setting
from server_manager import ServerProcess, get_server_process, register_server, unregister_server, clean_output
from terminal_handler import setup_terminal_handlers
from backup_manager import list_backups, create_backup, restore_backup, delete_backup
from file_explorer import list_files, read_file, write_file, delete_entry, create_directory, upload_file
from zip_importer import import_zip, chunked_init, chunked_upload, chunked_finalize, get_progress
from docker_manager import check_docker
from server_downloader import get_types, get_versions, get_builds, download_server
from plugin_downloader import search_plugins, get_versions as plugin_get_versions, install_plugin, list_installed, delete_plugin
from auth import login_required, require_permission, register_user, verify_user, init_auth, get_users, get_user_by_id, change_password, change_username, change_role, delete_user, create_user, ROLES
from auto_backup import start_auto_backup_scheduler
from update_manager import check_updates, install_updates, schedule_restart
from discovery import start_scanner, get_discovered_log

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 1024 ** 3
socketio = SocketIO(app, cors_allowed_origins=os.environ.get('GREATPANEL_ORIGIN', 'http://localhost:8080'), async_mode='eventlet')

os.makedirs(SERVERS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

# Kill leftover process on 8080
for cmd in [['fuser', '-k', f'{PORT}/tcp'], ['lsof', '-ti', f'tcp:{PORT}']]:
    try:
        r = _sp.run(cmd, capture_output=True, text=True, timeout=5)
        if cmd[0] == 'lsof' and r.stdout.strip():
            for p in r.stdout.strip().splitlines(): _sp.run(['kill', '-9', p], capture_output=True, timeout=3)
        break
    except: pass

init_db(); init_auth(); setup_terminal_handlers(socketio); start_auto_backup_scheduler(); start_scanner()

# --- Compression & caching ---
COMPRESS_TYPES = {'text/html', 'text/css', 'application/javascript', 'application/json',
                  'text/javascript', 'text/plain', 'application/xml'}
@app.after_request
def _compress(resp):
    if resp.status_code < 200 or resp.status_code >= 300: return resp
    if 'gzip' not in request.headers.get('Accept-Encoding', ''): return resp
    ct = resp.content_type or ''
    if not any(t in ct for t in COMPRESS_TYPES): return resp
    if resp.content_length and resp.content_length > 200 and resp.is_sequence:
        resp.direct_passthrough = False
        resp.set_data(gzip.compress(resp.get_data()))
        resp.headers['Content-Encoding'] = 'gzip'
        resp.headers['Content-Length'] = str(len(resp.get_data()))
    return resp

@app.context_processor
def _inject_ts():
    return {'static_ts': int(time.time())}

# --- Helpers ---
def get_srv(server_id):
    s = get_server(server_id)
    if not s: abort(404)
    return s

def res(ok, msg, code=None):
    if code: return jsonify(msg), code
    return (jsonify({'status': msg}), 200) if ok else (jsonify({'error': msg}), 400)

# --- Auth ---
@app.route('/')
def index():
    return render_template('login.html' if 'user_id' not in session else 'index.html')

@app.route('/api/auth/status')
def api_auth_status():
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'username': session['username'], 'user_id': session['user_id'], 'role': session.get('role', 'viewer')})
    return jsonify({'authenticated': False})

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    d = request.json; u, p = d.get('username', '').strip(), d.get('password', '')
    uid, role = verify_user(u, p)
    if uid: session.update({'user_id': uid, 'username': u, 'role': role}); return jsonify({'status': 'ok', 'username': u, 'role': role})
    return jsonify({'error': 'Invalid username or password'}), 401

@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    d = request.json; u, p = d.get('username', '').strip(), d.get('password', '')
    ok, msg, db_user = register_user(u, p)
    if ok:
        uid, role = verify_user(db_user, p)
        session.update({'user_id': uid, 'username': db_user, 'role': role})
        return jsonify({'status': 'ok', 'username': db_user, 'role': role}), 201
    return jsonify({'error': msg}), 400

@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    session.clear(); return jsonify({'status': 'logged out'})

# --- User management ---
@app.route('/api/users', methods=['GET'])
@login_required
@require_permission('users:manage')
def api_users_list(): return jsonify(get_users())

@app.route('/api/users', methods=['POST'])
@login_required
@require_permission('users:manage')
def api_users_create():
    d = request.json
    ok, msg = create_user(d.get('username', '').strip(), d.get('password', ''), d.get('role', 'viewer'))
    return res(ok, msg, 201 if ok else 400)

@app.route('/api/users/<int:user_id>', methods=['PATCH'])
@login_required
@require_permission('users:manage')
def api_user_update(user_id):
    if not get_user_by_id(user_id): abort(404)
    d = request.json
    if 'password' in d:
        ok, msg = change_password(user_id, d['password'])
        if not ok: return res(ok, msg)
    if 'username' in d:
        ok, msg = change_username(user_id, d['username'])
        if not ok: return res(ok, msg)
    if 'role' in d:
        ok, msg = change_role(user_id, d['role'])
        if not ok: return res(ok, msg)
    return jsonify({'status': 'updated'})

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@require_permission('users:manage')
def api_user_delete(user_id):
    if user_id == session.get('user_id'): return jsonify({'error': 'Cannot delete your own account'}), 400
    return res(*delete_user(user_id))

@app.route('/api/users/roles', methods=['GET'])
@login_required
@require_permission('users:manage')
def api_users_roles():
    return jsonify({k: {'name': v['name'], 'permissions': sorted(v['permissions'])} for k, v in ROLES.items()})

# --- Servers ---
@app.route('/api/servers', methods=['GET'])
@login_required
@require_permission('servers:list')
def api_servers_list():
    result = []
    for s in get_servers():
        p = get_server_process(s['id'])
        s['status'] = p.get_status() if p else {'running': False, 'pid': None}
        result.append(s)
    return jsonify(result)

@app.route('/api/servers', methods=['POST'])
@login_required
@require_permission('servers:create')
def api_servers_create():
    d = request.json
    sp = safe_path(SERVERS_DIR, d.get('name', 'New Server'))
    os.makedirs(sp, exist_ok=True)
    return jsonify({'id': create_server(name=d.get('name', 'New Server'), path=sp, jar_file=d.get('jar_file'),
                                       java_args=d.get('java_args', '-Xmx1G -Xms1G'), server_type=d.get('server_type', 'vanilla')), 'path': sp}), 201

@app.route('/api/servers/<int:server_id>', methods=['GET'])
@login_required
@require_permission('servers:get')
def api_server_get(server_id):
    s = get_srv(server_id)
    p = get_server_process(server_id)
    s['status'] = p.get_status() if p else {'running': False, 'pid': None}
    return jsonify(s)

@app.route('/api/servers/<int:server_id>', methods=['DELETE'])
@login_required
@require_permission('servers:delete')
def api_server_delete(server_id):
    s = get_srv(server_id)
    unregister_server(server_id)
    if os.path.isdir(s['path']): shutil.rmtree(s['path'], ignore_errors=True)
    delete_server(server_id)
    return jsonify({'status': 'deleted'})

@app.route('/api/servers/<int:server_id>/start', methods=['POST'])
@login_required
@require_permission('servers:start')
def api_server_start(server_id):
    s = get_srv(server_id)
    if get_server_process(server_id) and get_server_process(server_id).is_running: return jsonify({'status': 'already running'})
    jp = os.path.join(s['path'], s['jar_file']) if s['jar_file'] else None
    if not jp or not os.path.isfile(jp): return jsonify({'error': f'JAR file not found: {jp}'}), 400
    p = ServerProcess(server_id, s['path'], s['jar_file'], s['java_args'])
    if p.start():
        register_server(server_id, p)
        return jsonify({'status': 'started', 'pid': p.process.pid if p.process else None})
    return jsonify({'error': 'Failed to start server'}), 500

@app.route('/api/servers/<int:server_id>/stop', methods=['POST'])
@login_required
@require_permission('servers:stop')
def api_server_stop(server_id):
    p = get_server_process(server_id)
    if not p: return jsonify({'status': 'not running'})
    p.stop(); unregister_server(server_id)
    return jsonify({'status': 'stopped'})

@app.route('/api/servers/<int:server_id>/restart', methods=['POST'])
@login_required
@require_permission('servers:restart')
def api_server_restart(server_id):
    s = get_srv(server_id)
    p = get_server_process(server_id)
    if p: p.stop(); unregister_server(server_id); eventlet.sleep(1)
    jp = os.path.join(s['path'], s['jar_file']) if s['jar_file'] else None
    if not jp or not os.path.isfile(jp): return jsonify({'error': f'JAR file not found: {jp}'}), 400
    p = ServerProcess(server_id, s['path'], s['jar_file'], s['java_args'])
    if p.start():
        register_server(server_id, p)
        return jsonify({'status': 'restarted', 'pid': p.process.pid if p.process else None})
    return jsonify({'error': 'Failed to restart server'}), 500

@app.route('/api/servers/<int:server_id>/status', methods=['GET'])
@login_required
@require_permission('servers:status')
def api_server_status(server_id):
    p = get_server_process(server_id)
    return jsonify(p.get_status() if p else {'running': False, 'pid': None})

@app.route('/api/servers/<int:server_id>/java_args', methods=['PUT'])
@login_required
@require_permission('servers:java_args')
def api_server_java_args(server_id):
    s = get_srv(server_id)
    ja = request.json.get('java_args', '-Xmx1G -Xms1G')
    update_server(server_id, java_args=ja)
    return jsonify({'status': 'updated', 'java_args': ja})

# --- Files ---
@app.route('/api/servers/<int:server_id>/files', methods=['GET'])
@login_required
@require_permission('files:list')
def api_files_list(server_id):
    s = get_srv(server_id)
    result, error = list_files(s['path'], request.args.get('path', ''))
    if result: return jsonify(result)
    return jsonify({'error': error}), 400

@app.route('/api/servers/<int:server_id>/files/read', methods=['GET'])
@login_required
@require_permission('files:read')
def api_files_read(server_id):
    s = get_srv(server_id)
    content, error = read_file(s['path'], request.args.get('path', ''))
    if content: return jsonify({'content': content})
    return res(False, error)

@app.route('/api/servers/<int:server_id>/files/write', methods=['POST'])
@login_required
@require_permission('files:write')
def api_files_write(server_id):
    s = get_srv(server_id); d = request.json
    return res(*write_file(s['path'], d['path'], d['content']))

@app.route('/api/servers/<int:server_id>/files/delete', methods=['POST'])
@login_required
@require_permission('files:delete')
def api_files_delete(server_id):
    s = get_srv(server_id)
    return res(*delete_entry(s['path'], request.json['path']))

@app.route('/api/servers/<int:server_id>/files/mkdir', methods=['POST'])
@login_required
@require_permission('files:mkdir')
def api_files_mkdir(server_id):
    s = get_srv(server_id); d = request.json
    return res(*create_directory(s['path'], d.get('path', ''), d['name']))

@app.route('/api/servers/<int:server_id>/files/upload', methods=['POST'])
@login_required
@require_permission('files:upload')
def api_files_upload(server_id):
    s = get_srv(server_id)
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    return res(*upload_file(s['path'], request.form.get('path', ''), f.filename, f.read()))

@app.route('/api/servers/<int:server_id>/files/download', methods=['GET'])
@login_required
@require_permission('files:download')
def api_files_download(server_id):
    s = get_srv(server_id)
    try: fp = safe_join(s['path'], request.args.get('path', ''))
    except ValueError: abort(403)
    if not os.path.isfile(fp): abort(404)
    return send_file(fp, as_attachment=True)

# --- Backups ---
@app.route('/api/servers/<int:server_id>/backups', methods=['GET'])
@login_required
@require_permission('backups:list')
def api_backups_list(server_id):
    get_srv(server_id); return jsonify(list_backups(server_id))

@app.route('/api/servers/<int:server_id>/backups', methods=['POST'])
@login_required
@require_permission('backups:create')
def api_backups_create(server_id):
    get_srv(server_id)
    bid, error = create_backup(server_id, (request.json or {}).get('name'))
    if bid: return jsonify({'id': bid}), 201
    return jsonify({'error': error}), 500

@app.route('/api/backups/<int:backup_id>/restore', methods=['POST'])
@login_required
@require_permission('backups:restore')
def api_backups_restore(backup_id): return res(*restore_backup(backup_id))

@app.route('/api/backups/<int:backup_id>', methods=['DELETE'])
@login_required
@require_permission('backups:delete')
def api_backups_delete(backup_id): return res(*delete_backup(backup_id))

# --- Import ---
@app.route('/api/import/zip', methods=['POST'])
@login_required
@require_permission('import:zip')
def api_import_zip():
    if 'file' not in request.files: return jsonify({'error': 'No file uploaded'}), 400
    f = request.files['file']
    if not f.filename.endswith('.zip'): return jsonify({'error': 'File must be a .zip'}), 400
    r = import_zip(f, request.form.get('name'))
    if r['error']: return jsonify({'error': r['error']}), 400
    s = get_server(r['id'])
    return jsonify({'id': r['id'], 'name': s['name'] if s else request.form.get('name'), 'status': 'imported'}), 201

@app.route('/api/import/chunked/init', methods=['POST'])
@login_required
@require_permission('import:zip')
def api_chunked_init():
    d = request.json
    cid = chunked_init(d['filename'], d['total_size'], d.get('name'))
    return jsonify({'cid': cid, 'chunk_size': 4 * 1024 * 1024})

@app.route('/api/import/chunked/<cid>/<int:chunk_index>', methods=['POST'])
@login_required
@require_permission('import:zip')
def api_chunked_upload(cid, chunk_index):
    data = request.get_data()
    chunked_upload(cid, chunk_index, data)
    return jsonify({'status': 'ok'})

@app.route('/api/import/chunked/<cid>/finalize', methods=['POST'])
@login_required
@require_permission('import:zip')
def api_chunked_finalize(cid):
    r = chunked_finalize(cid)
    if r['error']: return jsonify({'error': r['error']}), 400
    s = get_server(r['id'])
    return jsonify({'id': r['id'], 'name': s['name'] if s else '', 'status': 'imported'}), 201

@app.route('/api/import/progress/<uid>', methods=['GET'])
@login_required
def api_import_progress(uid):
    return jsonify(get_progress(uid))

# --- Discovery ---
@app.route('/api/discovery/log', methods=['GET'])
@login_required
def api_discovery_log():
    return jsonify(get_discovered_log())

# --- Console ---
@app.route('/api/servers/<int:server_id>/console', methods=['GET'])
@login_required
@require_permission('servers:console')
def api_console(server_id):
    s = get_srv(server_id)
    p = get_server_process(server_id); running = bool(p and p.is_running)
    since = request.args.get('since', 0, type=int); output = ''; total = 0
    if p: output, total = p.buffer.get_since(since)
    else:
        lf = os.path.join(s['path'], 'logs', 'latest.log')
        if os.path.isfile(lf):
            try:
                fs = os.path.getsize(lf); mx = 5 * 1024 * 1024
                with open(lf, 'r', errors='replace') as f:
                    if fs > mx: f.seek(fs - mx); f.readline()
                    txt = clean_output(f.read()); lines = txt.splitlines(True)
                    total = len(lines); output = ''.join(lines[since:])
            except: pass
    return jsonify({'output': output, 'total': total, 'running': running})

# --- System ---
@app.route('/api/system/docker', methods=['GET'])
@login_required
@require_permission('system:docker')
def api_docker_check(): return jsonify({'available': check_docker()})

@app.route('/api/system/metrics', methods=['GET'])
@login_required
def api_system_metrics():
    m = psutil.virtual_memory(); c = psutil.cpu_percent(interval=0.2); d = psutil.disk_usage('/')
    return jsonify({'ram': {'total': m.total, 'used': m.used, 'percent': m.percent},
                    'cpu': {'percent': c}, 'disk': {'total': d.total, 'used': d.used, 'percent': d.percent}})

# --- Settings ---
@app.route('/api/settings', methods=['GET'])
@login_required
@require_permission('settings:read')
def api_settings_get():
    return jsonify({k: get_setting(k, v) for k, v in
                    {'port': '25565', 'docker_enabled': 'false', 'auto_backup_enabled': 'false',
                     'auto_backup_interval': '60', 'auto_backup_retention': '10'}.items()})

@app.route('/api/settings', methods=['POST'])
@login_required
@require_permission('settings:write')
def api_settings_set():
    for k, v in (request.json or {}).items(): set_setting(k, str(v))
    return jsonify({'status': 'saved'})

# --- Downloads ---
@app.route('/api/download/types', methods=['GET'])
@login_required
@require_permission('download:types')
def api_download_types(): return jsonify(get_types())

@app.route('/api/download/versions/<server_type>', methods=['GET'])
@login_required
@require_permission('download:versions')
def api_download_versions(server_type):
    try: return jsonify(get_versions(server_type))
    except: return jsonify({'error': 'Failed to get versions'}), 500

@app.route('/api/download/builds/<server_type>/<version>', methods=['GET'])
@login_required
@require_permission('download:builds')
def api_download_builds(server_type, version):
    try: return jsonify(get_builds(server_type, version))
    except: return jsonify({'error': 'Failed to get builds'}), 500

@app.route('/api/download', methods=['POST'])
@login_required
@require_permission('download:create')
def api_download():
    d = request.json
    if not d.get('type') or not d.get('version'): return jsonify({'error': 'type and version required'}), 400
    try:
        sid, error = download_server(d['type'], d['version'], d.get('build'), d.get('name'))
        if error: return jsonify({'error': error}), 400
        return jsonify({'id': sid, 'status': 'downloaded'}), 201
    except: return jsonify({'error': 'Download failed'}), 500

@app.route('/api/servers/<int:server_id>/upgrade', methods=['POST'])
@login_required
@require_permission('servers:upgrade')
def api_server_upgrade(server_id):
    s = get_srv(server_id)
    p = get_server_process(server_id)
    if p and p.is_running: return jsonify({'error': 'Stop the server before upgrading'}), 400
    st = s['server_type']
    vs = get_versions(st)
    if not vs: return jsonify({'error': f'No versions found for {st}'}), 400
    lv = vs[-1] if isinstance(vs, list) else vs[0]
    build = get_builds(st, lv)[-1] if st in ('paper', 'folia', 'purpur') and get_builds(st, lv) else None
    bp = os.path.join(s['path'], 'server.jar.backup'); oj = os.path.join(s['path'], s['jar_file'])
    if os.path.isfile(oj): shutil.copy2(oj, bp)
    nid, error = download_server(st, lv, build, s['name'])
    if error:
        if os.path.isfile(bp): shutil.copy2(bp, oj); os.remove(bp)
        return jsonify({'error': error}), 400
    if os.path.isfile(bp): os.remove(bp)
    return jsonify({'id': nid, 'version': lv, 'build': build, 'status': 'upgraded'})

# --- Plugins ---
@app.route('/api/plugins/search', methods=['GET'])
@login_required
@require_permission('plugins:search')
def api_plugins_search():
    q = request.args.get('q', '')
    if len(q) < 2: return jsonify([])
    try: return jsonify(search_plugins(q, request.args.get('provider'), server_type=request.args.get('server_type')))
    except: return jsonify({'error': 'Search failed'}), 500

@app.route('/api/plugins/versions/<provider>/<project_id>', methods=['GET'])
@login_required
@require_permission('plugins:search')
def api_plugin_versions(provider, project_id):
    try: return jsonify(plugin_get_versions(provider, project_id))
    except: return jsonify({'error': 'Failed to get versions'}), 500

@app.route('/api/plugins/install', methods=['POST'])
@login_required
@require_permission('plugins:install')
def api_plugin_install():
    d = request.json
    if not all([d.get('server_id'), d.get('provider'), d.get('project_id')]):
        return jsonify({'error': 'server_id, provider, project_id required'}), 400
    return res(*install_plugin(d['server_id'], d['provider'], d['project_id'], d.get('version_id'), d.get('version_number')))

@app.route('/api/servers/<int:server_id>/plugins', methods=['GET'])
@login_required
@require_permission('plugins:list')
def api_plugins_list(server_id): return jsonify(list_installed(server_id))

@app.route('/api/servers/<int:server_id>/plugins/<filename>', methods=['DELETE'])
@login_required
@require_permission('plugins:delete')
def api_plugin_delete(server_id, filename): return res(*delete_plugin(server_id, filename))

# --- Panel Auto-Update ---
@app.route('/api/update/check', methods=['GET'])
@login_required
@require_permission('system:update')
def api_update_check(): return jsonify(check_updates())

@app.route('/api/update/install', methods=['POST'])
@login_required
@require_permission('system:update')
def api_update_install():
    r = install_updates()
    if not r['success']: return jsonify({'error': r['error']}), 400
    schedule_restart(); return jsonify({'status': 'restarting'})

@app.route('/api/admin/info', methods=['GET'])
@login_required
@require_permission('system:admin')
def api_admin_info():
    import platform, datetime, sys
    users = get_users()
    total, used, free = shutil.disk_usage(SERVERS_DIR)
    servers = get_servers()
    db_size = os.path.getsize('instances.db') if os.path.isfile('instances.db') else 0
    return jsonify({
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'uptime': time.time() - psutil.boot_time(),
        'users_total': len(users),
        'users_by_role': {r: sum(1 for u in users if u.get('role') == r) for r in ('admin', 'operator', 'viewer')},
        'servers_total': len(servers),
        'servers_running': sum(1 for s in servers if s.get('status', {}).get('running')),
        'disk_total': total, 'disk_used': used, 'disk_free': free,
        'db_size': db_size,
        'server_dir_size': sum(f.stat().st_size for f in __import__('pathlib').Path(SERVERS_DIR).rglob('*') if f.is_file()) if os.path.isdir(SERVERS_DIR) else 0,
        'backups_dir_size': sum(f.stat().st_size for f in __import__('pathlib').Path(BACKUPS_DIR).rglob('*') if f.is_file()) if os.path.isdir(BACKUPS_DIR) else 0,
    })

if __name__ == '__main__':
    print(f'Windfall ECU starting on {HOST}:{PORT}')
    socketio.run(app, host=HOST, port=PORT, allow_unsafe_werkzeug=True)
