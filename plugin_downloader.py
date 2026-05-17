import os
import json
import requests

MODRINTH_API = 'https://api.modrinth.com/v2'
HANGAR_API = 'https://hangar.papermc.io/api/v1'
TIMEOUT = 30


SERVER_LOADER_MAP = {
    'paper':    ['bukkit', 'paper', 'purpur', 'spigot'],
    'purpur':   ['bukkit', 'paper', 'purpur', 'spigot'],
    'folia':    ['bukkit', 'paper', 'purpur', 'spigot'],
    'fabric':   ['fabric'],
    'quilt':    ['quilt'],
    'neoforge': ['neoforge'],
    'forge':    ['forge'],
    'vanilla':  None,
}


def _modrinth_search(query, loaders=None, limit=24):
    params = {
        'query': query,
        'limit': limit,
    }
    if loaders:
        params['facets'] = json.dumps([[f'categories:{l}' for l in loaders]])
    r = requests.get(f'{MODRINTH_API}/search', params=params, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        return []
    results = []
    for hit in data.get('hits', []):
        results.append({
            'provider': 'modrinth',
            'id': hit['project_id'],
            'slug': hit['slug'],
            'name': hit['title'],
            'description': (hit.get('description') or '')[:200],
            'downloads': hit.get('downloads', 0),
            'icon_url': hit.get('icon_url', ''),
            'latest_version': hit.get('latest_version', ''),
            'game_versions': hit.get('versions', [])[-3:] if hit.get('versions') else [],
            'loaders': hit.get('loaders', []),
            'project_url': f'https://modrinth.com/plugin/{hit["slug"]}',
            'author': hit.get('author', ''),
        })
    return results


def _modrinth_versions(project_id):
    r = requests.get(f'{MODRINTH_API}/project/{project_id}/version', timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def _modrinth_version(project_id, version_id):
    r = requests.get(f'{MODRINTH_API}/project/{project_id}/version/{version_id}', timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


_HANGAR_PLATFORM_MAP = {
    'bukkit': 'BUKKIT',
    'paper': 'PAPER',
    'purpur': 'PURPUR',
    'spigot': 'SPIGOT',
    'fabric': 'FABRIC',
    'quilt': 'QUILT',
    'neoforge': 'NEOFORGE',
    'forge': 'FORGE',
}


def _hangar_search(query, loaders=None, limit=24):
    try:
        params = {'q': query, 'limit': limit}
        r = requests.get(f'{HANGAR_API}/projects', params=params, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            return []
        results = []
        for hit in data.get('result', []):
            ns = hit.get('namespace', {})
            platforms = hit.get('supportedPlatforms', {})
            if not isinstance(platforms, dict):
                platforms = {}
            if loaders:
                expected = {_HANGAR_PLATFORM_MAP.get(l) for l in loaders if l in _HANGAR_PLATFORM_MAP}
                if not expected & set(platforms.keys()):
                    continue
            all_versions = set()
            for ver_list in platforms.values():
                if isinstance(ver_list, list):
                    all_versions.update(ver_list)
            sorted_versions = sorted(all_versions, key=lambda v: [int(x) if x.isdigit() else x for x in v.split('.')], reverse=True)

            stats = hit.get('stats', {}) or {}
            slug_val = ns.get('slug', '') or hit.get('name', '')
            results.append({
                'provider': 'hangar',
                'id': str(hit.get('id', slug_val)),
                'slug': slug_val,
                'name': hit.get('name', ''),
                'description': (hit.get('description') or '')[:200],
                'downloads': stats.get('downloads', 0),
                'icon_url': hit.get('avatarUrl', ''),
                'latest_version': sorted_versions[-1] if sorted_versions else '',
                'game_versions': sorted_versions[-3:],
                'loaders': [p.lower() for p in platforms.keys()],
                'project_url': f'https://hangar.papermc.io/{ns.get("owner", "")}/{slug_val}',
                'author': ns.get('owner', ''),
            })
        return results
    except Exception:
        return []


def search_plugins(query, provider=None, server_type=None):
    loaders = SERVER_LOADER_MAP.get(server_type) if server_type else None
    if loaders is None and server_type:
        return []
    results = []
    if provider in (None, 'modrinth'):
        try:
            results.extend(_modrinth_search(query, loaders=loaders))
        except Exception:
            pass
    if provider in (None, 'hangar'):
        try:
            results.extend(_hangar_search(query, loaders=loaders))
        except Exception:
            pass
    results.sort(key=lambda p: p['downloads'], reverse=True)
    return results


def get_versions(provider, project_id):
    if provider == 'modrinth':
        try:
            return _modrinth_versions(project_id)
        except Exception as e:
            return []
    return []


def install_plugin(server_id, provider, project_id, version_id=None, version_number=None):
    from models import get_server
    server = get_server(server_id)
    if not server:
        return False, 'Server not found'

    plugins_dir = os.path.join(server['path'], 'plugins')
    os.makedirs(plugins_dir, exist_ok=True)

    if provider == 'modrinth':
        versions = _modrinth_versions(project_id)
        if not versions:
            return False, 'No versions found for this project'

        version = None
        if version_id:
            version = next((v for v in versions if v['id'] == version_id), None)
        elif version_number:
            version = next((v for v in versions if v.get('version_number') == version_number), None)
        else:
            version = versions[0]

        if not version:
            return False, 'Specified version not found'

        files = version.get('files', [])
        if not files:
            return False, 'No downloadable files in this version'

        primary = next((f for f in files if f.get('primary')), files[0])
        url = primary['url']
        filename = primary['filename']

        dest = os.path.join(plugins_dir, filename)
        try:
            r = requests.get(url, stream=True, timeout=180)
            r.raise_for_status()
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True, f'Installed {filename}'
        except Exception as e:
            return False, f'Download failed: {e}'

    elif provider == 'hangar':
        return False, 'Hangar downloads require authentication. Visit the project page to download manually.'

    return False, 'Unknown provider'


def list_installed(server_id):
    from models import get_server
    server = get_server(server_id)
    if not server:
        return []

    plugins_dir = os.path.join(server['path'], 'plugins')
    if not os.path.isdir(plugins_dir):
        return []

    plugins = []
    for f in os.listdir(plugins_dir):
        fpath = os.path.join(plugins_dir, f)
        if f.endswith('.jar') and os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            plugins.append({
                'filename': f,
                'size': size,
                'modified': int(os.path.getmtime(fpath)),
            })
    return sorted(plugins, key=lambda p: p['filename'])


def delete_plugin(server_id, filename):
    from models import get_server
    server = get_server(server_id)
    if not server:
        return False, 'Server not found'

    fpath = os.path.join(server['path'], 'plugins', filename)
    fpath = os.path.normpath(fpath)
    if not fpath.startswith(os.path.normpath(os.path.join(server['path'], 'plugins'))):
        return False, 'Access denied'
    if not os.path.isfile(fpath):
        return False, 'File not found'

    os.remove(fpath)
    return True, f'Deleted {filename}'
