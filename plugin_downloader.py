import os, json, requests, re, time as _time, logging
from urllib.parse import quote
from path_util import safe_join

MODRINTH_API = 'https://api.modrinth.com/v2'
SPIGET_API = 'https://api.spiget.org/v2'
HANGAR_API = 'https://hangar.papermc.io/api/v1'

TIMEOUT_SEARCH = 15
TIMEOUT_VERSIONS = 20
TIMEOUT_DOWNLOAD = 180
USER_AGENT = 'WindfallECU/1.0'

CACHE_TTL_SEARCH = 120
CACHE_TTL_VERSIONS = 60
_cache = {}

SERVER_LOADER_MAP = {
    'paper': ['bukkit', 'paper', 'purpur', 'spigot'], 'purpur': ['bukkit', 'paper', 'purpur', 'spigot'],
    'folia': ['bukkit', 'paper', 'purpur', 'spigot'], 'fabric': ['fabric'],
    'quilt': ['quilt'], 'neoforge': ['neoforge'], 'forge': ['forge'], 'vanilla': None,
}

HANGAR_PLATFORM_MAP = {
    'PAPER': ['bukkit', 'paper', 'purpur', 'spigot'],
    'WATERFALL': ['bukkit', 'paper', 'purpur', 'spigot'],
    'VELOCITY': [],
    'FABRIC': ['fabric'], 'QUILT': ['quilt'], 'FORGE': ['forge'], 'NEOFORGE': ['neoforge'],
}

_log = logging.getLogger(__name__)

# ---- HTTP helper with retry + User-Agent ----

