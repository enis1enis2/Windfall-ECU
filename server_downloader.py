import requests, os, json, re, xml.etree.ElementTree as ET
from config import SERVERS_DIR
from path_util import safe_join, safe_path, safe_write

PAPER_API, FOLIA_API = 'https://api.papermc.io/v2/projects/paper', 'https://api.papermc.io/v2/projects/folia'
PURPUR_API = 'https://api.purpurmc.org/v2/purpur'
VANILLA_MANIFEST = 'https://launchermeta.mojang.com/mc/game/version_manifest_v2.json'
FORGE_PROMOS = 'https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json'
NEOFORGE_MAVEN = 'https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml'
FABRIC_META, QUILT_META = 'https://meta.fabricmc.net/v2/versions', 'https://meta.quiltmc.org/v3/versions'
TIMEOUT = 30

SERVER_TYPES = {k: {'name': v, 'api': k} for k, v in
    {'paper': 'Paper', 'folia': 'Folia', 'purpur': 'Purpur', 'vanilla': 'Vanilla',
     'fabric': 'Fabric', 'quilt': 'Quilt', 'forge': 'Forge', 'neoforge': 'NeoForge'}.items()}

_PAPER_UNLISTED = {'26.1.2': {64: '830d4eb5c15cbd802a9ec9f2f54eaaaeb9511958339aec983fd0c88bad21d940'}}
_FOLIA_UNLISTED = {'26.1.2': {8: '607afd1c3320008e1ffd2eaee6780ace4419d5f8c527b75e79f259be79ebf57b'}}

def get_types():
    return [{'id': k, 'name': v['name']} for k, v in SERVER_TYPES.items()]

def fetch_json(url):
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def _sort_versions(versions):
    return sorted(versions, key=lambda v: [int(x) if x.isdigit() else x for x in re.split(r'[.\-]', v)], reverse=True)

def get_versions(server_type):
    if server_type == 'paper':
        v = (fetch_json(PAPER_API) or {}).get('versions', [])[::-1]
        if v and '26.1.2' not in v: v.insert(0, '26.1.2')
        return v
    if server_type == 'folia':
        v = (fetch_json(FOLIA_API) or {}).get('versions', [])[::-1]
        if v and '26.1.2' not in v: v.insert(0, '26.1.2')
        return v
    if server_type == 'purpur':
        d = fetch_json(PURPUR_API)
        if isinstance(d.get('versions'), list): return _sort_versions(d['versions'])
        if isinstance(d.get('versions'), dict): return _sort_versions(d['versions'].keys())
        return []
    if server_type == 'vanilla':
        return [v['id'] for v in (fetch_json(VANILLA_MANIFEST) or {}).get('versions', []) if v.get('type') == 'release']
    if server_type == 'fabric':
        d = fetch_json(f'{FABRIC_META}/game')
        return _sort_versions([v['version'] for v in d if isinstance(v, dict) and v.get('stable')]) if isinstance(d, list) else []
    if server_type == 'quilt':
        d = fetch_json(f'{QUILT_META}/game')
        return _sort_versions([v['version'] for v in d]) if isinstance(d, list) else []
    if server_type == 'forge':
        try:
            p = (fetch_json(FORGE_PROMOS) or {}).get('promos', {})
            return _sort_versions({k.split('-')[0] for k in p if k.split('-')[0]})
        except Exception: return ['latest']
    if server_type == 'neoforge':
        try:
            r = requests.get(NEOFORGE_MAVEN, timeout=TIMEOUT)
            r.raise_for_status()
            v = [v.text for v in ET.fromstring(r.content).findall('.//version') if v.text]
            return _sort_versions(v) if v else ['latest']
        except Exception: return ['latest']
    return []

def get_builds(server_type, version):
    if server_type == 'paper':
        ul, api = _PAPER_UNLISTED, PAPER_API
    elif server_type == 'folia':
        ul, api = _FOLIA_UNLISTED, FOLIA_API
    elif server_type == 'purpur':
        d = fetch_json(f'{PURPUR_API}/{version}')
        return [{'build': b} for b in (d.get('builds', {}).get('all', []) if isinstance(d, dict) else [])]
    else:
        return []
    if version in ul: return [{'build': b, 'channel': 'default'} for b in ul[version]]
    d = fetch_json(f'{api}/versions/{version}/builds')
    bs = [b for b in (d.get('builds') or []) if isinstance(b, dict) and b.get('channel') == 'default'] or d.get('builds', [])
    return [{'build': b['build'], 'channel': b.get('channel', 'unknown')} for b in bs]

