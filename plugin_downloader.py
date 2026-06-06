import os, json, requests, re
from path_util import safe_join

MODRINTH_API = 'https://api.modrinth.com/v2'
TIMEOUT = 30

SERVER_LOADER_MAP = {
    'paper': ['bukkit', 'paper', 'purpur', 'spigot'], 'purpur': ['bukkit', 'paper', 'purpur', 'spigot'],
    'folia': ['bukkit', 'paper', 'purpur', 'spigot'], 'fabric': ['fabric'],
    'quilt': ['quilt'], 'neoforge': ['neoforge'], 'forge': ['forge'], 'vanilla': None,
}

def _filter_versions_by_loader(versions, allowed_loaders):
    if not allowed_loaders:
        return versions
    return [v for v in versions if any(l in v.get('loaders', []) for l in allowed_loaders)]

def _modrinth_search(query, loaders=None, game_version=None, limit=24):
    params = {'query': query, 'limit': limit}
    facets = []
    if loaders:
        facets.append([f'categories:{l}' for l in loaders])
    if game_version:
        facets.append([f'versions:{game_version}'])
    if facets:
        params['facets'] = json.dumps(facets)
    d = requests.get(f'{MODRINTH_API}/search', params=params, timeout=TIMEOUT).json()
    return [{
        'provider': 'modrinth', 'id': h['project_id'], 'slug': h['slug'], 'name': h['title'],
        'description': (h.get('description') or '')[:200], 'downloads': h.get('downloads', 0),
        'icon_url': h.get('icon_url', ''), 'latest_version': h.get('latest_version', ''),
        'game_versions': (h.get('versions') or [])[-3:], 'loaders': h.get('loaders', []),
        'project_url': f"https://modrinth.com/plugin/{h['slug']}", 'author': h.get('author', ''),
    } for h in d.get('hits', [])] if isinstance(d, dict) else []

def search_plugins(query, provider=None, server_type=None, game_version=None):
    loaders = SERVER_LOADER_MAP.get(server_type) if server_type else None
    if loaders is None and server_type:
        return []
    results = []
    if provider in (None, 'modrinth'):
        try:
            results.extend(_modrinth_search(query, loaders=loaders, game_version=game_version))
        except Exception:
            pass
    results.sort(key=lambda p: p['downloads'], reverse=True)
    return results

def _modrinth_versions(project_id):
    d = requests.get(f'{MODRINTH_API}/project/{project_id}/version', timeout=TIMEOUT).json()
    return d if isinstance(d, list) else []

def get_versions(provider, project_id):
    if provider == 'modrinth':
        try:
            return _modrinth_versions(project_id)
        except Exception:
            return []
    return []

# --- Plugin metadata for tracking installed plugins ---

def _meta_path(server_id):
    from models import get_server
    s = get_server(server_id)
    if not s:
        return None
    return safe_join(s['path'], '.plugin_meta.json')

def _read_meta(server_id):
    mp = _meta_path(server_id)
    if not mp or not os.path.isfile(mp):
        return {}
    try:
        with open(mp) as f:
            return json.load(f)
    except Exception:
        return {}

def _write_meta(server_id, meta):
    mp = _meta_path(server_id)
    if not mp:
        return
    with open(mp, 'w') as f:
        json.dump(meta, f, indent=2)

def install_plugin(server_id, provider, project_id, version_id=None, version_number=None, game_version=None):
    from models import get_server
    server = get_server(server_id)
    if not server:
        return False, 'Server not found'

    plugins_dir = safe_join(server['path'], 'plugins')
    os.makedirs(plugins_dir, exist_ok=True)

    if provider == 'modrinth':
        versions = _modrinth_versions(project_id)
        if not versions:
            return False, 'No versions found'

        allowed = SERVER_LOADER_MAP.get(server.get('server_type', ''))
        compatible = _filter_versions_by_loader(versions, allowed)
        if not compatible and allowed:
            compatible = versions

        v = None
        if version_id:
            v = next((x for x in (compatible or versions) if x['id'] == version_id), None)
        elif version_number:
            v = next((x for x in (compatible or versions) if x.get('version_number') == version_number), None)
        if not v:
            if game_version:
                v = next((x for x in (compatible or versions) if game_version in x.get('game_versions', [])), None)
            if not v and compatible:
                v = compatible[0]
            if not v:
                v = versions[0]
        if not v:
            return False, 'No suitable version found'

        files = v.get('files', [])
        if not files:
            return False, 'No downloadable files'

        pf = next((f for f in files if f.get('primary')), files[0])
        fn = pf['filename'].replace('../', '').replace('..\\', '')

        try:
            r = requests.get(pf['url'], stream=True, timeout=180)
            r.raise_for_status()
            fp = safe_join(plugins_dir, fn)
            with open(fp, 'wb') as f:
                for c in r.iter_content(8192):
                    f.write(c)

            meta = _read_meta(server_id)
            meta[project_id] = {
                'filename': fn,
                'project_id': project_id,
                'version_id': v['id'],
                'version_number': v.get('version_number', ''),
                'name': v.get('name', ''),
                'game_versions': v.get('game_versions', []),
                'loaders': v.get('loaders', []),
                'installed_at': int(__import__('time').time()),
            }
            _write_meta(server_id, meta)
            return True, f'Installed {fn}'
        except Exception:
            return False, 'Download failed'

    elif provider == 'hangar':
        return False, 'Hangar downloads require manual install. Visit the project page.'
    return False, 'Unknown provider'

