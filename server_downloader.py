import requests
import os
import json
import re
import zipfile
import io
import shutil
from config import SERVERS_DIR

PAPER_API = 'https://api.papermc.io/v2/projects/paper'
FOLIA_API = 'https://api.papermc.io/v2/projects/folia'
PURPUR_API = 'https://api.purpurmc.org/v2/purpur'
VANILLA_MANIFEST = 'https://launchermeta.mojang.com/mc/game/version_manifest_v2.json'
FORGE_PROMOS = 'https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json'
NEOFORGE_API = 'https://api.neoforged.net/api/v1/versions'
FABRIC_META = 'https://meta.fabricmc.net/v2/versions'
QUILT_META = 'https://meta.quiltmc.org/v3/versions'

TIMEOUT = 30

SERVER_TYPES = {
    'paper':    {'name': 'Paper',     'api': 'papermc'},
    'folia':    {'name': 'Folia',     'api': 'papermc'},
    'purpur':   {'name': 'Purpur',    'api': 'purpur'},
    'vanilla':  {'name': 'Vanilla',   'api': 'vanilla'},
    'fabric':   {'name': 'Fabric',    'api': 'fabric'},
    'quilt':    {'name': 'Quilt',     'api': 'quilt'},
    'forge':    {'name': 'Forge',     'api': 'forge'},
    'neoforge': {'name': 'NeoForge',  'api': 'neoforge'},
}


def get_types():
    return [{'id': k, 'name': v['name']} for k, v in SERVER_TYPES.items()]


def fetch_json(url):
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_versions(server_type):
    if server_type == 'paper':
        data = fetch_json(PAPER_API)
        if not isinstance(data, dict):
            return []
        return data.get('versions', [])[::-1]

    if server_type == 'folia':
        data = fetch_json(FOLIA_API)
        if not isinstance(data, dict):
            return []
        return data.get('versions', [])[::-1]

    if server_type == 'purpur':
        data = fetch_json(PURPUR_API)
        versions = data.get('versions', {})
        if isinstance(versions, dict):
            return sorted(versions.keys(), key=lambda v: [int(x) if x.isdigit() else x for x in v.split('.')], reverse=True)
        return []

    if server_type == 'vanilla':
        data = fetch_json(VANILLA_MANIFEST)
        releases = []
        for v in data.get('versions', []):
            if v['type'] == 'release':
                releases.append(v['id'])
        return releases[::-1]

    if server_type == 'fabric':
        data = fetch_json(f'{FABRIC_META}/game')
        if not isinstance(data, list):
            return []
        return [v['version'] for v in data if isinstance(v, dict) and v.get('stable', False)][::-1]

    if server_type == 'quilt':
        data = fetch_json(f'{QUILT_META}/game')
        if not isinstance(data, list):
            return []
        return [v['version'] for v in data if isinstance(v, dict)][::-1]

    if server_type == 'forge':
        try:
            data = fetch_json(FORGE_PROMOS)
            promos = data.get('promos', {})
            versions = set()
            for k in promos:
                parts = k.split('-')
                if parts[0]:
                    versions.add(parts[0])
            return sorted(versions, key=lambda v: [int(x) if x.isdigit() else x for x in v.split('.')], reverse=True)
        except Exception:
            return ['latest']

    if server_type == 'neoforge':
        try:
            data = fetch_json(NEOFORGE_API)
            versions = data if isinstance(data, list) else []
            return sorted(versions, key=lambda v: [int(x) if x.isdigit() else x for x in v.split('.')], reverse=True)
        except Exception:
            return ['latest']

    return []


