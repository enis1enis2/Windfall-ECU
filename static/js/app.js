const API = '/api';

let servers = [];
let activeServerId = null;
let activeTab = 'terminal';

function notify(msg, type = 'info') {
  const existing = document.querySelectorAll('.notification');
  if (existing.length >= 5) existing[0].remove();
  const el = document.createElement('div');
  el.className = `notification ${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body && !(body instanceof FormData)) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  } else if (body instanceof FormData) {
    opts.body = body;
  }
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: r.statusText }));
    throw new Error(err.error || r.statusText);
  }
  return r.json();
}

async function loadServers() {
  const list = document.getElementById('server-list');
  list.innerHTML = '<div class="spinner"></div>';
  try {
    servers = await api('GET', '/servers');
    renderServerList();
  } catch (e) {
    list.innerHTML = `<p style="color:var(--text-dim);padding:12px">Failed to load servers</p>`;
  }
}

function renderServerList() {
  const list = document.getElementById('server-list');
  list.innerHTML = '';
  if (!servers.length) {
    list.innerHTML = `<p style="color:var(--text-dim);padding:12px;font-size:13px">No servers yet.<br>Click + to add one or import a .zip</p>`;
    return;
  }
  servers.forEach(s => {
    const div = document.createElement('div');
    div.className = `server-list-item${s.id === activeServerId ? ' active' : ''}`;
    div.innerHTML = `
      <span class="status-dot ${s.status && s.status.running ? 'online' : 'offline'}"></span>
      <span class="name">${s.name}</span>
    `;
    div.onclick = () => selectServer(s.id);
    list.appendChild(div);
  });
}

async function createServer() {
  const name = prompt('Server name:');
  if (!name) return;
  try {
    await api('POST', '/servers', { name });
    await loadServers();
    notify('Server created', 'success');
  } catch (e) {
    notify(e.message, 'error');
  }
}

async function deleteServer() {
  if (!activeServerId || !confirm('Delete this server permanently? This cannot be undone.')) return;
  try {
    await api('DELETE', `/servers/${activeServerId}`);
    activeServerId = null;
    document.getElementById('main-title').textContent = 'Select a server';
    document.getElementById('server-actions').classList.add('hidden');
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    await loadServers();
    notify('Server deleted', 'success');
  } catch (e) {
    notify(e.message, 'error');
  }
}

async function startServer() {
  if (!activeServerId) return;
  try {
    await api('POST', `/servers/${activeServerId}/start`);
    notify('Server starting...', 'info');
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 1000));
      await loadServers();
      const s = servers.find(x => x.id === activeServerId);
      if (s && s.status && s.status.running) {
        selectServer(activeServerId);
        return;
      }
    }
    notify('Server took too long to start', 'error');
  } catch (e) {
    notify(e.message, 'error');
  }
}

function stopServer() {
  if (!activeServerId) return;
  const server = servers.find(s => s.id === activeServerId);
  document.getElementById('stop-server-name').textContent = server ? server.name : 'the server';
  document.getElementById('stop-confirm-overlay').classList.remove('hidden');
}

function closeStopConfirm() {
  document.getElementById('stop-confirm-overlay').classList.add('hidden');
}

async function confirmStop() {
  closeStopConfirm();
  if (!activeServerId) return;
  try {
    await api('POST', `/servers/${activeServerId}/stop`);
    notify('Server stopped', 'info');
    cleanupTerminal();
    await loadServers();
    updateServerActions();
    const container = document.getElementById('terminal-container');
    container.innerHTML = `<div class="empty-state"><p>Server stopped</p></div>`;
  } catch (e) {
    notify(e.message, 'error');
  }
}

async function restartServer() {
  if (!activeServerId) return;
  try {
    await api('POST', `/servers/${activeServerId}/restart`);
    notify('Server restarting...', 'info');
    cleanupTerminal();
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 1000));
      await loadServers();
      const s = servers.find(x => x.id === activeServerId);
      if (s && s.status && s.status.running) {
        selectServer(activeServerId);
        return;
      }
    }
    notify('Server took too long to restart', 'error');
  } catch (e) {
    notify(e.message, 'error');
  }
}

function updateServerActions() {
  const s = servers.find(x => x.id === activeServerId);
  const running = s && s.status && s.status.running;
  document.getElementById('btn-start').style.display = running ? 'none' : '';
  document.getElementById('btn-restart').style.display = running ? '' : 'none';
  document.getElementById('btn-stop').style.display = running ? '' : 'none';
}

function selectServer(id) {
  cleanupTerminal();
  activeServerId = id;
  renderServerList();
  const server = servers.find(s => s.id === id);
  if (!server) return;
  document.getElementById('main-title').textContent = server.name;
  document.getElementById('server-actions').classList.remove('hidden');
  updateServerActions();
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  switchTab('terminal');
  loadTerminal(id);
  loadBackups(id);
  loadFiles(id);
  loadPlugins(id);
}

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(el => el.classList.toggle('active', el.id === `tab-${tab}`));
}

/* Settings */
function openSettings(serverId) {
  const server = servers.find(s => s.id === serverId);
  if (!server) return;
  document.getElementById('settings-name').value = server.name || '';
  document.getElementById('settings-type').value = server.server_type || '';
  document.getElementById('settings-args').value = server.java_args || '';
  document.getElementById('settings-modal').classList.remove('hidden');
}

function closeSettings() {
  document.getElementById('settings-modal').classList.add('hidden');
}

async function saveSettings() {
  const args = document.getElementById('settings-args').value.trim();
  try {
    await api('PUT', `/servers/${activeServerId}/java_args`, { java_args: args });
    notify('Settings saved', 'success');
    await loadServers();
    closeSettings();
  } catch (e) {
    notify(e.message, 'error');
  }
}

/* Server Properties Editor */
async function editServerProperties(serverId) {
  closeSettings();
  try {
    let content = '';
    try {
      const data = await api('GET', `/servers/${serverId}/files/read?path=server.properties`);
      content = data.content || '';
    } catch (e) {
      content = '# server.properties\n# Create new properties here\n';
    }
    document.getElementById('properties-editor').value = content;
    document.getElementById('properties-modal').classList.remove('hidden');
  } catch (e) {
    notify(e.message, 'error');
  }
}

function closePropertiesEditor() {
  document.getElementById('properties-modal').classList.add('hidden');
}

async function saveProperties(serverId) {
  const content = document.getElementById('properties-editor').value;
  try {
    await api('POST', `/servers/${serverId}/files/write`, { path: 'server.properties', content });
    notify('Properties saved', 'success');
    closePropertiesEditor();
  } catch (e) {
    notify(e.message, 'error');
  }
}

/* Theme Toggle */
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  document.getElementById('theme-toggle').textContent = next === 'dark' ? '🌙' : '☀️';
  localStorage.setItem('greatpanel-theme', next);
}

function loadTheme() {
  const saved = localStorage.getItem('greatpanel-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  document.getElementById('theme-toggle').textContent = saved === 'dark' ? '🌙' : '☀️';
}

/* Tab click handlers */
document.querySelectorAll('.tab').forEach(el => {
  el.addEventListener('click', () => {
    const tab = el.dataset.tab;
    switchTab(tab);
    if (tab === 'terminal' && activeServerId) loadTerminal(activeServerId);
    if (tab === 'files' && activeServerId) loadFiles(activeServerId);
    if (tab === 'backups' && activeServerId) loadBackups(activeServerId);
    if (tab === 'plugins' && activeServerId) loadPlugins(activeServerId);
  });
});

document.addEventListener('visibilitychange', () => {
  if (!document.hidden && activeTab === 'terminal' && activeServerId) {
    cleanupTerminal();
    loadTerminal(activeServerId);
  }
});

loadTheme();
loadServers();

document.addEventListener('DOMContentLoaded', () => {
  const zone = document.getElementById('import-zone');
  zone.addEventListener('click', () => {
    document.getElementById('import-input').click();
  });
  document.getElementById('import-input').addEventListener('change', handleImportZip);

  /* Drag-and-drop for import */
  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => {
    zone.classList.remove('drag-over');
  });
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].name.endsWith('.zip')) {
      document.getElementById('import-input').files = files;
      handleImportZip({ target: { files: [files[0]] } });
    } else {
      notify('Please drop a .zip file', 'error');
    }
  });

  /* Modal overlay click-dismiss */
  document.querySelectorAll('.modal-overlay').forEach(el => {
    el.addEventListener('click', (e) => {
      if (e.target === el) el.classList.add('hidden');
    });
  });
});