def _filename_to_search_term(filename):
    name = filename.replace('.jar', '').replace('.JAR', '')
    name = re.sub(r'[-_](?:\d+\.\d+[\d.]*|mc\d+[\d.]*|v\d[\d.]*|universal|fabric|forge|neoforge|paper|spigot|bukkit|quilt)(?:[-_].*)?$', '', name, flags=re.I)
    name = re.sub(r'^\[.*?\]\s*', '', name)
    name = name.strip('-_ ')
    return name if len(name) >= 2 else ''

def _auto_recognize(server_id):
    from models import get_server
    server = get_server(server_id)
    if not server:
        return
    pd = safe_join(server['path'], 'plugins')
    if not os.path.isdir(pd):
        return
    meta = _read_meta(server_id)
    changed = False
    for f in sorted(os.listdir(pd)):
        if not f.endswith('.jar'):
            continue
        fp = safe_join(pd, f)
        if not os.path.isfile(fp):
            continue
        already = any(info.get('filename') == f for info in meta.values())
        if already:
            continue
        term = _filename_to_search_term(f)
        if not term:
            continue
        try:
            results = _modrinth_search(term, limit=5)
            t_clean = term.lower().replace(' ', '').replace('-', '').replace('_', '')
            for r in results:
                if r['id'] in meta:
                    continue
                r_clean = r['name'].lower().replace(' ', '').replace('-', '').replace('_', '')
                if t_clean in r_clean or r_clean in t_clean:
                    meta[r['id']] = {
                        'filename': f, 'project_id': r['id'],
                        'version_number': '', 'version_id': '',
                        'name': r['name'], 'game_versions': r.get('game_versions', []),
                        'loaders': r.get('loaders', []),
                        'installed_at': int(__import__('time').time()),
                    }
                    changed = True
                    break
        except Exception:
            pass
    if changed:
        _write_meta(server_id, meta)

def check_updates(server_id):
    _auto_recognize(server_id)
    meta = _read_meta(server_id)
    if not meta:
        return []
    updates = []
    changed = False
    for pid, info in meta.items():
        try:
            versions = _modrinth_versions(pid)
            if not versions:
                continue
            latest = versions[0]
            lv = latest.get('version_number', '')
            cv = info.get('version_number', '')
            if not cv:
                for v in versions:
                    for f in v.get('files', []):
                        if f.get('filename', '') == info.get('filename', ''):
                            cv = v.get('version_number', '')
                            info['version_number'] = cv
                            info['version_id'] = v['id']
                            changed = True
                            break
                    if cv:
                        break
            if not cv or lv != cv:
                updates.append({
                    'project_id': pid,
                    'current_version': cv or '?',
                    'latest_version': lv,
                    'latest_version_id': latest['id'],
                    'filename': info.get('filename', ''),
                    'game_versions': latest.get('game_versions', []),
                })
        except Exception:
            pass
    if changed:
        _write_meta(server_id, meta)
    return updates

def update_plugin(server_id, project_id, version_id=None):
    from models import get_server
    server = get_server(server_id)
    if not server:
        return False, 'Server not found'
    meta = _read_meta(server_id)
    if project_id not in meta:
        return False, 'Plugin not tracked'
    info = meta[project_id]
    old_fn = info['filename']
    plugins_dir = safe_join(server['path'], 'plugins')
    versions = _modrinth_versions(project_id)
    if not versions:
        return False, 'No versions found'

    allowed = SERVER_LOADER_MAP.get(server.get('server_type', ''))
    compatible = _filter_versions_by_loader(versions, allowed)

    v = None
    if version_id:
        v = next((x for x in (compatible or versions) if x['id'] == version_id), None)
    if not v and compatible:
        v = compatible[0]
    if not v:
        v = versions[0]
    if not v:
        return False, 'No version found'
    files = v.get('files', [])
    if not files:
        return False, 'No downloadable files'
    pf = next((f for f in files if f.get('primary')), files[0])
    new_fn = pf['filename'].replace('../', '').replace('..\\', '')
    try:
        r = requests.get(pf['url'], stream=True, timeout=180)
        r.raise_for_status()
        new_fp = safe_join(plugins_dir, new_fn)
        with open(new_fp, 'wb') as f:
            for c in r.iter_content(8192):
                f.write(c)
        if old_fn != new_fn:
            old_fp = safe_join(plugins_dir, old_fn)
            if os.path.isfile(old_fp):
                os.remove(old_fp)
        meta[project_id] = {
            'filename': new_fn,
            'project_id': project_id,
            'version_id': v['id'],
            'version_number': v.get('version_number', ''),
            'name': v.get('name', ''),
            'game_versions': v.get('game_versions', []),
            'loaders': v.get('loaders', []),
            'installed_at': int(__import__('time').time()),
        }
        _write_meta(server_id, meta)
        return True, f'Updated to {new_fn}'
    except Exception:
        return False, 'Update failed'