def get_builds(server_type, version):
    if server_type in ('paper', 'folia'):
        project = 'paper' if server_type == 'paper' else 'folia'
        api = PAPER_API if server_type == 'paper' else FOLIA_API
        data = fetch_json(f'{api}/versions/{version}/builds')
        if not isinstance(data, dict):
            return []
        builds = [b for b in data.get('builds', []) if isinstance(b, dict) and b.get('channel') == 'default']
        if not builds:
            builds = data.get('builds', [])
        return [{'build': b['build'], 'channel': b.get('channel', 'unknown')} for b in builds if isinstance(b, dict)]

    if server_type == 'purpur':
        data = fetch_json(f'{PURPUR_API}/{version}')
        if not isinstance(data, dict):
            return []
        builds_obj = data.get('builds', {})
        if not isinstance(builds_obj, dict):
            return []
        all_builds = builds_obj.get('all', [])
        return [{'build': b} for b in all_builds]

    return []


def download_server(server_type, version, build=None, server_name=None):
    if server_type == 'paper':
        return _download_paper('paper', version, build, server_name)
    if server_type == 'folia':
        return _download_paper('folia', version, build, server_name)
    if server_type == 'purpur':
        return _download_purpur(version, build, server_name)
    if server_type == 'vanilla':
        return _download_vanilla(version, server_name)
    if server_type == 'fabric':
        return _download_fabric(version, server_name)
    if server_type == 'quilt':
        return _download_quilt(version, server_name)
    if server_type == 'forge':
        return _download_forge(version, server_name)
    if server_type == 'neoforge':
        return _download_neoforge(version, server_name)
    return None, 'Unknown server type'


def _download_paper(project, version, build, server_name):
    if build is None:
        data = fetch_json(f'https://api.papermc.io/v2/projects/{project}/versions/{version}/builds')
        if not isinstance(data, dict):
            return None, 'Invalid API response'
        bs = [b for b in data.get('builds', []) if isinstance(b, dict) and b.get('channel') == 'default']
        if not bs:
            bs = data.get('builds', [])
        if not bs:
            return None, 'No builds found'
        build = bs[-1]['build']

    jar_name = f'{project}-{version}-{build}.jar'
    url = f'https://api.papermc.io/v2/projects/{project}/versions/{version}/builds/{build}/downloads/{jar_name}'

    return _download_and_create_server(url, jar_name, version, server_name or f'{project.title()} {version}')


def _download_purpur(version, build, server_name):
    if build is None:
        data = fetch_json(f'{PURPUR_API}/{version}')
        if not isinstance(data, dict):
            return None, 'Invalid API response'
        builds_obj = data.get('builds', {})
        all_b = builds_obj.get('all', []) if isinstance(builds_obj, dict) else []
        if not all_b:
            return None, 'No builds found'
        build = all_b[-1]

    url = f'{PURPUR_API}/{version}/{build}/download'
    jar_name = f'purpur-{version}-{build}.jar'
    return _download_and_create_server(url, jar_name, version, server_name or f'Purpur {version}')


def _download_vanilla(version, server_name):
    data = fetch_json(VANILLA_MANIFEST)
    target = None
    for v in data.get('versions', []):
        if v['id'] == version:
            target = v
            break
    if not target:
        return None, f'Version {version} not found'

    vdata = fetch_json(target['url'])
    jar_url = vdata.get('downloads', {}).get('server', {}).get('url')
    if not jar_url:
        return None, 'No server download URL found'

    return _download_and_create_server(jar_url, f'server.jar', version, server_name or f'Vanilla {version}')


def _download_fabric(version, server_name):
    loaders = fetch_json(f'{FABRIC_META}/loader')
    stable = [l for l in loaders if l.get('stable', False)]
    loader = stable[0] if stable else loaders[0]
    loader_version = loader['loader']['version']

    url = f'{FABRIC_META}/loader/{version}/{loader_version}/server/json'
    return _download_fabric_quilt_jar(url, f'fabric-server-mc.{version}-loader.{loader_version}.jar',
                                      version, server_name or f'Fabric {version}')


