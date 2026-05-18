import os


def safe_join(base, *parts):
    path = os.path.normpath(os.path.join(base, *parts))
    if not path.startswith(os.path.normpath(base)):
        raise ValueError('Path traversal detected')
    return path


def sanitize_name(name):
    return ''.join(c if c.isalnum() or c in ' _-.' else '_' for c in name)


def safe_path(base, name):
    safe = sanitize_name(name)
    return safe_join(base, safe)


def safe_write(path, content):
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
