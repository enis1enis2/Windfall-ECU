import subprocess
import os
import sys
import time
import threading
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_RESTART_SCRIPT = os.path.join(BASE_DIR, '.restart.sh')


def _git(*args, timeout=30):
    out_file = tempfile.NamedTemporaryFile(delete=False, mode='w+')
    err_file = tempfile.NamedTemporaryFile(delete=False, mode='w+')
    try:
        result = subprocess.run(
            ['git'] + list(args),
            cwd=BASE_DIR,
            stdout=out_file,
            stderr=err_file,
            timeout=timeout
        )
        out_file.seek(0)
        err_file.seek(0)
        result.stdout = out_file.read()
        result.stderr = err_file.read()
        return result
    finally:
        out_file.close()
        os.unlink(out_file.name)
        err_file.close()
        os.unlink(err_file.name)


def check_updates():
    try:
        _git('fetch', 'origin', timeout=30)
        result = _git('rev-list', '--count', 'HEAD..origin/main', timeout=10)
        behind = int(result.stdout.strip())
        if behind > 0:
            log_result = _git('log', '--oneline', f'-{behind}', 'HEAD..origin/main', timeout=10)
            return {
                'update_available': True,
                'commits_behind': behind,
                'log': log_result.stdout.strip()
            }
        return {'update_available': False, 'commits_behind': 0}
    except Exception as e:
        return {'update_available': False, 'error': str(e)}


def install_updates():
    try:
        result = _git('pull', 'origin', 'main', timeout=60)
        if result.returncode == 0:
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '-r',
                     os.path.join(BASE_DIR, 'requirements.txt'), '-q'],
                    cwd=BASE_DIR,                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120
                )
            except Exception:
                pass
            return {'success': True, 'output': result.stdout}
        return {'success': False, 'error': result.stderr}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _do_restart():
    time.sleep(1)
    script = (
        '#!/bin/bash\n'
        f'sleep 2\n'
        f'exec {sys.executable} "{os.path.join(BASE_DIR, "app.py")}"\n'
    )
    with open(_RESTART_SCRIPT, 'w') as f:
        f.write(script)
    os.chmod(_RESTART_SCRIPT, 0o755)
    subprocess.Popen(['bash', _RESTART_SCRIPT], cwd=BASE_DIR,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os._exit(0)


def schedule_restart():
    threading.Thread(target=_do_restart, daemon=True).start()