def check_mismatched_plugins(server_id):
    from models import get_server
    _auto_recognize(server_id)
    server = get_server(server_id)
    if not server:
        return []
    allowed = SERVER_LOADER_MAP.get(server.get('server_type', ''))
    if not allowed:
        return []
    meta = _read_meta(server_id)
    mismatched = []
    for pid, info in meta.items():
        try:
            installed_loaders = info.get('loaders', [])
            if installed_loaders and any(l in allowed for l in installed_loaders):
                continue
            versions = _modrinth_versions(pid)
            compatible = _filter_versions_by_loader(versions, allowed)
            if not compatible:
                mismatched.append({
                    'project_id': pid, 'filename': info.get('filename', ''),
                    'name': info.get('name', ''), 'reason': 'No version supports this server type',
                    'fix_version': '', 'fix_version_id': '',
                })
                continue
            best = compatible[0]
            mismatched.append({
                'project_id': pid, 'filename': info.get('filename', ''),
                'name': info.get('name', ''),
                'reason': f'Wrong loader: needs {"/".join(allowed)}',
                'fix_version': best.get('version_number', ''),
                'fix_version_id': best['id'],
            })
        except Exception:
            pass
    return mismatched

def fix_plugin(server_id, project_id):
    from models import get_server
    _auto_recognize(server_id)
    server = get_server(server_id)
    if not server:
        return False, 'Server not found'
    allowed = SERVER_LOADER_MAP.get(server.get('server_type', ''))
    if not allowed:
        return False, 'No loader restriction for this server type'
    meta = _read_meta(server_id)
    if project_id not in meta:
        return False, 'Plugin not tracked'
    info = meta[project_id]
    old_fn = info['filename']
    plugins_dir = safe_join(server['path'], 'plugins')
    versions = _modrinth_versions(project_id)
    if not versions:
        return False, 'No versions found'
    compatible = _filter_versions_by_loader(versions, allowed)
    if not compatible:
        return False, 'No compatible version for this server type'
    v = compatible[0]
    files = v.get('files', [])
    if not files:
        return False, 'No downloadable files'
    pf = next((f for f in files if f.get('primary')), files[0])
    new_fn = pf['filename'].replace('../', '').replace('..\\', '')
    try:
        r = requests.get(pf['url'], stream=True, timeout=180)
        r.raise_for_status()
        new_fp = safe_join(plugins_dir, new_fn)
        with open(new_fp, 'wb') as f:
            for c in r.iter_content(8192):
                f.write(c)
        if old_fn != new_fn:
            old_fp = safe_join(plugins_dir, old_fn)
            if os.path.isfile(old_fp):
                os.remove(old_fp)
        meta[project_id] = {
            'filename': new_fn, 'project_id': project_id,
            'version_id': v['id'], 'version_number': v.get('version_number', ''),
            'name': v.get('name', ''),
            'game_versions': v.get('game_versions', []),
            'loaders': v.get('loaders', []),
            'installed_at': int(__import__('time').time()),
        }
        _write_meta(server_id, meta)
        return True, f'Fixed: replaced with {new_fn}'
    except Exception:
        return False, 'Fix failed'

def list_installed(server_id):
    from models import get_server
    server = get_server(server_id)
    if not server:
        return []
    pd = safe_join(server['path'], 'plugins')
    if not os.path.isdir(pd):
        return []
    _auto_recognize(server_id)
    meta = _read_meta(server_id)
    plugins = []
    for f in sorted(os.listdir(pd)):
        if not f.endswith('.jar') or not os.path.isfile(safe_join(pd, f)):
            continue
        size = os.path.getsize(safe_join(pd, f))
        modified = int(os.path.getmtime(safe_join(pd, f)))
        tracked = None
        for pid, info in meta.items():
            if info.get('filename') == f:
                tracked = pid
                break
        plugins.append({
            'filename': f, 'size': size, 'modified': modified,
            'tracked': bool(tracked), 'project_id': tracked,
        })
    return plugins

def delete_plugin(server_id, filename):
    from models import get_server
    server = get_server(server_id)
    if not server:
        return False, 'Server not found'
    try:
        fp = safe_join(server['path'], 'plugins', filename)
    except ValueError:
        return False, 'Access denied'
    if not os.path.isfile(fp):
        return False, 'File not found'
    os.remove(fp)
    meta = _read_meta(server_id)
    for pid, info in list(meta.items()):
        if info.get('filename') == filename:
            del meta[pid]
            _write_meta(server_id, meta)
            break
    return True, f'Deleted {filename}'
