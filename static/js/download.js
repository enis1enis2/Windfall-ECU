let downloadTypes = [];

async function loadDownloadTypes() {
  try {
    downloadTypes = await api('GET', '/download/types');
    const sel = document.getElementById('dl-type');
    downloadTypes.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = t.name;
      sel.appendChild(opt);
    });
  } catch (e) {
    notify('Failed to load server types', 'error');
  }
}

async function onTypeChange() {
  const type = document.getElementById('dl-type').value;
  const verSel = document.getElementById('dl-version');
  const buildGroup = document.getElementById('dl-build-group');
  const dlBtn = document.getElementById('dl-download-btn');

  verSel.innerHTML = '<option value="">Loading...</option>';
  verSel.disabled = true;
  buildGroup.classList.add('hidden');
  dlBtn.disabled = true;

  if (!type) {
    verSel.innerHTML = '<option value="">Select a type first</option>';
    return;
  }

  try {
    const versions = await api('GET', `/download/versions/${type}`);
    verSel.innerHTML = '<option value="">Select version</option>';
    versions.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      verSel.appendChild(opt);
    });
    verSel.disabled = false;

    const needsBuild = ['paper', 'folia', 'purpur'].includes(type);
    if (needsBuild) {
      buildGroup.classList.remove('hidden');
    }
  } catch (e) {
    verSel.innerHTML = '<option value="">Failed to load</option>';
    notify(e.message, 'error');
  }
}

async function onVersionChange() {
  const type = document.getElementById('dl-type').value;
  const version = document.getElementById('dl-version').value;
  const buildSel = document.getElementById('dl-build');
  const dlBtn = document.getElementById('dl-download-btn');

  buildSel.innerHTML = '<option value="">Latest</option>';
  buildSel.disabled = true;
  dlBtn.disabled = !version;

  if (!version || !['paper', 'folia', 'purpur'].includes(type)) return;

  try {
    const builds = await api('GET', `/download/builds/${type}/${version}`);
    buildSel.innerHTML = '<option value="">Latest</option>';
    builds.forEach(b => {
      const opt = document.createElement('option');
      opt.value = b.build;
      const label = `Build #${b.build}`;
      opt.textContent = b.channel ? `${label} (${b.channel})` : label;
      buildSel.appendChild(opt);
    });
    buildSel.disabled = false;
  } catch (e) {
    notify(e.message, 'error');
  }
}

async function downloadServer() {
  const type = document.getElementById('dl-type').value;
  const version = document.getElementById('dl-version').value;
  const build = document.getElementById('dl-build').value;
  const name = document.getElementById('dl-name').value.trim();

  if (!type || !version) {
    notify('Select server type and version', 'error');
    return;
  }

  const btn = document.getElementById('dl-download-btn');
  btn.disabled = true;
  btn.textContent = 'Downloading...';

  const body = { type, version };
  if (build) body.build = parseInt(build);
  if (name) body.name = name;

  try {
    const result = await api('POST', '/download', body);
    notify(`Server downloaded!`, 'success');
    await loadServers();
    selectServer(result.id);

    document.getElementById('dl-type').value = '';
    document.getElementById('dl-version').innerHTML = '<option value="">Select type first</option>';
    document.getElementById('dl-version').disabled = true;
    document.getElementById('dl-build').innerHTML = '<option value="">Latest</option>';
    document.getElementById('dl-build').disabled = true;
    document.getElementById('dl-build-group').classList.add('hidden');
    document.getElementById('dl-name').value = '';
    btn.disabled = true;
    btn.textContent = 'Download';
  } catch (e) {
    notify(`Download failed: ${e.message}`, 'error');
    btn.disabled = false;
    btn.textContent = 'Download';
  }
}

async function upgradeServer(serverId) {
  if (!confirm('Upgrade this server to the latest version? The old JAR will be backed up.')) return;
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = 'Upgrading...';
  try {
    const result = await api('POST', `/servers/${serverId}/upgrade`);
    notify(`Server upgraded to ${result.version}${result.build ? ' (build ' + result.build + ')' : ''}`, 'success');
    await loadServers();
  } catch (e) {
    notify(`Upgrade failed: ${e.message}`, 'error');
  }
  btn.disabled = false;
  btn.textContent = 'Upgrade';
}

document.addEventListener('DOMContentLoaded', () => {
  loadDownloadTypes();
});
