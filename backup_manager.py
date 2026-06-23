import os
import tarfile
import shutil
from datetime import datetime
from models import get_server, create_backup_entry, get_backup, delete_backup_entry, get_backups as db_get_backups
from path_util import safe_join, sanitize_name

list_backups = db_get_backups

def create_backup(server_id, name=None):
    server = get_server(server_id)
    if not server: return None, 'Server not found'
    if not os.path.isdir(server['path']): return None, 'Server directory not found'

    name = sanitize_name(name or f"{server['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    backup_dir = safe_join(server['path'], 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = safe_join(backup_dir, f'{name}.tar.gz')

    try:
        backup_basename = os.path.basename(server['path'])
        def _exclude_backups(ti):
            parts = ti.name.split('/')
            return None if len(parts) > 1 and parts[1] == 'backups' else ti
        with tarfile.open(backup_path, 'w:gz') as tar:
            tar.add(server['path'], arcname=backup_basename, filter=_exclude_backups)
    except Exception:
        if os.path.exists(backup_path): os.remove(backup_path)
        return None, 'Backup failed'

    backup_id = create_backup_entry(server_id, name, backup_path, os.path.getsize(backup_path))
    return backup_id, None

def restore_backup(backup_id):
    backup = get_backup(backup_id)
    if not backup: return False, 'Backup not found'
    server = get_server(backup['server_id'])
    if not server: return False, 'Server not found'

    from server_manager import get_server_process
    sp = get_server_process(backup['server_id'])
    if sp and sp.is_running:
        return False, 'Stop the server before restoring a backup'

    bp, spath = backup['path'], server['path']
    if not os.path.isfile(bp): return False, 'Backup file not found'

    tmp = spath + '_restore_tmp'
    from path_util import is_within_directory
    try:
        if os.path.exists(tmp): shutil.rmtree(tmp)
        with tarfile.open(bp, 'r:gz') as tar:
            for member in tar.getmembers():
                if not is_within_directory(tmp, os.path.join(tmp, member.name)):
                    raise Exception('Potential Path Traversal in Tar')
            tar.extractall(tmp)

        items = []
        for root, dirs, files in os.walk(tmp):
            items = [os.path.relpath(os.path.join(root, x), tmp) for x in dirs + files]
            break

        if not items:
            shutil.rmtree(tmp)
            return False, 'Backup is empty'

        for item in os.listdir(spath):
            ip = os.path.join(spath, item)
            if os.path.isfile(ip) and item == 'session.lock': continue
            (shutil.rmtree if os.path.isdir(ip) else os.remove)(ip)

        for item in items:
            s, d = os.path.join(tmp, item), os.path.join(spath, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)

        shutil.rmtree(tmp)
        return True, 'Backup restored successfully'
    except Exception:
        if os.path.exists(tmp): shutil.rmtree(tmp, ignore_errors=True)
        return False, 'Restore failed'

def delete_backup(backup_id):
    backup = get_backup(backup_id)
    if not backup: return False, 'Backup not found'
    if os.path.isfile(backup['path']): os.remove(backup['path'])
    delete_backup_entry(backup_id)
    return True, 'Backup deleted'
