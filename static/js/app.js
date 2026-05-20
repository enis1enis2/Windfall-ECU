const API = '/api';

let servers = [];
let activeServerId = null;
let activeTab = 'terminal';
let currentUserId = null;
let currentUserRole = 'viewer';

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
  if (r.status === 401) {
    window.location.href = '/?_=' + Date.now();
    throw new Error('Authentication required');
  }
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

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escapeJs(str) {
  return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r');
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
      <span class="name">${escapeHtml(s.name)}</span>
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
  closeSidebar();
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

/* User Manager */

async function openUserManager() {
  try {
    const users = await api('GET', '/users');
    const list = document.getElementById('users-list');
    list.innerHTML = users.map(u => {
      const date = new Date(u.created_at + 'Z').toLocaleDateString();
      const badge = u.role === 'admin' ? 'Admin' : u.role === 'operator' ? 'Operator' : 'Viewer';
      return `<div class="backup-item" style="cursor:pointer" onclick="openUserEdit(${u.id})">
        <div class="info">
          <div class="name">${escapeHtml(u.username)} ${u.id === currentUserId ? '<span style="font-size:11px;color:var(--text-muted)">(you)</span>' : ''}</div>
          <div class="meta"><span style="display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600;background:var(--accent-subtle);color:var(--accent)">${badge}</span> &middot; Created ${date}</div>
        </div>
        <span class="btn btn-outline btn-xs">Edit</span>
      </div>`;
    }).join('');
    document.getElementById('users-modal').classList.remove('hidden');
  } catch (e) {
    notify(e.message, 'error');
  }
}

function closeUserManager() {
  document.getElementById('users-modal').classList.add('hidden');
}

async function loadRoleOptions(selected) {
  const sel = document.getElementById('user-edit-role');
  sel.innerHTML = '';
  for (const [key, val] of Object.entries({admin: 'Admin', operator: 'Operator', viewer: 'Viewer'})) {
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = val;
    if (key === selected) opt.selected = true;
    sel.appendChild(opt);
  }
}

function openCreateUser() {
  document.getElementById('user-edit-id').value = '';
  document.getElementById('user-edit-username').value = '';
  document.getElementById('user-edit-password').value = '';
  document.getElementById('user-edit-title').textContent = 'Create User';
  document.getElementById('user-delete-btn').style.display = 'none';
  loadRoleOptions('viewer');
  closeUserManager();
  document.getElementById('user-edit-modal').classList.remove('hidden');
}

async function openUserEdit(userId) {
  const users = await api('GET', '/users');
  const user = users.find(u => u.id === userId);
  if (!user) return;
  document.getElementById('user-edit-id').value = userId;
  document.getElementById('user-edit-username').value = user.username;
  document.getElementById('user-edit-password').value = '';
  document.getElementById('user-edit-title').textContent = `Edit User: ${user.username}`;
  document.getElementById('user-delete-btn').style.display = '';
  loadRoleOptions(user.role);
  closeUserManager();
  document.getElementById('user-edit-modal').classList.remove('hidden');
}

function closeUserEdit() {
  document.getElementById('user-edit-modal').classList.add('hidden');
  document.getElementById('user-delete-btn').style.display = '';
}

async function saveUser() {
  const id = document.getElementById('user-edit-id').value;
  const username = document.getElementById('user-edit-username').value.trim();
  const password = document.getElementById('user-edit-password').value;
  const role = document.getElementById('user-edit-role').value;
  const body = { role };
  if (username) body.username = username;
  if (password) body.password = password;
  if (!id) {
    if (!password) { notify('Password is required for new users', 'error'); return; }
    try {
      await api('POST', '/users', { username, password, role });
      notify('User created', 'success');
      closeUserEdit();
      openUserManager();
    } catch (e) { notify(e.message, 'error'); }
    return;
  }
  try {
    await api('PATCH', `/users/${id}`, body);
    notify('User updated', 'success');
    closeUserEdit();
    openUserManager();
  } catch (e) {
    notify(e.message, 'error');
  }
}

async function deleteUser() {
  const id = document.getElementById('user-edit-id').value;
  const username = document.getElementById('user-edit-username').value;
  if (!confirm(`Delete user "${username}" permanently?`)) return;
  try {
    await api('DELETE', `/users/${id}`);
    notify('User deleted', 'success');
    closeUserEdit();
    openUserManager();
  } catch (e) {
    notify(e.message, 'error');
  }
}

/* Auto Backup Settings */
async function openAutoBackupSettings() {
  try {
    const data = await api('GET', '/settings');
    document.getElementById('ab-enabled').checked = data.auto_backup_enabled === 'true';
    document.getElementById('ab-interval').value = data.auto_backup_interval || '60';
    document.getElementById('ab-retention').value = data.auto_backup_retention || '10';
    document.getElementById('autobackup-modal').classList.remove('hidden');
  } catch (e) {
    notify(e.message, 'error');
  }
}

function closeAutoBackupSettings() {
  document.getElementById('autobackup-modal').classList.add('hidden');
}

async function saveAutoBackupSettings() {
  try {
    await api('POST', '/settings', {
      auto_backup_enabled: document.getElementById('ab-enabled').checked ? 'true' : 'false',
      auto_backup_interval: String(parseInt(document.getElementById('ab-interval').value) || 60),
      auto_backup_retention: String(parseInt(document.getElementById('ab-retention').value) || 10),
    });
    notify('Auto backup settings saved', 'success');
    closeAutoBackupSettings();
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
  const btn = document.querySelector('.theme-toggle-btn');
  if (btn) btn.textContent = next === 'dark' ? '🌙 Dark Mode' : '☀️ Light Mode';
  localStorage.setItem('windfall-ecu-theme', next);
}

function loadTheme() {
  const saved = localStorage.getItem('windfall-ecu-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  const btn = document.querySelector('.theme-toggle-btn');
  if (btn) btn.textContent = saved === 'dark' ? '🌙 Dark Mode' : '☀️ Light Mode';
}

/* Sidebar toggle for mobile */
function toggleSidebar() {
  document.querySelector('.sidebar').classList.toggle('open');
  document.querySelector('.sidebar-overlay').classList.toggle('visible');
}

function closeSidebar() {
  document.querySelector('.sidebar').classList.remove('open');
  document.querySelector('.sidebar-overlay').classList.remove('visible');
}

/* Tab click handlers */
document.querySelectorAll('.tab').forEach(el => {
  el.addEventListener('click', () => {
    closeSidebar();
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

async function loadUser() {
  try {
    const data = await api('GET', '/auth/status');
    if (data.authenticated) {
      currentUserId = data.user_id;
      currentUserRole = data.role;
    }
  } catch (e) { /* not authenticated */ }
}

try { loadTheme(); } catch (e) { /* theme toggle may not exist in cached html */ }
loadUser().then(() => loadServers());

function logoutUser() {
  fetch('/api/auth/logout', { method: 'POST' }).then(() => {
    window.location.href = '/';
  }).catch(() => {
    window.location.href = '/';
  });
}

/* System Metrics */
function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let s = bytes;
  while (s >= 1024 && i < u.length - 1) { s /= 1024; i++; }
  return `${s.toFixed(1)} ${u[i]}`;
}

let metricsInterval = null;

async function updateMetrics() {
  try {
    const data = await api('GET', '/system/metrics');
    const ram = data.ram, cpu = data.cpu, disk = data.disk;

    document.getElementById('metric-ram-txt').textContent =
      `${formatBytes(ram.used)} / ${formatBytes(ram.total)}`;
    document.getElementById('metric-ram-bar').style.width = ram.percent + '%';
    document.getElementById('metric-ram-bar').className = 'progress' + (ram.percent > 80 ? ' danger' : ram.percent > 60 ? ' warning' : '');

    document.getElementById('metric-cpu-txt').textContent = cpu.percent.toFixed(1) + '%';
    document.getElementById('metric-cpu-bar').style.width = cpu.percent + '%';
    document.getElementById('metric-cpu-bar').className = 'progress' + (cpu.percent > 80 ? ' danger' : cpu.percent > 60 ? ' warning' : '');

    document.getElementById('metric-disk-txt').textContent =
      `${formatBytes(disk.used)} / ${formatBytes(disk.total)}`;
    document.getElementById('metric-disk-bar').style.width = disk.percent + '%';
    document.getElementById('metric-disk-bar').className = 'progress' + (disk.percent > 90 ? ' danger' : disk.percent > 75 ? ' warning' : '');
  } catch (e) { /* silently retry */ }
}

/* Panel Auto-Update */
let updateInterval = null;

async function checkForUpdates() {
  try {
    const data = await api('GET', '/update/check');
    const btn = document.getElementById('update-btn');
    if (data.update_available) {
      btn.style.display = '';
      btn.title = `Update available (${data.commits_behind} commit${data.commits_behind > 1 ? 's' : ''} behind)`;
    } else {
      btn.style.display = 'none';
    }
    return data;
  } catch (e) {
    return null;
  }
}

function openUpdateModal() {
  const modal = document.getElementById('update-modal');
  document.getElementById('update-install-btn').style.display = '';
  document.getElementById('update-installing').style.display = 'none';
  document.getElementById('update-commit-log').style.display = '';
  modal.classList.remove('hidden');
  checkForUpdates().then(data => {
    if (data && data.log) {
      document.getElementById('update-commit-log').textContent = data.log;
    }
  });
}

function closeUpdateModal() {
  document.getElementById('update-modal').classList.add('hidden');
}

async function installUpdate() {
  document.getElementById('update-install-btn').style.display = 'none';
  document.getElementById('update-installing').style.display = '';
  document.getElementById('update-commit-log').style.display = 'none';
  try {
    await api('POST', '/update/install');
    document.getElementById('update-installing').textContent = 'Restarting panel...';
    setTimeout(() => { window.location.reload(); }, 3000);
  } catch (e) {
    document.getElementById('update-installing').style.display = 'none';
    document.getElementById('update-install-btn').style.display = '';
    document.getElementById('update-commit-log').style.display = '';
    notify(e.message, 'error');
  }
}

/* Secret Admin Panel */
function openAdminPanel() {
  document.getElementById('admin-modal').classList.remove('hidden');
  loadAdminInfo();
}
function closeAdminPanel() {
  document.getElementById('admin-modal').classList.add('hidden');
}
function adminPanelTrigger() {
  if (currentUserRole === 'admin') openAdminPanel();
}
async function loadAdminInfo() {
  const el = document.getElementById('admin-content');
  try {
    const d = await api('GET', '/admin/info');
    const ups = Math.floor(d.uptime / 86400);
    const uph = Math.floor((d.uptime % 86400) / 3600);
    const upm = Math.floor((d.uptime % 3600) / 60);
    const dp = d.disk_total ? (d.disk_used / d.disk_total * 100).toFixed(1) : 0;
    el.innerHTML = `
      <div class="admin-section">
        <div class="admin-section-title">System</div>
        <div class="admin-grid">
          <div class="admin-card">
            <span class="admin-label">Python</span>
            <span class="admin-value">${d.python}</span>
          </div>
          <div class="admin-card">
            <span class="admin-label">Platform</span>
            <span class="admin-value">${escapeHtml(d.platform)}</span>
          </div>
          <div class="admin-card">
            <span class="admin-label">Host Uptime</span>
            <span class="admin-value">${ups}d ${uph}h ${upm}m</span>
          </div>
          <div class="admin-card">
            <span class="admin-label">Database</span>
            <span class="admin-value">${formatBytes(d.db_size)}</span>
          </div>
        </div>
      </div>
      <div class="admin-section">
        <div class="admin-section-title">Storage</div>
        <div class="admin-grid">
          <div class="admin-card">
            <span class="admin-label">Server Data</span>
            <span class="admin-value">${formatBytes(d.server_dir_size)}</span>
          </div>
          <div class="admin-card">
            <span class="admin-label">Backups</span>
            <span class="admin-value">${formatBytes(d.backups_dir_size)}</span>
          </div>
          <div class="admin-card">
            <span class="admin-label">Disk Usage</span>
            <span class="admin-value">${formatBytes(d.disk_used)} / ${formatBytes(d.disk_total)}</span>
            <div class="admin-bar"><div class="admin-bar-fill" style="width:${dp}%"></div></div>
          </div>
        </div>
      </div>
      <div class="admin-section">
        <div class="admin-section-title">Stats</div>
        <div class="admin-grid">
          <div class="admin-card">
            <span class="admin-label">Total Users</span>
            <span class="admin-value">${d.users_total}</span>
            <span class="admin-sub">${d.users_by_role.admin} admin · ${d.users_by_role.operator} operator · ${d.users_by_role.viewer} viewer</span>
          </div>
          <div class="admin-card">
            <span class="admin-label">Servers</span>
            <span class="admin-value">${d.servers_total}</span>
            <span class="admin-sub">${d.servers_running} running</span>
          </div>
        </div>
      </div>
    `;
  } catch {
    el.innerHTML = '<p style="padding:20px;color:var(--text-dim);text-align:center">Failed to load admin info</p>';
  }
}

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

  /* System metrics polling */
  updateMetrics();
  metricsInterval = setInterval(updateMetrics, 2000);

  /* Panel auto-update polling */
  checkForUpdates();
  updateInterval = setInterval(checkForUpdates, 60000);

  /* Secret admin panel trigger */
  if (currentUserRole === 'admin') {
    const abtn = document.getElementById('admin-btn');
    if (abtn) abtn.style.display = '';
    const header = document.querySelector('.sidebar-header h1');
    if (header) { header.style.cursor = 'pointer'; header.addEventListener('dblclick', adminPanelTrigger); }
  }

  /* Modal overlay click-dismiss */
  document.querySelectorAll('.modal-overlay').forEach(el => {
    el.addEventListener('click', (e) => {
      if (e.target === el) el.classList.add('hidden');
    });
  });
});
