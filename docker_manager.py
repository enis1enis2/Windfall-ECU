import subprocess, os

DOCKER_AVAILABLE = None

def check_docker():
    global DOCKER_AVAILABLE
    if DOCKER_AVAILABLE is not None: return DOCKER_AVAILABLE
    try:
        DOCKER_AVAILABLE = subprocess.run(['docker', '--version'], capture_output=True, timeout=5).returncode == 0
        return DOCKER_AVAILABLE
    except: DOCKER_AVAILABLE = False; return False

def create_docker_container(server_id, server_name, server_path, jar_file, java_args='-Xmx1G -Xms1G'):
    if not check_docker(): return False, 'Docker is not available'
    import shlex, json
    cn = f'windfall-ecu_{server_id}_{"".join(c if c.isalnum() or c in "_-" else "_" for c in server_name)}'
    cmd = json.dumps(['java'] + shlex.split(java_args) + ['-jar', jar_file, 'nogui'])
    with open(os.path.join(server_path, 'Dockerfile'), 'w') as f:
        f.write(f'FROM openjdk:21-slim AS mc-server\nWORKDIR /server\nCOPY . /server/\nCMD {cmd}\n')
    try:
        b = subprocess.run(['docker', 'build', '-t', cn, server_path], capture_output=True, text=True, timeout=120)
        if b.returncode != 0: return False, f'Docker build failed: {b.stderr[:500]}'
        r = subprocess.run(['docker', 'run', '-d', '--name', cn, '-v', f'{server_path}:/server', '-p', '25565:25565',
                           '--restart', 'unless-stopped', cn], capture_output=True, text=True, timeout=30)
        if r.returncode != 0: return False, f'Docker run failed: {r.stderr[:500]}'
        return True, cn
    except subprocess.TimeoutExpired: return False, 'Docker operation timed out'
    except: return False, 'Docker build/run failed'
