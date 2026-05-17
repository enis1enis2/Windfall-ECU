import sqlite3
import functools
from flask import session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from config import DATABASE

def init_auth():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         username TEXT UNIQUE NOT NULL,
         password_hash TEXT NOT NULL,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    conn.close()
    if count == 0:
        _create_user('admin', 'admin')

def _create_user(username, password):
    pw_hash = generate_password_hash(password)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, pw_hash))
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
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, pw_hash))
        conn.commit()
        return True, 'User created'
    except sqlite3.IntegrityError:
        return False, 'Username already exists'
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row[1], password):
        return row[0]
    return None

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated
