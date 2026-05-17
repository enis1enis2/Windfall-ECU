import subprocess
import os
import signal
import pty
import select
import fcntl
import struct
import termios
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
        self.master_fd = None
        self.slave_fd = None
        self.running = False
        self.output_callback = None
        self.read_thread = None

    def start(self):
        if self.running:
            return False

        os.makedirs(self.workdir, exist_ok=True)
        cmd = f'{JAVA_BIN} {self.java_args} -jar {self.jar_file} nogui'

        self.master_fd, self.slave_fd = pty.openpty()

        self.process = subprocess.Popen(
            cmd,
            shell=True,
            cwd=self.workdir,
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            preexec_fn=os.setsid,
            close_fds=True
        )

        os.close(self.slave_fd)
        self.slave_fd = None

        self.running = True
        self.read_thread = threading.Thread(target=self._read_output, daemon=True)
        self.read_thread.start()
        return True

    def _read_output(self):
        while self.running:
            try:
                r, w, e = select.select([self.master_fd], [], [], 0.1)
                if r:
                    output = os.read(self.master_fd, 65536)
                    if output:
                        if self.output_callback:
                            self.output_callback(output.decode('utf-8', errors='replace'))
                    else:
                        break
            except (OSError, ValueError):
                break
        self.running = False

    def write_input(self, data):
        if self.master_fd is not None and self.running:
            try:
                os.write(self.master_fd, data.encode('utf-8'))
            except OSError:
                pass

    def set_size(self, rows, cols):
        if self.master_fd is not None:
            try:
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ,
                            struct.pack('HHHH', rows, cols, 0, 0))
            except OSError:
                pass

    def stop(self):
        self.running = False
        if self.process:
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

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except OSError:
                pass
            self.slave_fd = None

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
