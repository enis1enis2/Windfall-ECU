import os, zipfile, tempfile, shutil, time, json, re
from config import SERVERS_DIR
from models import create_server, get_server
from path_util import safe_path, safe_join, safe_write, sanitize_name

CHUNK_DIR = safe_join(SERVERS_DIR, '_chunks') if os.path.isdir(SERVERS_DIR) else None
CHUNK_SIZE = 4 * 1024 * 1024
CHUNK_TTL = 600
_progress_store = {}
_socketio_proxy = None

def _sio():
    global _socketio_proxy
    if _socketio_proxy is None:
        try:
            from app import socketio
            _socketio_proxy = socketio
        except Exception:
            _socketio_proxy = object()
    return _socketio_proxy if _socketio_proxy is not object() else None

def _ensure_chunk_dir():
    global CHUNK_DIR
    if CHUNK_DIR is None:
        CHUNK_DIR = safe_join(SERVERS_DIR, '_chunks')
    return CHUNK_DIR

def emit_progress(uid, percent, stage='uploading'):
    _progress_store[uid] = {'percent': percent, 'stage': stage}
    sio = _sio()
    if sio:
        sio.emit('import_progress', {'percent': percent, 'stage': stage})

def get_progress(uid):
    return _progress_store.get(uid, {'percent': 0, 'stage': ''})

def _make_result(sid=None, error=None):
    return {'success': error is None, 'id': sid, 'error': error}

def _detect(jars):
    if not jars: return None, None
    jc = [j for j in jars if any(kw in j.lower() for kw in
         ['server', 'paper', 'purpur', 'spigot', 'vanilla', 'fabric', 'quilt', 'forge', 'neoforge', 'minecraft_server'])]
    jf = (jc or jars)[0]
    dt = 'vanilla'
    for kw, t in [('paper', 'paper'), ('folia', 'folia'), ('purpur', 'purpur'),
                   ('fabric', 'fabric'), ('quilt', 'quilt'), ('forge', 'forge'),
                   ('neoforge', 'neoforge')]:
        if kw in jf.lower(): dt = t; break
    return jf, dt

def _extract_jars(ed):
    jars = []
    for root, dirs, files in os.walk(ed):
        for f in files:
            if f.endswith('.jar'):
                r = os.path.relpath(root, ed)
                jars.append(os.path.join(r, f) if r != '.' else f)
    return jars

def _finalize(sp, jf, dt, sn):
    if os.path.exists(sp): return None, f'Server "{os.path.basename(sp)}" already exists'
    el = safe_join(sp, 'eula.txt')
    if not os.path.isfile(el): safe_write(el, 'eula=true\n')
    return create_server(name=sn, path=sp, jar_file=jf, server_type=dt), None

# --- Standard import ---
def import_zip(file_storage, server_name=None, server_type=None):
    tmp = tempfile.mkdtemp()
    ed = os.path.join(tmp, 'extracted')
    os.makedirs(ed, exist_ok=True)
    file_storage.save(os.path.join(tmp, 'import.zip'))
    try:
        with zipfile.ZipFile(os.path.join(tmp, 'import.zip')) as zf: zf.extractall(ed)
        jars = _extract_jars(ed)
        if not jars: shutil.rmtree(tmp); return _make_result(error='No .jar file found')
        jf, dt = _detect(jars)
        if server_type: dt = server_type
        sn = server_name or (os.path.basename(jf).replace('.jar', '') or 'Imported Server')
        sp = safe_path(SERVERS_DIR, sn)
        e = None
        if os.path.exists(sp): e = f'Server "{os.path.basename(sp)}" already exists'
        if e: shutil.rmtree(tmp); return _make_result(error=e)
        shutil.copytree(ed, sp)
        sid, _ = _finalize(sp, jf, dt, sn)
        shutil.rmtree(tmp)
        return _make_result(sid)
    except zipfile.BadZipFile: shutil.rmtree(tmp); return _make_result(error='Invalid zip file')
    except Exception: shutil.rmtree(tmp); return _make_result(error='Import failed')

