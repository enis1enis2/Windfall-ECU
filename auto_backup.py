import os, threading, time
from datetime import datetime
from models import get_servers, get_backups, delete_backup_entry, get_setting
from backup_manager import create_backup

_scheduler_stop = threading.Event()
_scheduler_thread = None
_last_run = 0

def _loop():
    while not _scheduler_stop.is_set():
        try:
            if get_setting('auto_backup_enabled', 'false') == 'true':
                global _last_run
                now = time.time()
                if now - _last_run >= int(get_setting('auto_backup_interval', '60')) * 60:
                    _last_run = now
                    for srv in get_servers():
                        try:
                            create_backup(srv['id'], f"auto_{srv['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                            bs = get_backups(srv['id'])
                            keep = int(get_setting('auto_backup_retention', '10'))
                            for b in bs[keep:]:
                                if os.path.isfile(b['path']): os.remove(b['path'])
                                delete_backup_entry(b['id'])
                        except Exception: pass
        except Exception: pass
        _scheduler_stop.wait(60)

def start_auto_backup_scheduler():
    global _scheduler_thread, _last_run
    if _scheduler_thread: return
    _last_run = time.time()
    _scheduler_thread = threading.Thread(target=_loop, daemon=True)
    _scheduler_thread.start()