def _request(url, params=None, timeout=TIMEOUT_SEARCH, retries=3):
    headers = {'User-Agent': USER_AGENT}
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 429:
                _time.sleep(1 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == retries - 1:
                _log.warning('Request failed after %d retries: %s %s', retries, url, e)
                return None
            _time.sleep(1 * (attempt + 1))
        except Exception as e:
            _log.warning('Request error: %s %s', url, e)
            return None
    return None

def _cache_get(key):
    val, expiry = _cache.get(key, (None, 0))
    return val if _time.time() < expiry else None

def _cache_set(key, val, ttl):
    _cache[key] = (val, _time.time() + ttl)

# ---- Plugin metadata key helpers ----

def _meta_key(provider, project_id):
    return f"{provider}:{project_id}"

def _split_key(key):
    if ':' in key:
        return key.split(':', 1)
    return ('modrinth', key)

def _find_meta(meta, project_id):
    for k, v in meta.items():
        if _split_key(k)[1] == project_id:
            return k, v
    return None, None

# ---- Search ----

def _modrinth_search(query, loaders=None, game_version=None, limit=24):
    cache_key = ('msearch', query, str(loaders), str(game_version))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    params = {'query': query, 'limit': limit}
    facets = []
    if loaders:
        facets.append([f'categories:{l}' for l in loaders])
    if game_version:
        facets.append([f'versions:{game_version}'])
    if facets:
        params['facets'] = json.dumps(facets)
    d = _request(f'{MODRINTH_API}/search', params=params)
    if not isinstance(d, dict):
        return []
    hits = d.get('hits', [])
    if not isinstance(hits, list):
        return []
    res = [{
        'provider': 'modrinth', 'id': h['project_id'], 'slug': h['slug'], 'name': h['title'],
        'description': (h.get('description') or '')[:200], 'downloads': h.get('downloads', 0),
        'icon_url': h.get('icon_url', ''), 'latest_version': h.get('latest_version', ''),
        'game_versions': (h.get('versions') or [])[-3:], 'loaders': h.get('categories', []),
        'project_url': f"https://modrinth.com/plugin/{h['slug']}", 'author': h.get('author', ''),
        'installable': True,
    } for h in hits if isinstance(h, dict)]
    _cache_set(cache_key, res, CACHE_TTL_SEARCH)
    return res

def _spiget_search(query, limit=20):
    cache_key = ('ssearch', query)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    data = _request(f'{SPIGET_API}/search/resources/{quote(query)}', params={'size': limit, 'field': 'name,description,tag'}, timeout=TIMEOUT_SEARCH)
    if not isinstance(data, list):
        return []
    res = []
    for h in data:
        if not isinstance(h, dict):
            continue
        premium = h.get('premium') or {}
        price_str = premium.get('price', '0')
        try:
            if float(price_str) > 0:
                continue
        except (ValueError, TypeError):
            pass
        icon = h.get('icon') or {}
        ver = h.get('version') or {}
        author = h.get('author') or {}
        res.append({
            'provider': 'spigot', 'id': str(h['id']), 'slug': str(h['id']),
            'name': h['name'], 'description': (h.get('tag') or '')[:200],
            'downloads': h.get('downloads', 0), 'icon_url': icon.get('url', ''),
            'latest_version': ver.get('name', ''),
            'game_versions': (h.get('testedVersions') or [])[-3:],
            'loaders': ['spigot', 'bukkit', 'paper'],
            'project_url': f"https://www.spigotmc.org/resources/{h['id']}/",
            'author': author.get('name', ''),
            'installable': True,
        })
    _cache_set(cache_key, res, CACHE_TTL_SEARCH)
    return res

def _hangar_search(query, limit=25):
    cache_key = ('hsearch', query)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    data = _request(f'{HANGAR_API}/projects', params={'q': query, 'limit': limit})
    hits = (data.get('result') or []) if isinstance(data, dict) else []
    if not isinstance(hits, list):
        return []
    res = [{
        'provider': 'hangar', 'id': h['namespace']['slug'], 'slug': h['namespace']['slug'],
        'name': h['name'], 'description': (h.get('description') or '')[:200],
        'downloads': (h.get('stats') or {}).get('downloads', 0), 'icon_url': '',
        'latest_version': '', 'game_versions': [],
        'loaders': ['spigot', 'bukkit', 'paper'],
        'project_url': f"https://hangar.papermc.io/{h['namespace']['owner']}/{h['namespace']['slug']}",
        'author': h['namespace']['owner'],
        'installable': False,
    } for h in hits if isinstance(h, dict)]
    _cache_set(cache_key, res, CACHE_TTL_SEARCH)
    return res

def search_plugins(query, provider=None, server_type=None, game_version=None):
    loaders = SERVER_LOADER_MAP.get(server_type) if server_type else None
    if loaders is None and server_type:
        return []
    results = []
    if provider in (None, 'modrinth'):
        try:
            results.extend(_modrinth_search(query, loaders=loaders, game_version=game_version))
        except Exception as e:
            _log.warning('modrinth search: %s', e)
    if provider in (None, 'spigot'):
        try:
            results.extend(_spiget_search(query))
        except Exception as e:
            _log.warning('spiget search: %s', e)
    if provider in (None, 'hangar'):
        try:
            results.extend(_hangar_search(query))
        except Exception as e:
            _log.warning('hangar search: %s', e)
    results.sort(key=lambda p: p['downloads'], reverse=True)
    return results

# ---- Versions ----

def _modrinth_versions(project_id):
    cache_key = ('mvers', project_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    d = _request(f'{MODRINTH_API}/project/{project_id}/version', timeout=TIMEOUT_VERSIONS)
    if not isinstance(d, list):
        return []
    _cache_set(cache_key, d, CACHE_TTL_VERSIONS)
    return d

def _spiget_versions(resource_id):
    cache_key = ('svers', resource_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    data = _request(f'{SPIGET_API}/resources/{resource_id}/versions', params={'size': 50}, timeout=TIMEOUT_VERSIONS)
    if not isinstance(data, list):
        return []
    resource = _request(f'{SPIGET_API}/resources/{resource_id}', timeout=TIMEOUT_SEARCH)
    res = []
    for v in data:
        if not isinstance(v, dict):
            continue
        v_id = str(v.get('id', ''))
        v_name = v.get('name', '')
        fn = resource.get('fileName', f'{resource_id}-{v_id}.jar') if isinstance(resource, dict) else f'{resource_id}-{v_id}.jar'
        res.append({
            'id': v_id,
            'version_number': v_name,
            'name': v_name,
            'game_versions': [],
            'loaders': ['spigot', 'bukkit', 'paper'],
            'files': [{'url': f'{SPIGET_API}/resources/{resource_id}/versions/{v_id}/download', 'primary': True, 'filename': fn}],
        })
    _cache_set(cache_key, res, CACHE_TTL_VERSIONS)
    return res

def _hangar_versions(slug):
    cache_key = ('hvers', slug)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    data = _request(f'{HANGAR_API}/projects/{slug}/versions', params={'limit': 50}, timeout=TIMEOUT_VERSIONS)
    hits = (data.get('result') or []) if isinstance(data, dict) else []
    if not isinstance(hits, list):
        return []
    res = [{
        'id': v['name'],
        'version_number': v['name'],
        'name': v['name'],
        'game_versions': list(set(
            mv for p, deps in (v.get('platformDependencies') or {}).items()
            for mv in (deps or []) if mv
        )),
        'loaders': list(set(
            l for p in (v.get('platformDependencies') or {}).keys()
            for l in HANGAR_PLATFORM_MAP.get(p, [])
        )),
        'files': [],
    } for v in hits if isinstance(v, dict)]
    _cache_set(cache_key, res, CACHE_TTL_VERSIONS)
    return res

def get_versions(provider, project_id):
    if provider == 'modrinth':
        try:
            return _modrinth_versions(project_id)
        except Exception as e:
            _log.warning('modrinth versions: %s', e)
            return []
    elif provider == 'spigot':
        return _spiget_versions(project_id)
    elif provider == 'hangar':
        return _hangar_versions(project_id)
    return []

# ---- Plugin metadata ----

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
            meta = json.load(f)
    except Exception as e:
        _log.warning('meta read error: %s', e)
        return {}
    changed = False
    for k in list(meta.keys()):
        if ':' not in k:
            meta[f"modrinth:{k}"] = meta.pop(k)
            changed = True
    if changed:
        _write_meta(server_id, meta)
    return meta

def _write_meta(server_id, meta):
    mp = _meta_path(server_id)
    if not mp:
        return
    try:
        with open(mp, 'w') as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        _log.warning('meta write error: %s', e)

def _write_meta_entry(meta, project_id, provider, filename, version_id, version_number, name, game_versions, loaders):
    meta[_meta_key(provider, project_id)] = {
        'provider': provider, 'filename': filename,
        'project_id': project_id, 'version_id': version_id,
        'version_number': version_number, 'name': name,
        'game_versions': game_versions, 'loaders': loaders,
        'installed_at': int(_time.time()),
    }

def _download_jar(url, plugins_dir, filename):
    headers = {'User-Agent': USER_AGENT}
    r = requests.get(url, stream=True, headers=headers, timeout=TIMEOUT_DOWNLOAD)
    r.raise_for_status()
    fn = filename.replace('../', '').replace('..\\', '')
    fp = safe_join(plugins_dir, fn)
    with open(fp, 'wb') as f:
        for c in r.iter_content(8192):
            f.write(c)
    return fp

def _replace_plugin_file(plugins_dir, old_fn, new_fn, download_url):
    _download_jar(download_url, plugins_dir, new_fn)
    if old_fn != new_fn:
        old_fp = safe_join(plugins_dir, old_fn)
        if os.path.isfile(old_fp):
            os.remove(old_fp)

# ---- Version filtering helpers ----

def _filter_versions_by_loader(versions, allowed_loaders):
    if not allowed_loaders:
        return versions
    res = []
    for v in versions:
        v_loaders = v.get('loaders', [])
        if v_loaders and any(l in allowed_loaders for l in v_loaders):
            res.append(v)
    if not res:
        return versions
    return res

def _filter_versions_by_game_version(versions, game_version):
    if not game_version:
        return versions
    res = [v for v in versions if not v.get('game_versions') or game_version in v.get('game_versions', [])]
    if not res:
        return versions
    return res

# ---- Install ----

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
        gv = game_version or server.get('game_version', '')
        by_loader = _filter_versions_by_loader(versions, allowed)
        compatible = _filter_versions_by_game_version(by_loader, gv)
        if not compatible:
            compatible = by_loader
        if not compatible and allowed:
            compatible = versions
        v = None
        if version_id:
            v = next((x for x in (compatible or versions) if x['id'] == version_id), None)
        elif version_number:
            v = next((x for x in (compatible or versions) if x.get('version_number') == version_number), None)
        if not v:
            if gv:
                v = next((x for x in (compatible or versions) if gv in x.get('game_versions', [])), None)
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
            _download_jar(pf['url'], plugins_dir, fn)
            meta = _read_meta(server_id)
            _write_meta_entry(meta, project_id, 'modrinth', fn,
                v['id'], v.get('version_number', ''), v.get('name', ''),
                v.get('game_versions', []), v.get('loaders', []))
            _write_meta(server_id, meta)
            _cache.clear()
            return True, f'Installed {fn}'
        except Exception as e:
            _log.warning('modrinth download: %s', e)
            return False, 'Download failed'

    elif provider == 'spigot':
        versions = _spiget_versions(project_id)
        if not versions:
            return False, 'No versions found'
        v = None
        if version_id:
            v = next((x for x in versions if x['id'] == version_id), None)
        if not v:
            v = versions[0]
        if not v:
            return False, 'No suitable version found'
        files = v.get('files', [])
        if not files:
            return False, 'No downloadable files'
        pf = next((f for f in files if f.get('primary')), files[0])
        try:
            _download_jar(pf['url'], plugins_dir, pf['filename'])
            meta = _read_meta(server_id)
            _write_meta_entry(meta, project_id, 'spigot', pf['filename'],
                v['id'], v.get('version_number', ''), v.get('name', ''),
                v.get('game_versions', []), v.get('loaders', []))
            _write_meta(server_id, meta)
            _cache.clear()
            return True, f'Installed {pf["filename"]}'
        except Exception as e:
            _log.warning('spigot download: %s', e)
            return False, 'Download failed'

    elif provider == 'hangar':
        return False, 'Hangar downloads require manual install. Visit the project page.'

    return False, 'Unknown provider'

# ---- Auto-recognize untracked JARs ----

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
    existing_fnames = {info.get('filename') for info in meta.values()}
    for f in sorted(os.listdir(pd)):
        if not f.endswith('.jar') or f in existing_fnames:
            continue
        fp = safe_join(pd, f)
        if not os.path.isfile(fp):
            continue
        term = _filename_to_search_term(f)
        if not term:
            continue
        found = False
        try:
            results = _modrinth_search(term, limit=10)
            t_clean = term.lower().replace(' ', '').replace('-', '').replace('_', '')
            for r in results:
                if _meta_key('modrinth', r['id']) in meta:
                    continue
                r_clean = r['name'].lower().replace(' ', '').replace('-', '').replace('_', '')
                if t_clean in r_clean or r_clean in t_clean:
                    _write_meta_entry(meta, r['id'], 'modrinth', f,
                        '', '', r['name'], r.get('game_versions', []), r.get('loaders', []))
                    changed = True
                    found = True
                    break
        except Exception as e:
            _log.warning('auto-recognize modrinth: %s', e)
        if not found:
            try:
                spigot_results = _spiget_search(term, limit=5)
                t_clean = term.lower().replace(' ', '').replace('-', '').replace('_', '')
                for r in spigot_results:
                    if _meta_key('spigot', r['id']) in meta:
                        continue
                    r_clean = r['name'].lower().replace(' ', '').replace('-', '').replace('_', '')
                    if t_clean in r_clean or r_clean in t_clean:
                        _write_meta_entry(meta, r['id'], 'spigot', f,
                            '', '', r['name'], r.get('game_versions', []), r.get('loaders', []))
                        changed = True
                        found = True
                        break
            except Exception as e:
                _log.warning('auto-recognize spiget: %s', e)
        if not found:
            try:
                slug = term.lower().replace(' ', '-').replace('_', '-')
                proj = _request(f'{MODRINTH_API}/project/{slug}')
                if isinstance(proj, dict) and proj.get('project_id') and _meta_key('modrinth', proj['project_id']) not in meta:
                    _write_meta_entry(meta, proj['project_id'], 'modrinth', f,
                        '', '', proj.get('title', term), [], proj.get('categories', []))
                    changed = True
            except Exception as e:
                _log.warning('auto-recognize slug fallback: %s', e)
    if changed:
        _write_meta(server_id, meta)

def _get_versions_by_provider(provider, project_id):
    if provider == 'modrinth':
        return _modrinth_versions(project_id)
    elif provider == 'spigot':
        return _spiget_versions(project_id)
    elif provider == 'hangar':
        return _hangar_versions(project_id)
    return []

# ---- Update checks ----

def check_updates(server_id):
    from models import get_server
    _auto_recognize(server_id)
    server = get_server(server_id)
    meta = _read_meta(server_id)
    if not meta:
        return []
    allowed = SERVER_LOADER_MAP.get(server.get('server_type', '')) if server else None
    gv = server.get('game_version', '') if server else ''
    updates = []
    changed = False
    for key, info in meta.items():
        pv = info.get('provider', 'modrinth')
        pid = info.get('project_id', _split_key(key)[1])
        try:
            versions = _get_versions_by_provider(pv, pid)
            if not versions:
                continue
            compatible = _filter_versions_by_game_version(
                _filter_versions_by_loader(versions, allowed), gv)
            if not compatible:
                compatible = versions
            latest = compatible[0]
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
                    'provider': pv,
                    'current_version': cv or '?',
                    'latest_version': lv,
                    'latest_version_id': latest['id'],
                    'filename': info.get('filename', ''),
                    'game_versions': latest.get('game_versions', []),
                })
        except Exception as e:
            _log.warning('check updates %s: %s', pid, e)
    if changed:
        _write_meta(server_id, meta)
    return updates

def update_plugin(server_id, project_id, version_id=None):
    from models import get_server
    server = get_server(server_id)
    if not server:
        return False, 'Server not found'
    meta = _read_meta(server_id)
    key, info = _find_meta(meta, project_id)
    if info is None:
        return False, 'Plugin not tracked'
    pv = info.get('provider', 'modrinth')
    old_fn = info['filename']
    plugins_dir = safe_join(server['path'], 'plugins')
    versions = _get_versions_by_provider(pv, project_id)
    if not versions:
        return False, 'No versions found'
    allowed = SERVER_LOADER_MAP.get(server.get('server_type', ''))
    gv = server.get('game_version', '')
    compatible = _filter_versions_by_game_version(
        _filter_versions_by_loader(versions, allowed), gv)
    if not compatible:
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
        _replace_plugin_file(plugins_dir, old_fn, new_fn, pf['url'])
        del meta[key]
        _write_meta_entry(meta, project_id, pv, new_fn,
            v['id'], v.get('version_number', ''), v.get('name', ''),
            v.get('game_versions', []), v.get('loaders', []))
        _write_meta(server_id, meta)
        _cache.clear()
        return True, f'Updated to {new_fn}'
    except Exception as e:
        _log.warning('update plugin %s: %s', project_id, e)
        return False, 'Update failed'

# ---- Mismatch detection / fix ----

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
    for key, info in meta.items():
        pv = info.get('provider', 'modrinth')
        if pv != 'modrinth':
            continue
        pid = info.get('project_id', _split_key(key)[1])
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
                    'fix_version': '', 'fix_version_id': '', 'provider': pv,
                })
                continue
            best = compatible[0]
            mismatched.append({
                'project_id': pid, 'filename': info.get('filename', ''),
                'name': info.get('name', ''),
                'reason': f'Wrong loader: needs {"/".join(allowed)}',
                'fix_version': best.get('version_number', ''),
                'fix_version_id': best['id'],
                'provider': pv,
            })
        except Exception as e:
            _log.warning('mismatch check %s: %s', pid, e)
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
    key, info = _find_meta(meta, project_id)
    if info is None:
        return False, 'Plugin not tracked'
    pv = info.get('provider', 'modrinth')
    old_fn = info['filename']
    plugins_dir = safe_join(server['path'], 'plugins')
    versions = _get_versions_by_provider(pv, project_id)
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
        _replace_plugin_file(plugins_dir, old_fn, new_fn, pf['url'])
        del meta[key]
        _write_meta_entry(meta, project_id, pv, new_fn,
            v['id'], v.get('version_number', ''), v.get('name', ''),
            v.get('game_versions', []), v.get('loaders', []))
        _write_meta(server_id, meta)
        _cache.clear()
        return True, f'Fixed: replaced with {new_fn}'
    except Exception as e:
        _log.warning('fix plugin %s: %s', project_id, e)
        return False, 'Fix failed'

def _auto_fix(server_id):
    mismatched = check_mismatched_plugins(server_id)
    for m in mismatched:
        if m.get('fix_version_id'):
            try:
                fix_plugin(server_id, m['project_id'])
            except Exception as e:
                _log.warning('auto-fix %s: %s', m.get('project_id'), e)

# ---- Auto-update settings ----

def get_auto_update(server_id):
    from models import get_setting
    v = get_setting(f'auto_update_{server_id}', '1')
    return v == '1'

def set_auto_update(server_id, enabled):
    from models import set_setting
    set_setting(f'auto_update_{server_id}', '1' if enabled else '0')

# ---- List installed ----

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
        provider = None
        for key, info in meta.items():
            if info.get('filename') == f:
                tracked = info.get('project_id', _split_key(key)[1])
                provider = info.get('provider', 'modrinth')
                break
        plugins.append({
            'filename': f, 'size': size, 'modified': modified,
            'tracked': bool(tracked), 'project_id': tracked,
            'provider': provider,
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
    for key, info in list(meta.items()):
        if info.get('filename') == filename:
            del meta[key]
            _write_meta(server_id, meta)
            break
    return True, f'Deleted {filename}'
