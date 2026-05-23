import re
import subprocess
import os
import signal
import threading
import time
import shlex
from collections import deque
from config import JAVA_BIN

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
MC_COLOR_RE = re.compile(r'§[0-9a-fklmnor]')

def clean_output(text):
    text = ANSI_RE.sub('', text)
    text = MC_COLOR_RE.sub('', text)
    return text


class ConsoleBuffer:
    def __init__(self, maxlen=5000):
        self.lines = deque(maxlen=maxlen)
        self.lock = threading.Lock()

    def append(self, text):
        with self.lock:
            for line in text.splitlines(True):
                self.lines.append(line)

    def get_since(self, pos):
        with self.lock:
            total = len(self.lines)
            if pos >= total:
                return '', total
            result = ''.join(list(self.lines)[pos:])
            return result, total

    def get_all(self):
        with self.lock:
            return ''.join(self.lines), len(self.lines)


class ServerProcess:
    def __init__(self, server_id, workdir, jar_file, java_args):
        self.server_id = server_id
        self.workdir = workdir
        self.jar_file = jar_file
        self.java_args = java_args
        self.process = None
        self.running = False
        self.output_callback = None
        self.read_thread = None
        self.buffer = ConsoleBuffer()
        self._stop_event = threading.Event()

    def _free_port(self):
        props = os.path.join(self.workdir, 'server.properties')
        port = '25565'
        if os.path.isfile(props):
            try:
                with open(props) as f:
                    for line in f:
                        m = re.match(r'^server-port=(\d+)', line.strip())
                        if m:
                            port = m.group(1)
                            break
            except OSError:
                pass
        try:
            subprocess.run(['fuser', '-k', f'{port}/tcp'], capture_output=True, timeout=5)
        except Exception:
            pass
        try:
            r = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True, timeout=5)
            if r.stdout.strip():
                subprocess.run(['kill', '-9'] + r.stdout.strip().splitlines(), capture_output=True, timeout=3)
        except Exception:
            pass

    def start(self):
        if self.running:
            return False

        os.makedirs(self.workdir, exist_ok=True)
        os.makedirs(os.path.join(self.workdir, 'logs'), exist_ok=True)
        self._free_port()

        java_opts = ['-Dlog4j.configurationFile=log4j2.xml', '-Dconsole.encoding=UTF-8']
        cmd = [JAVA_BIN] + java_opts + shlex.split(self.java_args) + ['-jar', self.jar_file, 'nogui']

        self.process = subprocess.Popen(
            cmd,
            cwd=self.workdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )

        self.running = True
        self._stop_event.clear()

        self.read_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self.read_thread.start()

        return True

    def _read_stdout(self):
        while not self._stop_event.is_set() and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                text = clean_output(line.decode('utf-8', errors='replace'))
                self.buffer.append(text)
                if self.output_callback:
                    self.output_callback(text)
            except (OSError, ValueError):
                break
        self.running = False

    def write_input(self, data):
        if self.process and self.process.stdin and self.running:
            try:
                self.process.stdin.write(data.encode('utf-8'))
                self.process.stdin.flush()
            except (OSError, BrokenPipeError):
                pass

    def stop(self):
        self._stop_event.set()
        self.running = False
        if self.process:
            try:
                self.process.stdin.close()
            except (OSError, BrokenPipeError):
                pass
            try:
                pgid = os.getpgid(self.process.pid)
                os.killpg(pgid, signal.SIGTERM)
                self.process.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
                try:
                    pgid = os.getpgid(self.process.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass

    @property
    def is_running(self):
        if self.process and self.process.poll() is None:
            return True
        return False

    def get_status(self):
        if not self.process:
            return {'running': False, 'pid': None}
        rc = self.process.poll()
        if rc is not None:
            return {'running': False, 'returncode': rc, 'pid': None}
        return {'running': True, 'pid': self.process.pid}


_servers = {}

def get_server_process(server_id):
    return _servers.get(server_id)

def register_server(server_id, server_proc):
    _servers[server_id] = server_proc

def unregister_server(server_id):
    if server_id in _servers:
        proc = _servers[server_id]
        if proc:
            proc.stop()
        del _servers[server_id]




