import sqlite3
from config import DATABASE

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS servers
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT NOT NULL,
         path TEXT NOT NULL,
         jar_file TEXT,
         java_args TEXT DEFAULT '-Xmx1G -Xms1G',
         server_type TEXT DEFAULT 'vanilla',
         auto_start INTEGER DEFAULT 0,
         docker_mode INTEGER DEFAULT 0,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS backups
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         server_id INTEGER NOT NULL,
         name TEXT NOT NULL,
         path TEXT NOT NULL,
         size INTEGER DEFAULT 0,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY(server_id) REFERENCES servers(id) ON DELETE CASCADE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings
        (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit()
    conn.close()

def get_servers():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM servers ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_server(server_id):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM servers WHERE id = ?', (server_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def create_server(name, path, jar_file=None, java_args='-Xmx1G -Xms1G', server_type='vanilla', docker_mode=0):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO servers (name, path, jar_file, java_args, server_type, docker_mode) VALUES (?, ?, ?, ?, ?, ?)',
              (name, path, jar_file, java_args, server_type, docker_mode))
    conn.commit()
    server_id = c.lastrowid
    conn.close()
    return server_id

def delete_server(server_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM servers WHERE id = ?', (server_id,))
    conn.commit()
    conn.close()

def update_server(server_id, **kwargs):
    if not kwargs:
        return
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    for key, value in kwargs.items():
        c.execute(f'UPDATE servers SET {key} = ? WHERE id = ?', (value, server_id))
    conn.commit()
    conn.close()

def get_backups(server_id):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM backups WHERE server_id = ? ORDER BY created_at DESC', (server_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_backup(backup_id):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM backups WHERE id = ?', (backup_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def create_backup_entry(server_id, name, path, size=0):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO backups (server_id, name, path, size) VALUES (?, ?, ?, ?)',
              (server_id, name, path, size))
    conn.commit()
    backup_id = c.lastrowid
    conn.close()
    return backup_id

def delete_backup_entry(backup_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM backups WHERE id = ?', (backup_id,))
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()
