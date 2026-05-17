import os
import tarfile
import shutil
import time
from datetime import datetime
from config import BACKUPS_DIR, SERVERS_DIR
from models import get_server, create_backup_entry, get_backup, delete_backup_entry, get_backups as db_get_backups


def list_backups(server_id):
    return db_get_backups(server_id)


def create_backup(server_id, name=None):
    server = get_server(server_id)
    if not server:
        return None, 'Server not found'

    server_path = server['path']
    if not os.path.isdir(server_path):
        return None, 'Server directory not found'

    if not name:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name = f"{server['name']}_{timestamp}"

    safe_name = ''.join(c if c.isalnum() or c in ' _-.' else '_' for c in name)
    backup_dir = os.path.join(BACKUPS_DIR, str(server_id))
    os.makedirs(backup_dir, exist_ok=True)

    backup_path = os.path.join(backup_dir, f'{safe_name}.tar.gz')

    try:
        with tarfile.open(backup_path, 'w:gz') as tar:
            tar.add(server_path, arcname=os.path.basename(server_path))
    except Exception as e:
        return None, str(e)

    size = os.path.getsize(backup_path)
    backup_id = create_backup_entry(server_id, name, backup_path, size)

    return backup_id, None


def restore_backup(backup_id):
    backup = get_backup(backup_id)
    if not backup:
        return False, 'Backup not found'

    server = get_server(backup['server_id'])
    if not server:
        return False, 'Server not found'

    from server_manager import get_server_process
    proc = get_server_process(backup['server_id'])
    if proc and proc.is_running:
        return False, 'Stop the server before restoring a backup'

    backup_path = backup['path']
    if not os.path.isfile(backup_path):
        return False, 'Backup file not found'

    server_path = server['path']
    temp_dir = server_path + '_restore_tmp'

    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        with tarfile.open(backup_path, 'r:gz') as tar:
            tar.extractall(temp_dir)

        extracted_items = []
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), temp_dir)
                extracted_items.append(rel)
            for d in dirs:
                rel = os.path.relpath(os.path.join(root, d), temp_dir)
                extracted_items.append(rel)
            break

        if not extracted_items:
            shutil.rmtree(temp_dir)
            return False, 'Backup is empty'

        for item in os.listdir(server_path):
            item_path = os.path.join(server_path, item)
            if os.path.isfile(item_path) and item == 'session.lock':
                continue
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

        for item in extracted_items:
            s = os.path.join(temp_dir, item)
            d = os.path.join(server_path, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)

        shutil.rmtree(temp_dir)
        return True, 'Backup restored successfully'
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        return False, str(e)


def delete_backup(backup_id):
    backup = get_backup(backup_id)
    if not backup:
        return False, 'Backup not found'

    backup_path = backup['path']
    if os.path.isfile(backup_path):
        os.remove(backup_path)

    delete_backup_entry(backup_id)
    return True, 'Backup deleted'
