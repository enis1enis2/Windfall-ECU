import contextlib, sqlite3
from functools import lru_cache
from config import DATABASE

ALLOWED_COLUMNS = {'name', 'path', 'jar_file', 'java_args', 'server_type', 'game_version', 'auto_start', 'docker_mode'}

@contextlib.contextmanager
def get_db(row=False):
    conn = sqlite3.connect(DATABASE, timeout=10, check_same_thread=False)
    if row:
        conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

def _fetchone(sql, params=()):
    with get_db(True) as c:
        r = c.execute(sql, params).fetchone()
        return dict(r) if r else None

def _fetchall(sql, params=()):
    with get_db(True) as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]

def _execute(sql, params=()):
    with get_db() as c:
        return c.execute(sql, params).lastrowid

def init_db():
    with get_db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS servers
            (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
             path TEXT NOT NULL, jar_file TEXT,
             java_args TEXT DEFAULT '-Xmx1G -Xms1G',
             server_type TEXT DEFAULT 'vanilla',
             game_version TEXT DEFAULT '',
             auto_start INTEGER DEFAULT 0, docker_mode INTEGER DEFAULT 0,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        try:
            c.execute("ALTER TABLE servers ADD COLUMN game_version TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        c.execute('''CREATE TABLE IF NOT EXISTS backups
            (id INTEGER PRIMARY KEY AUTOINCREMENT, server_id INTEGER NOT NULL,
             name TEXT NOT NULL, path TEXT NOT NULL, size INTEGER DEFAULT 0,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
             FOREIGN KEY(server_id) REFERENCES servers(id) ON DELETE CASCADE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings
            (key TEXT PRIMARY KEY, value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users
            (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
             password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'admin',
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

def get_servers():
    return _fetchall('SELECT * FROM servers ORDER BY created_at DESC')

def get_server(server_id):
    return _fetchone('SELECT * FROM servers WHERE id = ?', (server_id,))

def create_server(name, path, jar_file=None, java_args='-Xmx1G -Xms1G', server_type='vanilla', docker_mode=0):
    return _execute('INSERT INTO servers (name,path,jar_file,java_args,server_type,docker_mode) VALUES (?,?,?,?,?,?)',
                    (name, path, jar_file, java_args, server_type, docker_mode))

def delete_server(server_id):
    _execute('DELETE FROM servers WHERE id = ?', (server_id,))

def update_server(server_id, **kwargs):
    if not kwargs:
        return
    with get_db() as c:
        for key, value in kwargs.items():
            if key in ALLOWED_COLUMNS:
                c.execute(f'UPDATE servers SET {key} = ? WHERE id = ?', (value, server_id))

def get_backups(server_id):
    return _fetchall('SELECT * FROM backups WHERE server_id = ? ORDER BY created_at DESC', (server_id,))

def get_backup(backup_id):
    return _fetchone('SELECT * FROM backups WHERE id = ?', (backup_id,))

def create_backup_entry(server_id, name, path, size=0):
    return _execute('INSERT INTO backups (server_id,name,path,size) VALUES (?,?,?,?)', (server_id, name, path, size))

def delete_backup_entry(backup_id):
    _execute('DELETE FROM backups WHERE id = ?', (backup_id,))

def get_setting(key, default=None):
    r = _fetchone('SELECT value FROM settings WHERE key = ?', (key,))
    return r['value'] if r else default

def set_setting(key, value):
    with get_db() as c:
        c.execute('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?',
                  (key, value, value))
