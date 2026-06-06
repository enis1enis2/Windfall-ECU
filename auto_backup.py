import os, threading, time
from datetime import datetime
from models import get_servers, get_backups, delete_backup_entry, get_setting
from backup_manager import create_backup

_scheduler_thread = None

def _run():
    while True:
        try:
            if get_setting('auto_backup_enabled', 'false') != 'true':
                time.sleep(60)
                continue
            interval = max(1, int(get_setting('auto_backup_interval', '60'))) * 60
            _last_run = time.time()
            for srv in get_servers():
                try:
                    create_backup(srv['id'], f"auto_{srv['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                    bs = get_backups(srv['id'])
                    keep = max(1, int(get_setting('auto_backup_retention', '10')))
                    for b in bs[keep:]:
                        if os.path.isfile(b['path']):
                            os.remove(b['path'])
                        delete_backup_entry(b['id'])
                except Exception:
                    pass
            remaining = interval - (time.time() - _last_run)
            if remaining > 0:
                time.sleep(remaining)
        except Exception:
            time.sleep(60)

def start_auto_backup_scheduler():
    global _scheduler_thread
    if _scheduler_thread:
        return
    _scheduler_thread = threading.Thread(target=_run, daemon=True)
    _scheduler_thread.start()
