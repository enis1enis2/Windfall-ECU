import sqlite3
import functools
from flask import session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from config import DATABASE

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
            'system:docker',
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
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         username TEXT UNIQUE NOT NULL,
         password_hash TEXT NOT NULL,
         role TEXT NOT NULL DEFAULT 'admin',
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    try:
        c.execute('ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT \'admin\'')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    conn.close()
    if count == 0:
        _create_user('admin', 'admin', 'admin')

def _create_user(username, password, role='admin'):
    pw_hash = generate_password_hash(password)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                  (username, pw_hash, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def register_user(username, password):
    if len(username) < 3 or len(password) < 4:
        return False, 'Username must be at least 3 characters, password at least 4'
    pw_hash = generate_password_hash(password)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                  (username, pw_hash, 'admin'))
        conn.commit()
        return True, 'User created'
    except sqlite3.IntegrityError:
        return False, 'Username already exists'
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, password_hash, role FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row[1], password):
        return row[0], row[2]
    return None, None

def get_users():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT id, username, role, created_at FROM users ORDER BY id')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_by_id(user_id):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT id, username, role, created_at FROM users WHERE id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def change_password(user_id, new_password):
    if len(new_password) < 4:
        return False, 'Password must be at least 4 characters'
    pw_hash = generate_password_hash(new_password)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('UPDATE users SET password_hash = ? WHERE id = ?', (pw_hash, user_id))
    conn.commit()
    conn.close()
    return True, 'Password changed'

def change_username(user_id, new_username):
    if len(new_username) < 3:
        return False, 'Username must be at least 3 characters'
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('UPDATE users SET username = ? WHERE id = ?', (new_username, user_id))
        conn.commit()
        return True, 'Username changed'
    except sqlite3.IntegrityError:
        return False, 'Username already exists'
    finally:
        conn.close()

def change_role(user_id, new_role):
    if new_role not in ROLES:
        return False, 'Invalid role'
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    conn.commit()
    conn.close()
    return True, 'Role changed'

def delete_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    if count <= 1:
        conn.close()
        return False, 'Cannot delete the last user'
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True, 'User deleted'

def create_user(username, password, role='viewer'):
    if len(username) < 3:
        return False, 'Username must be at least 3 characters'
    if len(password) < 4:
        return False, 'Password must be at least 4 characters'
    if role not in ROLES:
        return False, 'Invalid role'
    pw_hash = generate_password_hash(password)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                  (username, pw_hash, role))
        conn.commit()
        return True, 'User created'
    except sqlite3.IntegrityError:
        return False, 'Username already exists'
    finally:
        conn.close()

def has_permission(permission, role=None):
    if role is None:
        role = session.get('role', 'viewer')
    return permission in ROLES.get(role, ROLES['viewer'])['permissions']

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

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated

def get_role_permissions(role):
    return ROLES.get(role, ROLES['viewer']).get('permissions', set())
