import requests
import os
import json
import re
import zipfile
import io
import shutil
from config import SERVERS_DIR
from path_util import safe_join, safe_path, safe_write

PAPER_API = 'https://api.papermc.io/v2/projects/paper'
FOLIA_API = 'https://api.papermc.io/v2/projects/folia'
PURPUR_API = 'https://api.purpurmc.org/v2/purpur'
VANILLA_MANIFEST = 'https://launchermeta.mojang.com/mc/game/version_manifest_v2.json'
FORGE_PROMOS = 'https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json'
NEOFORGE_MAVEN = 'https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml'
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
        versions = data.get('versions', [])[::-1]
        if versions and '26.1.2' not in versions:
            versions.insert(0, '26.1.2')
        return versions

    if server_type == 'folia':
        data = fetch_json(FOLIA_API)
        if not isinstance(data, dict):
            return []
        versions = data.get('versions', [])[::-1]
        if versions and '26.1.2' not in versions:
            versions.insert(0, '26.1.2')
        return versions

    if server_type == 'purpur':
        data = fetch_json(PURPUR_API)
        versions = data.get('versions', [])
        if isinstance(versions, list):
            return sorted(versions, key=lambda v: [int(x) if x.isdigit() else x for x in v.split('.')], reverse=True)
        if isinstance(versions, dict):
            return sorted(versions.keys(), key=lambda v: [int(x) if x.isdigit() else x for x in v.split('.')], reverse=True)
        return []

    if server_type == 'vanilla':
        data = fetch_json(VANILLA_MANIFEST)
        releases = []
        for v in data.get('versions', []):
            if v['type'] == 'release':
                releases.append(v['id'])
        return releases

    if server_type == 'fabric':
        data = fetch_json(f'{FABRIC_META}/game')
        if not isinstance(data, list):
            return []
        versions = [v['version'] for v in data if isinstance(v, dict) and v.get('stable', False)]
        return sorted(versions, key=lambda v: [int(x) if x.isdigit() else x for x in v.split('.')], reverse=True)

    if server_type == 'quilt':
        data = fetch_json(f'{QUILT_META}/game')
        if not isinstance(data, list):
            return []
        versions = [v['version'] for v in data if isinstance(v, dict)]
        return sorted(versions, key=lambda v: [int(x) if x.isdigit() and x else 0 for x in re.split(r'[.\-]', v)], reverse=True)

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
            import xml.etree.ElementTree as ET
            r = requests.get(NEOFORGE_MAVEN, timeout=TIMEOUT)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            versions = [v.text for v in root.findall('.//version') if v.text]
            if not versions:
                return ['latest']
            return sorted(versions, key=lambda v: [int(x) if x.isdigit() and x else 0 for x in v.replace('-beta', '.0').replace('-alpha', '.0').split('.')], reverse=True)
        except Exception:
            return ['latest']

    return []


def get_builds(server_type, version):
    if server_type in ('paper', 'folia'):
        project = 'paper' if server_type == 'paper' else 'folia'
        api = PAPER_API if server_type == 'paper' else FOLIA_API
        unlisted = _PAPER_UNLISTED if project == 'paper' else _FOLIA_UNLISTED
        if version in unlisted:
            return [{'build': b, 'channel': 'default'} for b in unlisted[version]]
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
        return _download_paper('paper', version, build, server_name, server_type)
    if server_type == 'folia':
        return _download_paper('folia', version, build, server_name, server_type)
    if server_type == 'purpur':
        return _download_purpur(version, build, server_name, server_type)
    if server_type == 'vanilla':
        return _download_vanilla(version, server_name, server_type)
    if server_type == 'fabric':
        return _download_fabric(version, server_name, server_type)
    if server_type == 'quilt':
        return _download_quilt(version, server_name, server_type)
    if server_type == 'forge':
        return _download_forge(version, server_name, server_type)
    if server_type == 'neoforge':
        return _download_neoforge(version, server_name, server_type)
    return None, 'Unknown server type'


_PAPER_UNLISTED = {
    '26.1.2': {64: '830d4eb5c15cbd802a9ec9f2f54eaaaeb9511958339aec983fd0c88bad21d940'},
}
_FOLIA_UNLISTED = {
    '26.1.2': {8: '607afd1c3320008e1ffd2eaee6780ace4419d5f8c527b75e79f259be79ebf57b'},
}


