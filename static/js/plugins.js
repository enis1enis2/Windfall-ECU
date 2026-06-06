let searchTimeout = null;

async function loadPlugins(serverId) {
  const container = document.getElementById('plugins-container');
  container.innerHTML = `
    <div class="plugins-layout">
      <div class="plugins-installed">
        <div class="plugins-header">
          <h4>Installed Plugins</h4>
          <button class="btn btn-sm btn-outline" onclick="checkPluginUpdates(${serverId})" id="update-all-btn">Check Updates</button>
        </div>
        <div id="installed-plugins-list"><div class="spinner"></div></div>
      </div>
      <div class="plugins-browse">
        <div class="plugins-header">
          <h4>Browse Plugins</h4>
          <div class="plugin-search-bar">
            <input type="text" id="plugin-search-input" placeholder="Search Modrinth..." oninput="onSearchInput()">
          </div>
        </div>
        <div id="plugin-search-results"><div class="empty-state"><p>Search for plugins above</p></div></div>
      </div>
    </div>
  `;
  await loadInstalledPlugins(serverId);
  checkPluginUpdates(serverId);
}

async function loadInstalledPlugins(serverId) {
  const list = document.getElementById('installed-plugins-list');
  try {
    const plugins = await api('GET', `/servers/${serverId}/plugins`);
    if (!plugins.length) {
      list.innerHTML = '<div class="empty-state"><p>No plugins installed</p></div>';
      return;
    }
    list.innerHTML = '';
    plugins.forEach(p => {
      const div = document.createElement('div');
      div.className = 'installed-plugin-item';
      const size = formatBytes(p.size);
      const date = new Date(p.modified * 1000).toLocaleDateString();
      const badge = p.tracked ? '<span class="badge badge-tracked" title="Tracked for updates">📡</span>' : '<span class="badge badge-untracked" title="Not tracked (installed manually)">?</span>';
      div.innerHTML = `
        <div class="plugin-info">
          <div class="plugin-name">${badge} ${escapeHtml(p.filename)}</div>
          <div class="plugin-meta">${size} &middot; ${date}</div>
        </div>
        <div style="display:flex;gap:4px">
          ${p.tracked ? `<button class="btn btn-sm btn-outline" onclick="updateSinglePlugin(${serverId}, '${escapeJs(p.project_id)}')" title="Update">↻</button>` : ''}
          <button class="btn btn-danger btn-sm" onclick="deleteInstalledPlugin(${serverId}, '${escapeJs(p.filename)}')">Delete</button>
        </div>
      `;
      list.appendChild(div);
    });
  } catch (e) {
    list.innerHTML = `<div class="empty-state"><p>${escapeHtml(e.message)}</p></div>`;
  }
}

async function checkPluginUpdates(serverId) {
  const btn = document.getElementById('update-all-btn');
  btn.disabled = true;
  btn.textContent = 'Checking...';
  try {
    const updates = await api('GET', `/servers/${serverId}/plugins/updates`);
    if (!updates.length) {
      notify('All plugins are up to date', 'success');
      btn.textContent = 'Check Updates';
      btn.disabled = false;
      return;
    }
    for (const u of updates) {
      try {
        await api('POST', `/servers/${serverId}/plugins/update`, { project_id: u.project_id });
        notify(`Updated ${escapeHtml(u.filename)} to ${u.latest_version}`, 'success');
      } catch (e) {
        notify(`Failed to update ${escapeHtml(u.filename)}: ${e.message}`, 'error');
      }
    }
    await loadInstalledPlugins(serverId);
  } catch (e) {
    notify(e.message, 'error');
  }
  btn.textContent = 'Check Updates';
  btn.disabled = false;
}

async function updateSinglePlugin(serverId, projectId) {
  try {
    await api('POST', `/servers/${serverId}/plugins/update`, { project_id: projectId });
    notify('Plugin updated', 'success');
    await loadInstalledPlugins(serverId);
  } catch (e) {
    notify(e.message, 'error');
  }
}

function onSearchInput() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(doPluginSearch, 400);
}

