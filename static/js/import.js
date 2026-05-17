async function handleImportZip(event) {
  const file = event.target.files[0];
  if (!file) return;

  const zone = document.getElementById('import-zone');
  zone.classList.add('has-file');
  zone.innerHTML = '<div class="spinner"></div><p style="margin-top:12px">Importing...</p>';

  const form = new FormData();
  form.append('file', file);
  form.append('name', file.name.replace('.zip', ''));

  try {
    const result = await api('POST', '/import/zip', form);
    notify(`Server "${result.id}" imported successfully!`, 'success');
    await loadServers();
    selectServer(result.id);
    zone.classList.remove('has-file');
    zone.innerHTML = `
      <div class="icon">📦</div>
      <p>Drop a .zip file here or click to browse</p>
      <p style="font-size:12px;margin-top:8px;color:var(--text-dim)">
        The zip should contain a server JAR and config files
      </p>
    `;
  } catch (e) {
    notify(`Import failed: ${e.message}`, 'error');
    zone.classList.remove('has-file');
    zone.innerHTML = `
      <div class="icon">📦</div>
      <p>Drop a .zip file here or click to browse</p>
      <p style="font-size:12px;margin-top:8px;color:var(--text-dim)">
        The zip should contain a server JAR and config files
      </p>
    `;
  }

  event.target.value = '';
}

async function manualImport() {
  document.getElementById('import-input').click();
}
