import subprocess
import os
import signal
import threading
import time
from config import JAVA_BIN, SERVERS_DIR


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
        self.log_pos = 0

    def start(self):
        if self.running:
            return False

        os.makedirs(self.workdir, exist_ok=True)
        cmd = f'{JAVA_BIN} {self.java_args} -jar {self.jar_file} nogui'

        self.process = subprocess.Popen(
            cmd,
            shell=True,
            cwd=self.workdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )

        self.running = True
        self.log_pos = 0
        self.read_thread = threading.Thread(target=self._read_output, daemon=True)
        self.read_thread.start()
        return True

    def _read_output(self):
        log_file = os.path.join(self.workdir, 'logs', 'latest.log')
        stdout_alive = True

        while self.running:
            # Read from stdout pipe
            if stdout_alive and self.process and self.process.stdout:
                try:
                    line = self.process.stdout.readline()
                    if line:
                        text = line.decode('utf-8', errors='replace')
                        if self.output_callback:
                            self.output_callback(text)
                    else:
                        stdout_alive = False
                except (OSError, ValueError):
                    stdout_alive = False

            # Also tail the log file for any missed output
            if os.path.isfile(log_file):
                try:
                    with open(log_file, 'r', errors='replace') as f:
                        f.seek(self.log_pos)
                        for line in f:
                            if self.output_callback:
                                self.output_callback(line)
                        self.log_pos = f.tell()
                except (OSError, PermissionError):
                    pass

            if not stdout_alive and not os.path.isfile(log_file):
                time.sleep(0.5)

        self.running = False

    def write_input(self, data):
        if self.process and self.process.stdin and self.running:
            try:
                self.process.stdin.write(data.encode('utf-8'))
                self.process.stdin.flush()
            except (OSError, BrokenPipeError):
                pass

    def stop(self):
        self.running = False
        if self.process:
            try:
                self.process.stdin.close()
            except:
                pass
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
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

def get_server_path(server_id, server_name):
    safe_name = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in server_name)
    return os.path.join(SERVERS_DIR, safe_name)
