import os
import mimetypes
from path_util import safe_join

def _sf(base, *parts):
    try:
        return os.path.normpath(safe_join(base, *parts))
    except ValueError:
        return None

def list_files(base_path, rel_path=''):
    full = _sf(base_path, rel_path) if rel_path else base_path
    if not full or not full.startswith(os.path.normpath(base_path)):
        return None, 'Access denied'
    os.makedirs(full, exist_ok=True)
    try:
        entries = []
        for name in sorted(os.listdir(full)):
            p = os.path.join(full, name)
            d = os.path.isdir(p)
            s = os.stat(p)
            entries.append({
                'name': name, 'path': os.path.join(rel_path, name) if rel_path else name,
                'is_dir': d, 'size': 0 if d else s.st_size,
                'modified': int(s.st_mtime), 'mime': None if d else mimetypes.guess_type(name)[0],
            })
    except PermissionError:
        return None, 'Permission denied'
    return {'path': rel_path, 'current': os.path.basename(full) if rel_path else '',
            'parent': os.path.dirname(rel_path) if rel_path else None, 'entries': entries}, None

def read_file(base_path, rel_path):
    f = _sf(base_path, rel_path)
    if not f: return None, 'Access denied'
    if not os.path.isfile(f): return None, 'Not a file'
    try:
        with open(f, 'r', errors='replace') as fp: return fp.read(), None
    except Exception: return None, 'Failed to read file'

def write_file(base_path, rel_path, content):
    f = _sf(base_path, rel_path)
    if not f: return False, 'Access denied'
    try:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, 'w') as fp: fp.write(content)
        return True, 'File saved'
    except Exception: return False, 'Failed to write file'

def delete_entry(base_path, rel_path):
    f = _sf(base_path, rel_path)
    if not f: return False, 'Access denied'
    if not os.path.exists(f): return False, 'Not found'
    try:
        (__import__('shutil').rmtree if os.path.isdir(f) else os.remove)(f)
        return True, 'Deleted'
    except Exception: return False, 'Failed to delete'

def create_directory(base_path, rel_path, name):
    f = _sf(base_path, rel_path, name)
    if not f: return False, 'Access denied'
    try:
        os.makedirs(f, exist_ok=True)
        return True, 'Directory created'
    except Exception: return False, 'Failed to create directory'

def upload_file(base_path, rel_path, filename, content):
    f = _sf(base_path, rel_path, filename)
    if not f: return False, 'Access denied'
    mode = 'wb' if isinstance(content, bytes) else 'w'
    try:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, mode) as fp: fp.write(content)
        return True, 'File uploaded'
    except Exception: return False, 'Failed to upload file'
