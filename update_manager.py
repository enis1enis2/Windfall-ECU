import subprocess, os, sys, time, threading, tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_RESTART_SCRIPT = os.path.join(BASE_DIR, '.restart.sh')

def _git(*args, timeout=30):
    with tempfile.NamedTemporaryFile(delete=False, mode='w+') as out, \
         tempfile.NamedTemporaryFile(delete=False, mode='w+') as err:
        try:
            r = subprocess.run(['git'] + list(args), cwd=BASE_DIR, stdout=out, stderr=err, timeout=timeout)
            out.seek(0); err.seek(0)
            r.stdout, r.stderr = out.read(), err.read()
            return r
        finally:
            for f in [out, err]:
                f.close()
                try: os.unlink(f.name)
                except: pass

def _git_available():
    try: return subprocess.run(['git', '--version'], capture_output=True, timeout=5).returncode == 0
    except: return False

def check_updates():
    if not _git_available(): return {'update_available': False, 'error': 'git is not installed'}
    try:
        _git('fetch', 'origin', timeout=30)
        r = int(_git('rev-list', '--count', 'HEAD..origin/main', timeout=10).stdout.strip())
        if r > 0:
            log = _git('log', '--oneline', f'-{r}', 'HEAD..origin/main', timeout=10).stdout.strip()
            return {'update_available': True, 'commits_behind': r, 'log': log}
        return {'update_available': False, 'commits_behind': 0}
    except: return {'update_available': False, 'error': 'Update check failed'}

def install_updates():
    if not _git_available(): return {'success': False, 'error': 'git is not installed'}
    try:
        _git('stash', timeout=10)
        r = _git('pull', 'origin', 'main', timeout=60)
        _git('stash', 'drop', timeout=5)
        if r.returncode == 0:
            try: subprocess.run([sys.executable, '-m', 'pip', 'install', '-r',
                                os.path.join(BASE_DIR, 'requirements.txt'), '-q'],
                               cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            except: pass
            return {'success': True, 'output': r.stdout}
        return {'success': False, 'error': r.stderr}
    except: return {'success': False, 'error': 'Install failed'}

def _do_restart():
    time.sleep(1)
    with open(_RESTART_SCRIPT, 'w') as f:
        f.write(f'#!/bin/bash\nsleep 2\nexec {sys.executable} "{os.path.join(BASE_DIR, "app.py")}"\n')
    os.chmod(_RESTART_SCRIPT, 0o755)
    subprocess.Popen(['bash', _RESTART_SCRIPT], cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os._exit(0)

def schedule_restart():
    threading.Thread(target=_do_restart, daemon=True).start()