def _paper_download_url(project, version, build, jar_name):
    unlisted = _PAPER_UNLISTED if project == 'paper' else _FOLIA_UNLISTED
    if version in unlisted and build in unlisted[version]:
        sha256 = unlisted[version][build]
        return f'https://fill-data.papermc.io/v1/objects/{sha256}/{jar_name}'
    try:
        build_data = fetch_json(f'https://api.papermc.io/v2/projects/{project}/versions/{version}/builds/{build}')
        if isinstance(build_data, dict) and 'downloads' in build_data:
            app = build_data['downloads'].get('application', {})
            sha256 = app.get('sha256', '')
            if sha256:
                return f'https://fill-data.papermc.io/v1/objects/{sha256}/{jar_name}'
    except Exception:
        pass
    return f'https://api.papermc.io/v2/projects/{project}/versions/{version}/builds/{build}/downloads/{jar_name}'


def _download_paper(project, version, build, server_name, server_type=None):
    if build is None:
        unlisted = _PAPER_UNLISTED if project == 'paper' else _FOLIA_UNLISTED
        if version in unlisted:
            build = max(unlisted[version].keys())
        else:
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
    url = _paper_download_url(project, version, build, jar_name)

    return _download_and_create_server(url, jar_name, version, server_name or f'{project.title()} {version}', server_type or project)


def _download_purpur(version, build, server_name, server_type='purpur'):
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
    return _download_and_create_server(url, jar_name, version, server_name or f'Purpur {version}', server_type)


def _download_vanilla(version, server_name, server_type='vanilla'):
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

    return _download_and_create_server(jar_url, f'server.jar', version, server_name or f'Vanilla {version}', server_type)


def _get_loader_version(meta_url):
    loaders = fetch_json(meta_url)
    if not isinstance(loaders, list) or not loaders:
        return None
    stable = [l for l in loaders if l.get('stable', False)]
    entry = stable[0] if stable else loaders[0]
    if 'loader' in entry and isinstance(entry['loader'], dict):
        return entry['loader']['version']
    return entry.get('version')


def _download_fabric(version, server_name, server_type='fabric'):
    loader_version = _get_loader_version(f'{FABRIC_META}/loader')
    if not loader_version:
        return None, 'Could not find Fabric loader version'
    url = f'{FABRIC_META}/loader/{version}/{loader_version}/server/json'
    return _download_fabric_quilt_jar(url, f'fabric-server-mc.{version}-loader.{loader_version}.jar',
                                      version, server_name or f'Fabric {version}', server_type)


def _download_quilt(version, server_name, server_type='quilt'):
    loader_version = _get_loader_version(f'{QUILT_META}/loader')
    if not loader_version:
        return None, 'Could not find Quilt loader version'
    url = f'{QUILT_META}/loader/{version}/{loader_version}/server/json'
    return _download_fabric_quilt_jar(url, f'quilt-server-mc.{version}-loader.{loader_version}.jar',
                                      version, server_name or f'Quilt {version}', server_type)


def _maven_url(base_url, coord):
    parts = coord.split(':')
    if len(parts) >= 3:
        group, artifact, ver = parts[0], parts[1], parts[2]
        path = f'{group.replace(".", "/")}/{artifact}/{ver}/{artifact}-{ver}.jar'
        return base_url.rstrip('/') + '/' + path
    return None


