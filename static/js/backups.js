async function loadBackups(serverId) {
  const container = document.getElementById('backup-list');
  container.innerHTML = '<div class="spinner"></div>';
  try {
    const backups = await api('GET', `/servers/${serverId}/backups`);
    renderBackups(backups, serverId);
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><p>${escapeHtml(e.message)}</p></div>`;
  }
}

function renderBackups(backups, serverId) {
  const container = document.getElementById('backup-list');
  container.innerHTML = '';

  const header = document.createElement('div');
  header.style.cssText = 'display:flex;gap:8px;margin-bottom:16px';
  header.innerHTML = `
    <button class="btn btn-success btn-sm" onclick="createBackup(${serverId})">Create Backup</button>
  `;
  container.appendChild(header);

  if (!backups.length) {
    container.innerHTML += `<div class="empty-state"><p>No backups yet</p></div>`;
    return;
  }

  backups.forEach(b => {
    const div = document.createElement('div');
    div.className = 'backup-item';
    const date = new Date(b.created_at + 'Z').toLocaleString();
    const size = formatBytes(b.size);
    div.innerHTML = `
      <div class="info">
        <div class="name">${escapeHtml(b.name)}</div>
        <div class="meta">${date} &middot; ${size}</div>
      </div>
      <div class="actions">
        <button class="btn btn-success btn-sm" onclick="restoreBackup(${b.id})">Restore</button>
        <button class="btn btn-danger btn-sm" onclick="deleteBackupById(${b.id})">Delete</button>
      </div>
    `;
    container.appendChild(div);
  });
}

async function createBackup(serverId) {
  const name = prompt('Backup name (optional):');
  try {
    await api('POST', `/servers/${serverId}/backups`, { name: name || undefined });
    await loadBackups(serverId);
    notify('Backup created', 'success');
  } catch (e) {
    notify(e.message, 'error');
  }
}

async function restoreBackup(backupId) {
  if (!confirm('Restore this backup? Current server files will be replaced.')) return;
  try {
    await api('POST', `/backups/${backupId}/restore`);
    notify('Backup restored', 'success');
  } catch (e) {
    notify(e.message, 'error');
  }
}

async function deleteBackupById(backupId) {
  if (!confirm('Delete this backup?')) return;
  try {
    await api('DELETE', `/backups/${backupId}`);
    if (activeServerId) await loadBackups(activeServerId);
    notify('Backup deleted', 'success');
  } catch (e) {
    notify(e.message, 'error');
  }
}


