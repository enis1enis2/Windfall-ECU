import os


def safe_join(base: str, *parts: str) -> str:
    path = os.path.normpath(os.path.join(base, *parts))
    if not path.startswith(os.path.normpath(base)):
        raise ValueError('Path traversal detected')
    return path


def sanitize_name(name: str) -> str:
    return ''.join(c if c.isalnum() or c in ' _-.' else '_' for c in name)


def safe_path(base: str, name: str) -> str:
    safe = sanitize_name(name)
    return safe_join(base, safe)


def safe_write(path: str, content: str) -> None:
    import tempfile, os
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent, prefix='.tmp_')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path): os.remove(tmp_path)
        raise

def is_within_directory(directory: str, target: str) -> bool:
    abs_directory = os.path.abspath(directory)
    abs_target = os.path.abspath(target)
    prefix = os.path.commonprefix([abs_directory, abs_target])
    return prefix == abs_directory
