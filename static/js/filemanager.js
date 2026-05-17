let currentFilePath = '';
let fileTreeCache = {};

async function loadFiles(serverId) {
  const panel = document.getElementById('file-panel');
  panel.innerHTML = `
    <div class="file-tree" id="file-tree"></div>
    <div class="file-editor" id="file-editor">
      <div class="empty-state"><p>Select a file to view or edit</p></div>
    </div>
  `;
  fileTreeCache = {};
  currentFilePath = '';
  await renderFileTree(serverId, '');
}

async function renderFileTree(serverId, path) {
  const tree = document.getElementById('file-tree');
  try {
    const data = await api('GET', `/servers/${serverId}/files?path=${encodeURIComponent(path)}`);
    tree.innerHTML = buildTreeHtml(serverId, data, path);
  } catch (e) {
    tree.innerHTML = `<p style="color:var(--text-dim);padding:8px;font-size:13px">Error loading files</p>`;
  }
}

function buildTreeHtml(serverId, data, basePath) {
  let html = '';
  if (data.parent !== null && data.parent !== undefined) {
    html += `<div class="tree-item" onclick="renderFileTree(${serverId}, '${escapeHtml(data.parent)}')">
      <span class="icon">📂</span> ..
    </div>`;
  }
  data.entries.forEach(entry => {
    const icon = entry.is_dir ? '📁' : '📄';
    const iconClass = entry.is_dir ? 'folder-icon' : 'file-icon';
    const path = entry.path;
    const display = entry.name;
    if (entry.is_dir) {
      html += `<div class="tree-item" onclick="renderFileTree(${serverId}, '${escapeHtml(path)}')">
        <span class="icon ${iconClass}">${icon}</span> ${escapeHtml(display)}
      </div>`;
    } else {
      html += `<div class="tree-item ${currentFilePath === path ? 'selected' : ''}" onclick="openFile(${serverId}, '${escapeHtml(path)}')">
        <span class="icon ${iconClass}">${icon}</span> ${escapeHtml(display)}
      </div>`;
    }
  });
  return html;
}

async function openFile(serverId, path) {
  currentFilePath = path;
  document.querySelectorAll('.tree-item').forEach(el => el.classList.remove('selected'));
  const editor = document.getElementById('file-editor');
  editor.innerHTML = `<div class="spinner"></div>`;
  try {
    const data = await api('GET', `/servers/${serverId}/files/read?path=${encodeURIComponent(path)}`);
    editor.innerHTML = `
      <textarea id="file-content">${escapeHtml(data.content)}</textarea>
      <div class="editor-actions">
        <button class="btn btn-success btn-sm" onclick="saveFile(${serverId})">Save</button>
        <button class="btn btn-danger btn-sm" onclick="deleteFile(${serverId})">Delete</button>
      </div>
    `;
    await renderFileTree(serverId, path.substring(0, path.lastIndexOf('/')) || '');
  } catch (e) {
    editor.innerHTML = `<div class="empty-state"><p>Error: ${escapeHtml(e.message)}</p></div>`;
  }
}

async function saveFile(serverId) {
  const content = document.getElementById('file-content').value;
  try {
    await api('POST', `/servers/${serverId}/files/write`, { path: currentFilePath, content });
    notify('File saved', 'success');
  } catch (e) {
    notify(e.message, 'error');
  }
}

async function deleteFile(serverId) {
  if (!confirm('Delete this file?')) return;
  try {
    await api('POST', `/servers/${serverId}/files/delete`, { path: currentFilePath });
    currentFilePath = '';
    await loadFiles(serverId);
    notify('File deleted', 'success');
  } catch (e) {
    notify(e.message, 'error');
  }
}

async function uploadFileToServer(serverId) {
  const input = document.createElement('input');
  input.type = 'file';
  input.multiple = true;
  input.onchange = async () => {
    const form = new FormData();
    for (const file of input.files) {
      form.append('file', file);
    }
    form.append('path', '');
    try {
      await api('POST', `/servers/${serverId}/files/upload`, form);
      await loadFiles(serverId);
      notify('Files uploaded', 'success');
    } catch (e) {
      notify(e.message, 'error');
    }
  };
  input.click();
}

async function createFolder(serverId) {
  const name = prompt('Folder name:');
  if (!name) return;
  try {
    await api('POST', `/servers/${serverId}/files/mkdir`, { name, path: '' });
    await loadFiles(serverId);
    notify('Folder created', 'success');
  } catch (e) {
    notify(e.message, 'error');
  }
}