def download_server(server_type, version, build=None, server_name=None):
    dispatch = {'paper': _download_paper, 'folia': _download_paper, 'purpur': _download_purpur,
                'vanilla': _download_vanilla, 'fabric': _download_fabric, 'quilt': _download_quilt,
                'forge': _download_forge, 'neoforge': _download_neoforge}
    fn = dispatch.get(server_type)
    if not fn: return None, 'Unknown server type'
    return fn(server_type if fn == _download_paper else None, version, build, server_name, server_type)

def _paper_download_url(project, version, build, jar_name):
    ul = _PAPER_UNLISTED if project == 'paper' else _FOLIA_UNLISTED
    if version in ul and build in ul[version]:
        return f'https://fill-data.papermc.io/v1/objects/{ul[version][build]}/{jar_name}'
    try:
        d = fetch_json(f'https://api.papermc.io/v2/projects/{project}/versions/{version}/builds/{build}')
        sha = d.get('downloads', {}).get('application', {}).get('sha256')
        if sha: return f'https://fill-data.papermc.io/v1/objects/{sha}/{jar_name}'
    except Exception: pass
    return f'https://api.papermc.io/v2/projects/{project}/versions/{version}/builds/{build}/downloads/{jar_name}'

def _download_paper(_project, version, build, server_name, server_type='paper'):
    project = _project or server_type
    ul = _PAPER_UNLISTED if project == 'paper' else _FOLIA_UNLISTED
    if build is None:
        if version in ul:
            build = max(ul[version].keys())
        else:
            d = fetch_json(f'https://api.papermc.io/v2/projects/{project}/versions/{version}/builds')
            bs = [b for b in (d.get('builds') or []) if isinstance(b, dict) and b.get('channel') == 'default'] or d.get('builds', [])
            if not bs: return None, 'No builds found'
            build = bs[-1]['build']
    jar_name = f'{project}-{version}-{build}.jar'
    return _create_server(_paper_download_url(project, version, build, jar_name), jar_name, version,
                          server_name or f'{project.title()} {version}', server_type)

def _download_purpur(_, version, build, server_name, server_type='purpur'):
    if build is None:
        d = fetch_json(f'{PURPUR_API}/{version}')
        b = d.get('builds', {}).get('all', []) if isinstance(d, dict) else []
        if not b: return None, 'No builds found'
        build = b[-1]
    return _create_server(f'{PURPUR_API}/{version}/{build}/download', f'purpur-{version}-{build}.jar',
                          version, server_name or f'Purpur {version}', server_type)

def _download_vanilla(*_, version, server_name, server_type='vanilla'):
    d = fetch_json(VANILLA_MANIFEST)
    tv = next((v for v in d.get('versions', []) if v['id'] == version), None)
    if not tv: return None, f'Version {version} not found'
    url = fetch_json(tv['url']).get('downloads', {}).get('server', {}).get('url')
    if not url: return None, 'No server download URL found'
    return _create_server(url, 'server.jar', version, server_name or f'Vanilla {version}', server_type)

def _get_loader(meta_url):
    d = fetch_json(meta_url)
    if not isinstance(d, list) or not d: return None
    e = next((l for l in d if l.get('stable')), d[0])
    return e.get('loader', e).get('version') if isinstance(e.get('loader'), dict) else e.get('version')

def _download_fabric(*_, version, server_name, server_type='fabric'):
    lv = _get_loader(f'{FABRIC_META}/loader')
    if not lv: return None, 'Could not find Fabric loader version'
    return _download_modded(f'{FABRIC_META}/loader/{version}/{lv}/server/json',
                           f'fabric-server-mc.{version}-loader.{lv}.jar', version,
                           server_name or f'Fabric {version}', server_type)

