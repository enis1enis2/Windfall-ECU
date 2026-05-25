async function handleImportZip(event) {
  const file = event.target.files[0];
  if (!file) return;
  if (!file.name.endsWith('.zip')) { notify('Please select a .zip file', 'error'); return; }

  const zone = document.getElementById('import-zone');
  zone.classList.add('has-file', 'uploading');

  try {
    if (file.size > 10 * 1024 * 1024) {
      await chunkedUpload(file, zone);
    } else {
      await directUpload(file, zone);
    }
  } catch (e) {
    notify('Import failed: ' + e.message, 'error');
    resetZone(zone);
  }
  event.target.value = '';
}

async function directUpload(file, zone) {
  zone.innerHTML = '<div class="spinner"></div><p style="margin-top:12px">Importing...</p>';
  const form = new FormData();
  form.append('file', file);
  form.append('name', file.name.replace('.zip', ''));
  const sel = document.getElementById('import-type');
  if (sel && sel.value) form.append('server_type', sel.value);
  const result = await api('POST', '/import/zip', form);
  onImportDone(result, zone);
}

async function chunkedUpload(file, zone) {
  const CHUNK = 4 * 1024 * 1024;
  const total = file.size;
  const cid = (await api('POST', '/import/chunked/init', {
    filename: file.name, total_size: total, name: file.name.replace('.zip', ''),
    server_type: (document.getElementById('import-type') || {}).value || ''
  })).cid;

  zone.innerHTML = `
    <div style="width:100%;max-width:320px;margin:0 auto;text-align:left">
      <p style="font-size:13px;margin-bottom:8px;color:var(--text-muted)">Uploading <strong>${escapeHtml(file.name)}</strong></p>
      <div class="metric-bar" style="height:8px"><div class="progress" id="chunk-progress" style="width:0%"></div></div>
      <p style="font-size:11px;color:var(--text-dim);margin-top:6px" id="chunk-status">0%</p>
    </div>
  `;

  const totalChunks = Math.ceil(total / CHUNK);
  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK;
    const end = Math.min(start + CHUNK, total);
    const chunk = file.slice(start, end);
    let uploaded = false;
    for (let retry = 0; retry < 3 && !uploaded; retry++) {
      try {
        const r = await fetch(API + '/import/chunked/' + cid + '/' + i, { method: 'POST', body: chunk });
        if (!r.ok) throw new Error('Chunk upload failed');
        uploaded = true;
      } catch (e) {
        if (retry === 2) throw e;
        await new Promise(r => setTimeout(r, 1000 * (retry + 1)));
      }
    }
    const pct = Math.round((i + 1) / totalChunks * 100);
    document.getElementById('chunk-progress').style.width = pct + '%';
    document.getElementById('chunk-status').textContent = pct + '% (' + formatBytes(Math.min((i + 1) * CHUNK, total)) + ' / ' + formatBytes(total) + ')';
  }

  document.getElementById('chunk-status').textContent = 'Processing...';
  const result = await api('POST', '/import/chunked/' + cid + '/finalize');
  onImportDone(result, zone);
}

function onImportDone(result, zone) {
  notify('Server "' + result.name + '" imported successfully!', 'success');
  loadServers();
  selectServer(result.id);
  zone.classList.remove('has-file', 'uploading');
  resetZone(zone);
}

function resetZone(zone) {
  zone.innerHTML = `
    <div class="icon">📦</div>
    <p class="primary-text">Drop a .zip file here or click to browse</p>
    <p class="secondary-text">The zip should contain a server JAR and config files (e.g. Paper, Spigot, Vanilla)</p>
  `;
}

async function manualImport() {
  document.getElementById('import-input').click();
}
