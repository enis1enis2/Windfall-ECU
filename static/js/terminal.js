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
    <div id="xterm-wrap" style="flex:1;overflow:hidden;position:relative">
      <div id="xterm-container" style="height:100%"></div>
    </div>
    <div class="console-bar">
      <span class="console-prompt">&gt;</span>
      <input type="text" id="console-input" placeholder="Type a command..." autocomplete="off" spellcheck="false">
      <span class="console-status" id="console-status">&bull;</span>
    </div>`;

  const xtermEl = document.getElementById('xterm-container');
  const s = getComputedStyle(document.documentElement);
  const css = p => s.getPropertyValue(p).trim();
  const term = new Terminal({
    cursorBlink: true, cursorStyle: 'block', fontSize: 13,
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
    disableStdin: true, convertEol: true, cols: 80, rows: 24,
    theme: {
      background: css('--terminal-bg'), foreground: css('--term-fg'), cursor: css('--term-cursor'),
      selectionBackground: css('--term-selection'),
      black: css('--term-black'), red: css('--term-red'), green: css('--term-green'),
      yellow: css('--term-yellow'), blue: css('--term-blue'), magenta: css('--term-magenta'),
      cyan: css('--term-cyan'), white: css('--term-white'),
      brightBlack: css('--term-bright-black'), brightRed: css('--term-bright-red'),
      brightGreen: css('--term-bright-green'), brightYellow: css('--term-bright-yellow'),
      brightBlue: css('--term-bright-blue'), brightMagenta: css('--term-bright-magenta'),
      brightCyan: css('--term-bright-cyan'), brightWhite: css('--term-bright-white'),
    },
  });
  term.open(xtermEl);
  terminalState.term = term;

  const input = document.getElementById('console-input');
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const cmd = input.value;
      if (cmd.trim()) {
        sendCommand(serverId, cmd + '\n');
        term.write(`\x1b[90m> ${cmd}\x1b[0m\r\n`);
        input.value = '';
      }
    }
  });
  input.focus();

  await fetchConsole(serverId, term);
  tryConnectSocket(serverId, term);
}

function sendCommand(serverId, data) {
  if (terminalState.socket && terminalState.socket.connected) {
    terminalState.socket.emit('terminal_input', { server_id: serverId, data });
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
    if (data.running) document.getElementById('console-input').focus();
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
    document.getElementById('console-input').focus();
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
  if (s) { s.textContent = yes ? '\u25CF' : '\u25CB'; s.className = 'console-status' + (yes ? ' live' : ''); }
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
