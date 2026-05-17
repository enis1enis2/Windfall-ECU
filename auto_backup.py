import threading
import time
from datetime import datetime

from models import get_servers, get_server, get_backups, delete_backup_entry, get_setting, set_setting
from backup_manager import create_backup
from config import BACKUPS_DIR
import os
import shutil

_SCHEDULER_RUNNING = threading.Event()
_SCHEDULER_THREAD = None
_LAST_RUN = 0


def _scheduler_loop():
    while not _SCHEDULER_RUNNING.is_set():
        try:
            enabled = get_setting('auto_backup_enabled', 'false')
            if enabled == 'true':
                interval = int(get_setting('auto_backup_interval', '60'))
                retention = int(get_setting('auto_backup_retention', '10'))
                now = time.time()
                global _LAST_RUN
                if now - _LAST_RUN >= interval * 60:
                    _LAST_RUN = now
                    _run_backups(retention)
        except Exception:
            pass
        _SCHEDULER_RUNNING.wait(60)


def _run_backups(retention):
    servers = get_servers()
    for srv in servers:
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            create_backup(srv['id'], f"auto_{srv['name']}_{timestamp}")
            _prune_old_backups(srv['id'], retention)
        except Exception:
            pass


def _prune_old_backups(server_id, keep_count):
    backups = get_backups(server_id)
    if len(backups) <= keep_count:
        return
    for b in backups[keep_count:]:
        try:
            if os.path.isfile(b['path']):
                os.remove(b['path'])
        except Exception:
            pass
        delete_backup_entry(b['id'])


def start_auto_backup_scheduler():
    global _SCHEDULER_THREAD
    if _SCHEDULER_THREAD is not None:
        return
    _LAST_RUN = time.time()
    _SCHEDULER_THREAD = threading.Thread(target=_scheduler_loop, daemon=True)
    _SCHEDULER_THREAD.start()
