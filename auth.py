import functools
from flask import session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import _fetchone, _fetchall, _execute, get_db

ROLES = {
    'admin': {
        'name': 'Admin',
        'permissions': {
            'servers:list', 'servers:create', 'servers:get', 'servers:delete',
            'servers:start', 'servers:stop', 'servers:restart', 'servers:upgrade',
            'servers:status', 'servers:java_args', 'servers:console',
            'files:list', 'files:read', 'files:write', 'files:delete',
            'files:mkdir', 'files:upload', 'files:download',
            'backups:list', 'backups:create', 'backups:restore', 'backups:delete',
            'plugins:search', 'plugins:list', 'plugins:install', 'plugins:delete',
            'download:types', 'download:versions', 'download:builds', 'download:create',
            'import:zip',
            'settings:read', 'settings:write',
            'system:docker', 'system:update',
            'users:manage',
        }
    },
    'operator': {
        'name': 'Operator',
        'permissions': {
            'servers:list', 'servers:create', 'servers:get',
            'servers:start', 'servers:stop', 'servers:restart', 'servers:upgrade',
            'servers:status', 'servers:java_args', 'servers:console',
            'files:list', 'files:read', 'files:write', 'files:delete',
            'files:mkdir', 'files:upload', 'files:download',
            'backups:list', 'backups:create', 'backups:restore', 'backups:delete',
            'plugins:search', 'plugins:list', 'plugins:install',
            'download:types', 'download:versions', 'download:builds', 'download:create',
            'import:zip',
            'settings:read',
            'system:docker',
        }
    },
    'viewer': {
        'name': 'Viewer',
        'permissions': {
            'servers:list', 'servers:get', 'servers:status', 'servers:console',
            'files:list', 'files:read',
            'backups:list',
            'plugins:search', 'plugins:list',
            'download:types', 'download:versions', 'download:builds',
            'settings:read',
            'system:docker',
        }
    },
}

def init_auth():
    with get_db() as c:
        try:
            c.execute('ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT \'admin\'')
        except Exception:
            pass
    if not _fetchone('SELECT COUNT(*) as c FROM users')['c']:
        pw_hash = generate_password_hash('admin')
        _execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                 ('admin', pw_hash, 'admin'))

def register_user(username, password):
    if len(username) < 3 or len(password) < 4:
        return False, 'Username must be at least 3 characters, password at least 4'
    pw_hash = generate_password_hash(password)
    try:
        _execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                 (username, pw_hash, 'admin'))
        return True, 'User created'
    except Exception:
        return False, 'Username already exists'

def verify_user(username, password):
    r = _fetchone('SELECT id, password_hash, role FROM users WHERE username = ?', (username,))
    if r and check_password_hash(r['password_hash'], password):
        return r['id'], r['role']
    return None, None

def get_users():
    return _fetchall('SELECT id, username, role, created_at FROM users ORDER BY id')

def get_user_by_id(user_id):
    return _fetchone('SELECT id, username, role, created_at FROM users WHERE id = ?', (user_id,))

def change_password(user_id, new_password):
    if len(new_password) < 4:
        return False, 'Password must be at least 4 characters'
    _execute('UPDATE users SET password_hash = ? WHERE id = ?',
             (generate_password_hash(new_password), user_id))
    return True, 'Password changed'

def change_username(user_id, new_username):
    if len(new_username) < 3:
        return False, 'Username must be at least 3 characters'
    try:
        _execute('UPDATE users SET username = ? WHERE id = ?', (new_username, user_id))
        return True, 'Username changed'
    except Exception:
        return False, 'Username already exists'

def change_role(user_id, new_role):
    if new_role not in ROLES:
        return False, 'Invalid role'
    _execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    return True, 'Role changed'

def delete_user(user_id):
    r = _fetchone('SELECT COUNT(*) as c FROM users')
    if r['c'] <= 1:
        return False, 'Cannot delete the last user'
    _execute('DELETE FROM users WHERE id = ?', (user_id,))
    return True, 'User deleted'

def create_user(username, password, role='viewer'):
    if len(username) < 3:
        return False, 'Username must be at least 3 characters'
    if len(password) < 4:
        return False, 'Password must be at least 4 characters'
    if role not in ROLES:
        return False, 'Invalid role'
    try:
        _execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                 (username, generate_password_hash(password), role))
        return True, 'User created'
    except Exception:
        return False, 'Username already exists'

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated

def require_permission(permission):
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            role = session.get('role', 'viewer')
            if permission not in ROLES.get(role, ROLES['viewer'])['permissions']:
                return jsonify({'error': 'Forbidden'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
