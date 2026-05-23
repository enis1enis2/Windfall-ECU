import os, threading, time
from config import SERVERS_DIR
from models import get_servers, create_server
from path_util import safe_join

_scanner_stop = threading.Event()
_scanner_thread = None
_discovered_log = []

def _detect_server_type(jar_name):
    jl = jar_name.lower()
    for kw, t in [('paper', 'paper'), ('folia', 'folia'), ('purpur', 'purpur'),
                   ('fabric', 'fabric'), ('quilt', 'quilt'), ('forge', 'forge'),
                   ('neoforge', 'neoforge')]:
        if kw in jl: return t
    return 'vanilla'

def _find_jar(server_dir):
    for f in os.listdir(server_dir):
        if f.endswith('.jar'):
            jl = f.lower()
            if any(kw in jl for kw in ['server', 'paper', 'purpur', 'spigot',
                                         'vanilla', 'fabric', 'quilt', 'forge',
                                         'neoforge', 'minecraft_server']):
                return f
    for f in os.listdir(server_dir):
        if f.endswith('.jar'):
            return f
    return None

def _scan():
    while not _scanner_stop.is_set():
        try:
            registered = {s['path'] for s in get_servers()}
            if os.path.isdir(SERVERS_DIR):
                for entry in os.listdir(SERVERS_DIR):
                    path = os.path.join(SERVERS_DIR, entry)
                    if not os.path.isdir(path): continue
                    if entry.startswith('_dl_'): continue
                    if path in registered: continue
                    jar = _find_jar(path)
                    if not jar: continue
                    st = _detect_server_type(jar)
                    try:
                        sid = create_server(name=entry, path=path, jar_file=jar, server_type=st)
                        _discovered_log.append(f'Auto-registered "{entry}" ({st}) as server #{sid}')
                    except Exception:
                        pass
        except Exception:
            pass
        _scanner_stop.wait(5)

def start_scanner():
    global _scanner_thread
    if _scanner_thread: return
    _scanner_thread = threading.Thread(target=_scan, daemon=True)
    _scanner_thread.start()

def stop_scanner():
    _scanner_stop.set()

def get_discovered_log():
    return list(_discovered_log)
