import os, json, requests
from path_util import safe_join

MODRINTH_API, HANGAR_API = 'https://api.modrinth.com/v2', 'https://hangar.papermc.io/api/v1'
TIMEOUT = 30

SERVER_LOADER_MAP = {
    'paper': ['bukkit', 'paper', 'purpur', 'spigot'], 'purpur': ['bukkit', 'paper', 'purpur', 'spigot'],
    'folia': ['bukkit', 'paper', 'purpur', 'spigot'], 'fabric': ['fabric'],
    'quilt': ['quilt'], 'neoforge': ['neoforge'], 'forge': ['forge'], 'vanilla': None,
}
_HANGAR_PLATFORM = {k.upper(): k for k in ['bukkit', 'paper', 'purpur', 'spigot', 'fabric', 'quilt', 'neoforge', 'forge']}

def _modrinth_search(query, loaders=None, limit=24):
    params = {'query': query, 'limit': limit}
    if loaders: params['facets'] = json.dumps([[f'categories:{l}' for l in loaders]])
    d = requests.get(f'{MODRINTH_API}/search', params=params, timeout=TIMEOUT).json()
    return [{
        'provider': 'modrinth', 'id': h['project_id'], 'slug': h['slug'], 'name': h['title'],
        'description': (h.get('description') or '')[:200], 'downloads': h.get('downloads', 0),
        'icon_url': h.get('icon_url', ''), 'latest_version': h.get('latest_version', ''),
        'game_versions': (h.get('versions') or [])[-3:], 'loaders': h.get('loaders', []),
        'project_url': f"https://modrinth.com/plugin/{h['slug']}", 'author': h.get('author', ''),
    } for h in d.get('hits', [])] if isinstance(d, dict) else []

def _modrinth_versions(project_id):
    d = requests.get(f'{MODRINTH_API}/project/{project_id}/version', timeout=TIMEOUT).json()
    return d if isinstance(d, list) else []

def _hangar_search(query, loaders=None, limit=24):
    try:
        d = requests.get(f'{HANGAR_API}/projects', params={'q': query, 'limit': limit}, timeout=TIMEOUT).json()
        if not isinstance(d, dict): return []
        results = []
        for h in d.get('result', []):
            ns = h.get('namespace', {})
            pf = h.get('supportedPlatforms', {}) or {}
            if loaders:
                exp = {_HANGAR_PLATFORM.get(l) for l in loaders if l in _HANGAR_PLATFORM}
                if not exp & set(pf.keys()): continue
            av = sorted({v for vl in pf.values() if isinstance(vl, list) for v in vl},
                       key=lambda v: [int(x) if x.isdigit() else x for x in v.split('.')], reverse=True)
            st = h.get('stats', {}) or {}
            sl = ns.get('slug', '') or h.get('name', '')
            results.append({
                'provider': 'hangar', 'id': str(h.get('id', sl)), 'slug': sl, 'name': h.get('name', ''),
                'description': (h.get('description') or '')[:200], 'downloads': st.get('downloads', 0),
                'icon_url': h.get('avatarUrl', ''), 'latest_version': av[-1] if av else '',
                'game_versions': av[-3:], 'loaders': [p.lower() for p in pf.keys()],
                'project_url': f'https://hangar.papermc.io/{ns.get("owner", "")}/{sl}',
                'author': ns.get('owner', ''),
            })
        return results
    except Exception: return []

def search_plugins(query, provider=None, server_type=None):
    loaders = SERVER_LOADER_MAP.get(server_type) if server_type else None
    if loaders is None and server_type: return []
    results = []
    if provider in (None, 'modrinth'):
        try: results.extend(_modrinth_search(query, loaders=loaders))
        except Exception: pass
    if provider in (None, 'hangar'):
        try: results.extend(_hangar_search(query, loaders=loaders))
        except Exception: pass
    results.sort(key=lambda p: p['downloads'], reverse=True)
    return results

def get_versions(provider, project_id):
    if provider == 'modrinth':
        try: return _modrinth_versions(project_id)
        except Exception: return []
    return []

def install_plugin(server_id, provider, project_id, version_id=None, version_number=None):
    from models import get_server
    server = get_server(server_id)
    if not server: return False, 'Server not found'

    plugins_dir = safe_join(server['path'], 'plugins')
    os.makedirs(plugins_dir, exist_ok=True)

    if provider == 'modrinth':
        versions = _modrinth_versions(project_id)
        if not versions: return False, 'No versions found for this project'

        v = None
        if version_id: v = next((x for x in versions if x['id'] == version_id), None)
        elif version_number: v = next((x for x in versions if x.get('version_number') == version_number), None)
        else: v = versions[0]
        if not v: return False, 'Specified version not found'

        files = v.get('files', [])
        if not files: return False, 'No downloadable files in this version'

        p = next((f for f in files if f.get('primary')), files[0])
        fn = p['filename'].replace('../', '').replace('..\\', '')

        try:
            r = requests.get(p['url'], stream=True, timeout=180)
            r.raise_for_status()
            with open(safe_join(plugins_dir, fn), 'wb') as f:
                for c in r.iter_content(8192): f.write(c)
            return True, f'Installed {fn}'
        except Exception: return False, 'Download failed'

    elif provider == 'hangar':
        return False, 'Hangar downloads require authentication. Visit the project page to download manually.'
    return False, 'Unknown provider'

def list_installed(server_id):
    from models import get_server
    server = get_server(server_id)
    if not server: return []
    pd = os.path.join(server['path'], 'plugins')
    if not os.path.isdir(pd): return []
    return sorted([{'filename': f, 'size': os.path.getsize(os.path.join(pd, f)),
                    'modified': int(os.path.getmtime(os.path.join(pd, f)))}
                   for f in os.listdir(pd) if f.endswith('.jar') and os.path.isfile(os.path.join(pd, f))],
                  key=lambda p: p['filename'])

def delete_plugin(server_id, filename):
    from models import get_server
    server = get_server(server_id)
    if not server: return False, 'Server not found'
    try:
        fp = safe_join(server['path'], 'plugins', filename)
    except ValueError:
        return False, 'Access denied'
    if not os.path.isfile(fp): return False, 'File not found'
    os.remove(fp)
    return True, f'Deleted {filename}'
