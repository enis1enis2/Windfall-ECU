const API = '/api';

let servers = [];
let activeServerId = null;
let activeTab = 'terminal';

function notify(msg, type = 'info') {
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

function selectServer(id) {
  if (window.terminalInstance) {
    window.terminalInstance.dispose();
    window.terminalInstance = null;
  }
  if (window.terminalSocket) {
    window.terminalSocket.disconnect();
    window.terminalSocket = null;
  }
  activeServerId = id;
  renderServerList();
  const server = servers.find(s => s.id === id);
  if (!server) return;
  document.getElementById('main-title').textContent = server.name;
  document.getElementById('server-actions').classList.remove('hidden');
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  switchTab('terminal');
  loadTerminal(id);
  loadBackups(id);
  loadFiles(id);
  loadPlugins(id);
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
  if (!activeServerId || !confirm('Delete this server permanently?')) return;
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
    await loadServers();
    setTimeout(() => selectServer(activeServerId), 500);
  } catch (e) {
    notify(e.message, 'error');
  }
}

async function stopServer() {
  if (!activeServerId) return;
  try {
    await api('POST', `/servers/${activeServerId}/stop`);
    notify('Server stopped', 'info');
    await loadServers();
  } catch (e) {
    notify(e.message, 'error');
  }
}

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(el => el.classList.toggle('active', el.id === `tab-${tab}`));
}

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

loadServers();

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('import-zone').addEventListener('click', () => {
    document.getElementById('import-input').click();
  });
  document.getElementById('import-input').addEventListener('change', handleImportZip);
});