# --- Chunked upload ---
def chunked_init(filename, total_size, server_name=None, server_type=None):
    cd = _ensure_chunk_dir()
    os.makedirs(cd, exist_ok=True)
    _clean_stale()
    cid = f'{int(time.time())}_{abs(hash(filename)) % 10000}'
    meta = {'cid': cid, 'filename': filename, 'total_size': total_size,
            'server_name': server_name, 'server_type': server_type, 'chunks': [], 'started': time.time()}
    with open(safe_join(_ensure_chunk_dir(), sanitize_name(cid) + '.meta'), 'w') as f:
        json.dump(meta, f)
    _progress_store[cid] = {'percent': 0, 'stage': 'init'}
    return cid

def chunked_upload(cid, chunk_index, chunk_data):
    cs = sanitize_name(cid)
    cd = safe_join(_ensure_chunk_dir(), cs)
    os.makedirs(cd, exist_ok=True)
    ci = str(int(chunk_index)) if isinstance(chunk_index, (int, float)) else str(chunk_index)
    with open(safe_join(cd, ci), 'wb') as f:
        f.write(chunk_data)
    mf = safe_join(_ensure_chunk_dir(), f'{cs}.meta')
    if os.path.isfile(mf):
        with open(mf) as f: meta = json.load(f)
        if chunk_index not in meta['chunks']:
            meta['chunks'].append(chunk_index); meta['chunks'].sort()
            meta['total'] = len(meta['chunks'])
            sent = sum(os.path.getsize(safe_join(cd, str(i))) for i in meta['chunks'] if os.path.isfile(safe_join(cd, str(i))))
            pct = min(99, int(sent / meta['total_size'] * 100)) if meta['total_size'] else 0
            emit_progress(cid, pct, 'uploading')
        with open(mf, 'w') as f: json.dump(meta, f)
    return True

def chunked_finalize(cid):
    cs = sanitize_name(cid)
    cd = safe_join(_ensure_chunk_dir(), cs)
    mf = safe_join(_ensure_chunk_dir(), f'{cs}.meta')
    if not os.path.isfile(mf): return _make_result(error='Upload session not found')
    with open(mf) as f: meta = json.load(f)
    tmp = tempfile.mkdtemp()
    fpath = safe_join(tmp, sanitize_name(meta['filename']))
    try:
        with open(fpath, 'wb') as out:
            for ci in sorted(meta['chunks']):
                cp = safe_join(cd, str(int(ci)))
                if os.path.isfile(cp):
                    with open(cp, 'rb') as cf: out.write(cf.read())
                    os.remove(cp)
        emit_progress(cid, 100, 'extracting')
        ed = safe_join(tmp, 'extracted')
        os.makedirs(ed, exist_ok=True)
        with zipfile.ZipFile(fpath) as zf: zf.extractall(ed)
        jars = _extract_jars(ed)
        if not jars: raise ValueError('No .jar file found')
        jf, dt = _detect(jars)
        if meta.get('server_type'): dt = meta['server_type']
        sn = meta['server_name'] or (os.path.basename(jf).replace('.jar', '') or 'Imported Server')
        sp = safe_path(SERVERS_DIR, sn)
        if os.path.exists(sp): raise ValueError(f'Server "{os.path.basename(sp)}" already exists')
        shutil.copytree(ed, sp)
        sid, _ = _finalize(sp, jf, dt, sn)
        emit_progress(cid, 100, 'done')
        shutil.rmtree(tmp); shutil.rmtree(cd, ignore_errors=True); os.remove(mf)
        return _make_result(sid)
    except ValueError as e:
        shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(cd, ignore_errors=True); os.remove(mf)
        return _make_result(error=e.args[0] if e.args else 'Import failed')
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(cd, ignore_errors=True)
        return _make_result(error='Import failed')

def _clean_stale():
    cd = _ensure_chunk_dir()
    if not os.path.isdir(cd): return
    now = time.time()
    for f in os.listdir(cd):
        fn = sanitize_name(f)
        fp = safe_join(cd, fn)
        if f.endswith('.meta') and now - os.path.getmtime(fp) > CHUNK_TTL:
            cid = f.replace('.meta', '')
            shutil.rmtree(safe_join(cd, sanitize_name(cid)), ignore_errors=True)
            os.remove(fp)
