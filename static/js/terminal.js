let terminalState = { socket: null, term: null, pollTimer: null, since: 0, serverId: null, wsConnected: false };

async function loadTerminal(serverId) {
  cleanupTerminal();
  const container = document.getElementById('terminal-container');
  terminalState.serverId = serverId;
  const server = servers.find(s => s.id === serverId);
  if (!server || !server.status || !server.status.running) {
    container.innerHTML = `
      <div class="empty-state">
        <p>Server is offline</p>
        <p style="font-size:12px;margin-top:4px;color:var(--text-dim)">Start the server to access the console</p>
      </div>`;
    return;
  }
      container.innerHTML = `
    <div id="xterm-wrap" class="terminal-wrapper">
      <div id="xterm-container"></div>
    </div>
    <div class="console-controls">
      <div class="console-input-row">
        <input type="text" id="console-input" placeholder="Type a command..." autocomplete="off" spellcheck="false">
        <button class="btn btn-accent" id="console-send-btn">Send command</button>
      </div>
      <div class="console-actions-row">
        <button class="btn btn-success" id="console-start-btn" onclick="startServer()">Start</button>
        <button class="btn btn-primary" id="console-restart-btn" onclick="restartServer()">Restart</button>
        <button class="btn btn-danger" id="console-stop-btn" onclick="stopServer()">Stop</button>
      </div>
    </div>
    <div class="console-status-wrap">
      <span class="console-status" id="console-status">&bull;</span>
      <span id="console-status-text">Connecting...</span>
    </div>`;

  const xtermEl = document.getElementById('xterm-container');
  const s = getComputedStyle(document.documentElement);
  const css = p => s.getPropertyValue(p).trim();
  const term = new Terminal({
    cursorBlink: true, cursorStyle: 'block', fontSize: 14,
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
    disableStdin: true, convertEol: true, cols: 100, rows: 30,
        theme: {
      background: '#0c0c0c',
      foreground: '#d2d2d2',
      cursor: '#ffffff',
      selectionBackground: 'rgba(255, 255, 255, 0.3)',
      black: '#000000', red: '#c50f1f', green: '#13a10e',
      yellow: '#c19c00', blue: '#0037da', magenta: '#881798',
      cyan: '#3a96dd', white: '#cccccc',
      brightBlack: '#767676', brightRed: '#e74856',
      brightGreen: '#16c60c', brightYellow: '#f9f1a5',
      brightBlue: '#3b78ff', brightMagenta: '#b4009e',
      brightCyan: '#61d6d6', brightWhite: '#f2f2f2',
    },
  });
  term.open(xtermEl);
  terminalState.term = term;

  const input = document.getElementById('console-input');
  const sendBtn = document.getElementById('console-send-btn');
  const doSend = () => {
    if (!input) return;
    const cmd = input.value;
    if (cmd.trim()) {
      sendCommand(terminalState.serverId, cmd + '\n');
      if (terminalState.term) terminalState.term.write(`\x1b[90m> ${cmd}\x1b[0m\r\n`);
      input.value = '';
    }
  };
  if (input) {
    input.addEventListener('keydown', e => { if (e.key === 'Enter') doSend(); });
    input.focus();
  }
  if (sendBtn) sendBtn.addEventListener('click', doSend);
  input.focus();

  await fetchConsole(serverId, term);
  tryConnectSocket(serverId, term);
}

function sendCommand(serverId, data) {
  serverId = serverId || activeServerId;
  if (terminalState.socket && terminalState.socket.connected) {
    terminalState.socket.emit('terminal_input', { server_id: serverId, data });
  } else {
    api('POST', `/servers/${serverId}/console/input`, { data }).catch(() => {});
  }
}

function cleanupTerminal() {
  if (terminalState.pollTimer) { clearInterval(terminalState.pollTimer); terminalState.pollTimer = null; }
  if (terminalState.socket) { terminalState.socket.disconnect(); terminalState.socket = null; }
  if (terminalState.term) { terminalState.term.dispose(); terminalState.term = null; }
  terminalState.since = 0; terminalState.serverId = null; terminalState.wsConnected = false;
  const s = document.getElementById('console-status');
  if (s) { s.className = 'console-status'; s.textContent = '\u25CF'; }
}

async function fetchConsole(serverId, term) {
  try {
    const data = await api('GET', `/servers/${serverId}/console?since=0`);
    if (data.output) term.write(data.output);
    terminalState.since = data.total || 0;
    setConnected(data.running);
    if (data.running && document.getElementById('console-input')) if (document.getElementById('console-input')) document.getElementById('console-input').focus();
  } catch { setConnected(false); }
}

function tryConnectSocket(serverId, term) {
  const socket = io({
    transports: ['websocket', 'polling'], reconnection: true, reconnectionDelay: 1000,
  });
  socket.on('connect_error', () => {
    terminalState.wsConnected = false; setConnected(false);
    startPolling(serverId, term);
  });
  socket.on('connect', () => {
    terminalState.wsConnected = true; stopPolling(); setConnected(true);
    socket.emit('connect_terminal', { server_id: serverId });
    if (document.getElementById('console-input')) document.getElementById('console-input').focus();
  });
  socket.on('terminal_output', data => {
    if (data && data.data) { term.write(data.data); }
  });
  socket.on('disconnect', () => {
    terminalState.wsConnected = false; setConnected(false);
    startPolling(serverId, term);
  });
  terminalState.socket = socket;
}

function setConnected(yes) {
  const s = document.getElementById('console-status');
  const t = document.getElementById('console-status-text');
  const startBtn = document.getElementById('console-start-btn');
  const restartBtn = document.getElementById('console-restart-btn');
  const stopBtn = document.getElementById('console-stop-btn');

  if (s) {
    s.textContent = yes ? '\u25CF' : '\u25CB';
    s.className = 'console-status' + (yes ? ' live' : '');
  }
  if (t) {
    t.textContent = yes ? 'Live Console' : 'Disconnected (Polling)';
  }
  if (startBtn) startBtn.style.display = yes ? 'none' : '';
  if (restartBtn) restartBtn.style.display = yes ? '' : 'none';
  if (stopBtn) stopBtn.style.display = yes ? '' : 'none';
}

function startPolling(serverId, term) {
  if (terminalState.pollTimer) return;
  terminalState.pollTimer = setInterval(() => pollConsole(serverId, term), 1500);
}

function stopPolling() {
  if (terminalState.pollTimer) { clearInterval(terminalState.pollTimer); terminalState.pollTimer = null; }
}

async function pollConsole(serverId, term) {
  if (terminalState.wsConnected) { stopPolling(); return; }
  try {
    const data = await api('GET', `/servers/${serverId}/console?since=${terminalState.since}`);
    if (data.output) { term.write(data.output); terminalState.since = data.total || terminalState.since; }
    setConnected(data.running);
  } catch {}
}
