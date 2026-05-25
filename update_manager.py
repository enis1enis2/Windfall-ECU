import subprocess, os, sys, time, threading, tempfile, signal

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

def _find_python():
    candidates = ['python3.14', 'python3.13', 'python3.12', 'python3.11', 'python3.10',
                  'python3.9', 'python3.8', 'python3', 'python']
    extra = ['/usr/bin', '/usr/local/bin', os.path.expanduser('~/.local/bin'),
             '/opt/homebrew/bin', '/opt/bin']
    seen = set()
    for c in candidates:
        for p in [c] + [os.path.join(d, c) for d in extra]:
            if p in seen: continue
            seen.add(p)
            try:
                r = subprocess.run([p, '--version'], capture_output=True, timeout=5)
                if r.returncode == 0:
                    ver = r.stdout.decode().strip()
                    if 'Python 3.' in ver:
                        return p
            except: pass
    return sys.executable

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
        stash_was_empty = 'No local changes' in _git('stash', timeout=10).stderr
        r = _git('pull', 'origin', 'main', timeout=60)
        if not stash_was_empty:
            _git('stash', 'drop', timeout=5)
        if r.returncode == 0:
            try: subprocess.run([sys.executable, '-m', 'pip', 'install', '-r',
                                os.path.join(BASE_DIR, 'requirements.txt'), '-q'],
                               cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            except: pass
            return {'success': True, 'output': r.stdout}
        return {'success': False, 'error': r.stderr}
    except: return {'success': False, 'error': 'Install failed'}

def _restart_script():
    from config import PORT
    py = _find_python()
    app_path = os.path.join(BASE_DIR, 'app.py')
    return f'''#!/usr/bin/env bash
sleep 3
cd "{BASE_DIR}"
# Kill old process by port
fuser -k {PORT}/tcp 2>/dev/null
sleep 1
fuser -k {PORT}/tcp 2>/dev/null || lsof -ti :{PORT} 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1
# Launch detached
nohup "{py}" "{app_path}" > /dev/null 2>&1 &
disown
'''

def schedule_restart():
    py = _find_python()
    app_path = os.path.join(BASE_DIR, 'app.py')
    script = _restart_script()
    with open(_RESTART_SCRIPT, 'w') as f:
        f.write(script)
    os.chmod(_RESTART_SCRIPT, 0o755)
    # Use os.system to avoid eventlet subprocess patching issues with process groups
    os.system(f'bash "{_RESTART_SCRIPT}" &')