async function doPluginSearch() {
  const q = document.getElementById('plugin-search-input').value.trim();
  const container = document.getElementById('plugin-search-results');

  if (q.length < 2) {
    container.innerHTML = '<div class="empty-state"><p>Enter at least 2 characters to search</p></div>';
    return;
  }

  container.innerHTML = '<div class="spinner"></div>';

  try {
    let url = `/plugins/search?q=${encodeURIComponent(q)}`;
    if (activeServerId) {
      const server = await api('GET', `/servers/${activeServerId}`);
      if (server.server_type) url += `&server_type=${encodeURIComponent(server.server_type)}`;
      if (server.game_version) url += `&game_version=${encodeURIComponent(server.game_version)}`;
    }
    const results = await api('GET', url);
    renderSearchResults(results);
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><p>Search failed: ${escapeHtml(e.message)}</p></div>`;
  }
}

function renderSearchResults(results) {
  const container = document.getElementById('plugin-search-results');
  container.innerHTML = '';

  if (!results.length) {
    container.innerHTML = '<div class="empty-state"><p>No plugins found</p></div>';
    return;
  }

  const grid = document.createElement('div');
  grid.className = 'plugin-results-grid';
  results.forEach(p => {
    const loaderBadges = (p.loaders || []).slice(0, 4).map(l =>
      `<span class="loader-badge">${l}</span>`
    ).join('');

    const versionBadges = (p.game_versions || []).slice(0, 3).map(v =>
      `<span class="version-badge">${v}</span>`
    ).join('');

    const card = document.createElement('div');
    card.className = 'plugin-card';
    card.innerHTML = `
      <div class="plugin-card-header">
        ${p.icon_url ? `<img src="${p.icon_url}" class="plugin-icon" onerror="this.style.display='none'">` : '<div class="plugin-icon-placeholder"></div>'}
        <div class="plugin-card-title">
          <div class="plugin-card-name">${escapeHtml(p.name)}</div>
          <div class="plugin-card-author">${escapeHtml(p.author)}</div>
        </div>
        <span class="provider-badge provider-${p.provider}">${p.provider}</span>
      </div>
      <div class="plugin-card-desc">${escapeHtml(p.description)}</div>
      <div class="plugin-card-badges">
        ${loaderBadges}
        ${versionBadges}
      </div>
      <div class="plugin-card-meta">
        <span>${formatDownloads(p.downloads)} downloads</span>
        <span>v${escapeHtml(p.latest_version)}</span>
      </div>
      <div class="plugin-card-actions">
        <button class="btn btn-success btn-sm" onclick="showInstallDialog('${escapeJs(p.provider)}', '${escapeJs(p.id)}', '${escapeJs(p.name)}', ${activeServerId})">Install</button>
        <a href="${escapeHtml(p.project_url)}" target="_blank" class="btn btn-secondary btn-sm">View</a>
      </div>
    `;
    grid.appendChild(card);
  });
  container.appendChild(grid);
}

async function showInstallDialog(provider, projectId, name, serverId) {
  const dialog = document.getElementById('plugin-install-dialog');
  document.getElementById('install-provider').textContent = provider;
  document.getElementById('install-name').textContent = name;
  document.getElementById('install-server-id').value = serverId;
  document.getElementById('install-project-id').value = projectId;
  document.getElementById('install-provider-val').value = provider;

  const versionSel = document.getElementById('install-version');
  versionSel.innerHTML = '<option value="">Loading versions...</option>';
  dialog.classList.remove('hidden');

  try {
    const versions = await api('GET', `/plugins/versions/${provider}/${projectId}`);
    versionSel.innerHTML = '<option value="">Latest</option>';
    const server = await api('GET', `/servers/${serverId}`);
    const gv = server.game_version;
    versions.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v.id;
      let label = v.version_number;
      if (v.game_versions && v.game_versions.length) {
        label += ` (${v.game_versions.slice(0, 3).join(', ')})`;
      }
      if (gv && v.game_versions && v.game_versions.includes(gv)) {
        label += ' ✅';
      }
      opt.textContent = label;
      if (gv && v.game_versions && v.game_versions.includes(gv)) {
        opt.selected = true;
      }
      versionSel.appendChild(opt);
    });
  } catch (e) {
    versionSel.innerHTML = '<option value="">Latest (version list unavailable)</option>';
  }
}

function closeInstallDialog() {
  document.getElementById('plugin-install-dialog').classList.add('hidden');
}

async function confirmInstall() {
  const serverId = document.getElementById('install-server-id').value;
  const provider = document.getElementById('install-provider-val').value;
  const projectId = document.getElementById('install-project-id').value;
  const versionId = document.getElementById('install-version').value;

  if (!serverId || !provider || !projectId) return;

  const btn = document.querySelector('#plugin-install-dialog .btn-success');
  btn.disabled = true;
  btn.textContent = 'Installing...';

  try {
    let gv = '';
    try {
      const server = await api('GET', `/servers/${parseInt(serverId)}`);
      gv = server.game_version || '';
    } catch {}
    const body = { server_id: parseInt(serverId), provider, project_id: projectId };
    if (versionId) body.version_id = versionId;
    if (gv) body.game_version = gv;
    await api('POST', '/plugins/install', body);
    notify('Plugin installed!', 'success');
    closeInstallDialog();
    await loadInstalledPlugins(parseInt(serverId));
  } catch (e) {
    notify(`Install failed: ${e.message}`, 'error');
  }

  btn.disabled = false;
  btn.textContent = 'Install';
}

async function deleteInstalledPlugin(serverId, filename) {
  if (!confirm(`Delete ${filename}?`)) return;
  try {
    await api('DELETE', `/servers/${serverId}/plugins/${encodeURIComponent(filename)}`);
    notify('Plugin deleted', 'success');
    await loadInstalledPlugins(serverId);
  } catch (e) {
    notify(e.message, 'error');
  }
}

function formatDownloads(n) {
  if (!n) return '0';
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toString();
}
