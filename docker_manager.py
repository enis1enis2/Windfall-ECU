import subprocess
import os
import shutil
import json
import time
from config import SERVERS_DIR

DOCKER_AVAILABLE = None


def check_docker():
    global DOCKER_AVAILABLE
    if DOCKER_AVAILABLE is not None:
        return DOCKER_AVAILABLE
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
        DOCKER_AVAILABLE = result.returncode == 0
        return DOCKER_AVAILABLE
    except (FileNotFoundError, subprocess.TimeoutExpired):
        DOCKER_AVAILABLE = False
        return False


def create_docker_container(server_id, server_name, server_path, jar_file, java_args='-Xmx1G -Xms1G'):
    if not check_docker():
        return False, 'Docker is not available'

    safe_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in server_name)
    container_name = f'windfall-ecu_{server_id}_{safe_name}'

    import shlex
    cmd_parts = ['java'] + shlex.split(java_args) + ['-jar', jar_file, 'nogui']
    cmd_json = json.dumps(cmd_parts)
    dockerfile = f'''FROM openjdk:21-slim AS mc-server
WORKDIR /server
COPY . /server/
CMD {cmd_json}
'''

    dockerfile_path = os.path.join(server_path, 'Dockerfile')
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile)

    try:
        build = subprocess.run(
            ['docker', 'build', '-t', container_name, server_path],
            capture_output=True, text=True, timeout=120
        )
        if build.returncode != 0:
            return False, f'Docker build failed: {build.stderr[:500]}'

        run = subprocess.run(
            ['docker', 'run', '-d', '--name', container_name,
             '-v', f'{server_path}:/server',
             '-p', '25565:25565',
             '--restart', 'unless-stopped',
             container_name],
            capture_output=True, text=True, timeout=30
        )
        if run.returncode != 0:
            return False, f'Docker run failed: {run.stderr[:500]}'

        return True, container_name
    except subprocess.TimeoutExpired:
        return False, 'Docker operation timed out'
    except Exception as e:
        return False, str(e)


def stop_docker_container(container_name):
    if not check_docker():
        return False, 'Docker not available'
    try:
        subprocess.run(['docker', 'stop', container_name], capture_output=True, text=True, timeout=30)
        subprocess.run(['docker', 'rm', container_name], capture_output=True, text=True, timeout=30)
        return True, 'Container stopped and removed'
    except Exception as e:
        return False, str(e)


def get_docker_logs(container_name, tail=100):
    if not check_docker():
        return None, 'Docker not available'
    try:
        result = subprocess.run(
            ['docker', 'logs', '--tail', str(tail), container_name],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout + result.stderr, None
    except Exception as e:
        return None, str(e)


def docker_exec_command(container_name, command):
    if not check_docker():
        return None, 'Docker not available'
    try:
        result = subprocess.run(
            ['docker', 'exec', '-i', container_name] + command.split(),
            capture_output=True, text=True, timeout=30
        )
        return result.stdout + result.stderr, None
    except Exception as e:
        return None, str(e)