def _download_quilt(*_, version, server_name, server_type='quilt'):
    lv = _get_loader(f'{QUILT_META}/loader')
    if not lv: return None, 'Could not find Quilt loader version'
    return _download_modded(f'{QUILT_META}/loader/{version}/{lv}/server/json',
                           f'quilt-server-mc.{version}-loader.{lv}.jar', version,
                           server_name or f'Quilt {version}', server_type)

def _maven_url(base, coord):
    p = coord.split(':')
    if len(p) >= 3: return f'{base.rstrip("/")}/{p[0].replace(".", "/")}/{p[1]}/{p[2]}/{p[1]}-{p[2]}.jar'

def _download_modded(meta_url, jar_name, version, server_name, server_type):
    meta = fetch_json(meta_url)
    if not isinstance(meta, dict): return None, 'Invalid meta response'

    iv = meta.get('inheritsFrom', version)

    d = fetch_json(VANILLA_MANIFEST)
    tv = next((v for v in d.get('versions', []) if v['id'] == iv), None)
    if not tv: return None, f'Minecraft {iv} not found for server'
    surl = fetch_json(tv['url']).get('downloads', {}).get('server', {}).get('url')
    if not surl: return None, 'No server download URL found'

    tmp = safe_join(SERVERS_DIR, f'_dl_{version.replace(".", "_")}')
    os.makedirs(tmp, exist_ok=True)

    try:
        jar_path = safe_join(tmp, jar_name)
        r = requests.get(surl, timeout=120)
        r.raise_for_status()
        with open(jar_path, 'wb') as f: f.write(r.content)

        libs = safe_join(tmp, 'libraries')
        os.makedirs(libs, exist_ok=True)
        for lib in meta.get('libraries', []):
            try:
                if 'url' in lib and 'name' in lib:
                    lurl = _maven_url(lib['url'], lib['name'])
                    if lurl:
                        lr = requests.get(lurl, timeout=30)
                        lr.raise_for_status()
                        with open(safe_join(libs, lurl.split('/')[-1].replace('../', '').replace('..\\', '')), 'wb') as lf:
                            lf.write(lr.content)
            except Exception: pass

        return _finalize(tmp, jar_name, version, server_name, server_type)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, 'Download failed'

def _download_forge(*_, version, server_name, server_type='forge'):
    try:
        r = requests.get('https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml', timeout=TIMEOUT)
        r.raise_for_status()
        c = [v.text for v in ET.fromstring(r.content).findall('.//version') if v.text and v.text.startswith(version + '-')]
        fv = _sort_versions(c)[0] if c else None
    except Exception: fv = None
    if not fv: return None, f'No Forge build found for MC {version}'
    return _create_server(f'https://maven.minecraftforge.net/net/minecraftforge/forge/{fv}/forge-{fv}-server.jar',
                         f'forge-{fv}-server.jar', version, server_name or f'Forge {version}', server_type)

def _download_neoforge(*_, version, server_name, server_type='neoforge'):
    return _create_server(f'https://maven.neoforged.net/releases/net/neoforged/neoforge/{version}/neoforge-{version}-installer.jar',
                         f'neoforge-{version}-installer.jar', version, server_name or f'NeoForge {version}', server_type)

def _create_server(jar_url, jar_name, version, server_name, server_type='vanilla'):
    tmp = safe_join(SERVERS_DIR, f'_dl_{version.replace(".", "_")}')
    os.makedirs(tmp, exist_ok=True)
    try:
        jp = safe_join(tmp, jar_name)
        r = requests.get(jar_url, stream=True, timeout=120)
        r.raise_for_status()
        with open(jp, 'wb') as f:
            for c in r.iter_content(8192): f.write(c)
        return _finalize(tmp, jar_name, version, server_name, server_type)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, 'Download failed'

def _finalize(tmp, jar_name, version, server_name, server_type):
    sp = safe_path(SERVERS_DIR, server_name)
    if os.path.exists(sp):
        shutil.rmtree(tmp)
        return None, f'Server "{os.path.basename(sp)}" already exists'
    shutil.copytree(tmp, sp)
    shutil.rmtree(tmp)
    eula = safe_join(sp, 'eula.txt')
    if not os.path.isfile(eula): safe_write(eula, 'eula=true\n')
    from models import create_server
    return create_server(name=server_name, path=sp, jar_file=jar_name,
                         java_args='-Xmx2G -Xms1G', server_type=server_type), None
