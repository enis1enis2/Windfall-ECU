import os
import mimetypes


def list_files(base_path, rel_path=''):
    full_path = os.path.join(base_path, rel_path) if rel_path else base_path
    full_path = os.path.normpath(full_path)

    if not full_path.startswith(os.path.normpath(base_path)):
        return None, 'Access denied'

    if not os.path.isdir(full_path):
        return None, 'Not a directory'

    entries = []
    try:
        for name in sorted(os.listdir(full_path)):
            entry_path = os.path.join(full_path, name)
            rel = os.path.join(rel_path, name) if rel_path else name
            is_dir = os.path.isdir(entry_path)
            stat = os.stat(entry_path)
            entries.append({
                'name': name,
                'path': rel,
                'is_dir': is_dir,
                'size': stat.st_size if not is_dir else 0,
                'modified': int(stat.st_mtime),
                'mime': mimetypes.guess_type(name)[0] if not is_dir else None
            })
    except PermissionError:
        return None, 'Permission denied'

    current = os.path.basename(full_path) if rel_path else ''
    parent = os.path.dirname(rel_path) if rel_path else None

    return {
        'path': rel_path,
        'current': current,
        'parent': parent,
        'entries': entries
    }, None


def read_file(base_path, rel_path):
    full_path = os.path.normpath(os.path.join(base_path, rel_path))
    if not full_path.startswith(os.path.normpath(base_path)):
        return None, 'Access denied'
    if not os.path.isfile(full_path):
        return None, 'Not a file'

    try:
        with open(full_path, 'r', errors='replace') as f:
            content = f.read()
        return content, None
    except Exception as e:
        return None, str(e)


def write_file(base_path, rel_path, content):
    full_path = os.path.normpath(os.path.join(base_path, rel_path))
    if not full_path.startswith(os.path.normpath(base_path)):
        return False, 'Access denied'

    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        return True, 'File saved'
    except Exception as e:
        return False, str(e)


def delete_entry(base_path, rel_path):
    full_path = os.path.normpath(os.path.join(base_path, rel_path))
    if not full_path.startswith(os.path.normpath(base_path)):
        return False, 'Access denied'
    if not os.path.exists(full_path):
        return False, 'Not found'

    try:
        if os.path.isdir(full_path):
            import shutil
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)
        return True, 'Deleted'
    except Exception as e:
        return False, str(e)


def create_directory(base_path, rel_path, name):
    full_path = os.path.normpath(os.path.join(base_path, rel_path, name))
    if not full_path.startswith(os.path.normpath(base_path)):
        return False, 'Access denied'

    try:
        os.makedirs(full_path, exist_ok=True)
        return True, 'Directory created'
    except Exception as e:
        return False, str(e)


def upload_file(base_path, rel_path, filename, content):
    if isinstance(content, bytes):
        mode = 'wb'
    else:
        mode = 'w'

    full_path = os.path.normpath(os.path.join(base_path, rel_path, filename))
    if not full_path.startswith(os.path.normpath(base_path)):
        return False, 'Access denied'

    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, mode) as f:
            f.write(content)
        return True, 'File uploaded'
    except Exception as e:
        return False, str(e)