def _download_quilt(version, server_name):
    loaders = fetch_json(f'{QUILT_META}/loader')
    loader = loaders[0] if loaders else None
    if not loader:
        return None, 'No loader found'
    loader_version = loader['loader']['version']

    url = f'{QUILT_META}/loader/{version}/{loader_version}/server/json'
    return _download_fabric_quilt_jar(url, f'quilt-server-mc.{version}-loader.{loader_version}.jar',
                                      version, server_name or f'Quilt {version}')


def _download_fabric_quilt_jar(meta_url, jar_name, version, server_name):
    meta = fetch_json(meta_url)
    if not isinstance(meta, dict):
        return None, 'Invalid meta response'

    main_class = meta.get('mainClass', {})
    if isinstance(main_class, dict):
        main_class = main_class.get('server', '')

    libraries = meta.get('libraries', [])
    lib_urls = []
    for lib in libraries:
        if 'downloads' in lib and 'artifact' in lib['downloads']:
            lib_urls.append(lib['downloads']['artifact']['url'])

    server_data = meta.get('downloads', {}).get('server', {})
    server_url = server_data.get('url', '')
    if not server_url:
        return None, 'No server download URL in meta'

    tmp = os.path.join(SERVERS_DIR, f'_dl_{version.replace(".", "_")}')
    os.makedirs(tmp, exist_ok=True)

    try:
        jar_path = os.path.join(tmp, jar_name)
        r = requests.get(server_url, timeout=120)
        r.raise_for_status()
        with open(jar_path, 'wb') as f:
            f.write(r.content)

        libs_dir = os.path.join(tmp, 'libraries')
        os.makedirs(libs_dir, exist_ok=True)
        for lib_url in lib_urls[:20]:
            try:
                lr = requests.get(lib_url, timeout=30)
                lr.raise_for_status()
                lib_name = lib_url.split('/')[-1]
                with open(os.path.join(libs_dir, lib_name), 'wb') as lf:
                    lf.write(lr.content)
            except Exception:
                pass

        safe_name = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in server_name)
        server_path = os.path.join(SERVERS_DIR, safe_name)
        if os.path.exists(server_path):
            shutil.rmtree(tmp)
            return None, f'Server "{safe_name}" already exists'

        shutil.copytree(tmp, server_path)
        shutil.rmtree(tmp)

        from models import create_server
        server_id = create_server(name=server_name, path=server_path, jar_file=jar_name,
                                  java_args='-Xmx2G -Xms1G', server_type='fabric' if 'fabric' in server_name.lower() else 'quilt')
        return server_id, None

    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, str(e)


def _download_forge(version, server_name):
    url = f'https://maven.minecraftforge.net/net/minecraftforge/forge/{version}/forge-{version}-installer.jar'
    jar_name = f'forge-{version}-installer.jar'
    return _download_and_create_server(url, jar_name, version, server_name or f'Forge {version}')


def _download_neoforge(version, server_name):
    url = f'https://maven.neoforged.net/releases/net/neoforged/neoforge/{version}/neoforge-{version}-installer.jar'
    jar_name = f'neoforge-{version}-installer.jar'
    return _download_and_create_server(url, jar_name, version, server_name or f'NeoForge {version}')


def _download_and_create_server(jar_url, jar_name, version, server_name):
    tmp = os.path.join(SERVERS_DIR, f'_dl_{version.replace(".", "_")}')
    os.makedirs(tmp, exist_ok=True)

    try:
        jar_path = os.path.join(tmp, jar_name)
        r = requests.get(jar_url, stream=True, timeout=120)
        r.raise_for_status()
        with open(jar_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        safe_name = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in server_name)
        server_path = os.path.join(SERVERS_DIR, safe_name)
        if os.path.exists(server_path):
            shutil.rmtree(tmp)
            return None, f'Server "{safe_name}" already exists'

        shutil.copytree(tmp, server_path)
        shutil.rmtree(tmp)

        from models import create_server
        server_id = create_server(name=server_name, path=server_path, jar_file=jar_name,
                                  java_args='-Xmx2G -Xms1G', server_type=server_name.lower().split()[0])
        return server_id, None

    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, str(e)