def _download_fabric_quilt_jar(meta_url, jar_name, version, server_name, server_type='fabric'):
    meta = fetch_json(meta_url)
    if not isinstance(meta, dict):
        return None, 'Invalid meta response'

    inherits = meta.get('inheritsFrom', version)
    main_class = meta.get('mainClass', {})
    if isinstance(main_class, dict):
        main_class = main_class.get('server', '')

    vanilla_data = fetch_json(VANILLA_MANIFEST)
    target = None
    for v in vanilla_data.get('versions', []):
        if v['id'] == inherits:
            target = v
            break
    if not target:
        return None, f'Minecraft {inherits} not found for Fabric server'
    vdata = fetch_json(target['url'])
    server_url = vdata.get('downloads', {}).get('server', {}).get('url')
    if not server_url:
        return None, 'No server download URL found'

    tmp = safe_join(SERVERS_DIR, f'_dl_{version.replace(".", "_")}')
    os.makedirs(tmp, exist_ok=True)

    try:
        jar_path = safe_join(tmp, jar_name)
        r = requests.get(server_url, timeout=120)
        r.raise_for_status()
        with open(jar_path, 'wb') as f:
            f.write(r.content)

        libs_dir = safe_join(tmp, 'libraries')
        os.makedirs(libs_dir, exist_ok=True)
        for lib in meta.get('libraries', []):
            try:
                if 'url' in lib and 'name' in lib:
                    lib_url = _maven_url(lib['url'], lib['name'])
                    if lib_url:
                        lr = requests.get(lib_url, timeout=30)
                        lr.raise_for_status()
                        lib_name = lib_url.split('/')[-1].replace('../', '').replace('..\\', '')
                        with open(safe_join(libs_dir, lib_name), 'wb') as lf:
                            lf.write(lr.content)
            except Exception:
                pass

        server_path = safe_path(SERVERS_DIR, server_name)
        if os.path.exists(server_path):
            shutil.rmtree(tmp)
            return None, f'Server "{os.path.basename(server_path)}" already exists'

        shutil.copytree(tmp, server_path)
        shutil.rmtree(tmp)

        eula_path = safe_join(server_path, 'eula.txt')
        if not os.path.isfile(eula_path):
            safe_write(eula_path, 'eula=true\n')

        from models import create_server
        server_id = create_server(name=server_name, path=server_path, jar_file=jar_name,
                                  java_args='-Xmx2G -Xms1G', server_type=server_type)
        return server_id, None

    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, 'Download failed'


def _latest_forge_version(mc_version):
    try:
        import xml.etree.ElementTree as ET
        r = requests.get('https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml', timeout=TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        candidates = [v.text for v in root.findall('.//version') if v.text and v.text.startswith(mc_version + '-')]
        if candidates:
            return sorted(candidates, key=lambda v: [int(x) if x.isdigit() else x for x in v.split('.')], reverse=True)[0]
    except Exception:
        pass
    return None


def _download_forge(version, server_name, server_type='forge'):
    full_ver = _latest_forge_version(version)
    if not full_ver:
        return None, f'No Forge build found for MC {version}'
    url = f'https://maven.minecraftforge.net/net/minecraftforge/forge/{full_ver}/forge-{full_ver}-server.jar'
    jar_name = f'forge-{full_ver}-server.jar'
    return _download_and_create_server(url, jar_name, version, server_name or f'Forge {version}', server_type)


def _download_neoforge(version, server_name, server_type='neoforge'):
    url = f'https://maven.neoforged.net/releases/net/neoforged/neoforge/{version}/neoforge-{version}-installer.jar'
    jar_name = f'neoforge-{version}-installer.jar'
    return _download_and_create_server(url, jar_name, version, server_name or f'NeoForge {version}', server_type)


def _download_and_create_server(jar_url, jar_name, version, server_name, server_type='vanilla'):
    tmp = safe_join(SERVERS_DIR, f'_dl_{version.replace(".", "_")}')
    os.makedirs(tmp, exist_ok=True)

    try:
        jar_path = safe_join(tmp, jar_name)
        r = requests.get(jar_url, stream=True, timeout=120)
        r.raise_for_status()
        with open(jar_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        server_path = safe_path(SERVERS_DIR, server_name)
        if os.path.exists(server_path):
            shutil.rmtree(tmp)
            return None, f'Server "{os.path.basename(server_path)}" already exists'

        shutil.copytree(tmp, server_path)
        shutil.rmtree(tmp)

        eula_path = safe_join(server_path, 'eula.txt')
        if not os.path.isfile(eula_path):
            safe_write(eula_path, 'eula=true\n')

        from models import create_server
        server_id = create_server(name=server_name, path=server_path, jar_file=jar_name,
                                  java_args='-Xmx2G -Xms1G', server_type=server_type)
        return server_id, None

    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, 'Download failed'
