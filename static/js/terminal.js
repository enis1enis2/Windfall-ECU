let terminalState = { socket: null, term: null, pollTimer: null, lastPos: 0, serverId: null };

async function loadTerminal(serverId) {
  cleanupTerminal();

  const container = document.getElementById('terminal-container');
  terminalState.serverId = serverId;

  const server = servers.find(s => s.id === serverId);
  if (!server || !server.status || !server.status.running) {
    container.innerHTML = `
      <div class="empty-state">
        <p>Server is offline</p>
        <p style="font-size:12px;margin-top:4px">Start the server to access the terminal</p>
      </div>`;
    return;
  }

  container.innerHTML = `
    <div class="terminal-status-bar" id="term-status">Connecting...</div>
    <div id="xterm-container" style="height:calc(100% - 28px)"></div>`;

  const term = new Terminal({
    cursorBlink: true,
    cursorStyle: 'block',
    fontSize: 14,
    fontFamily: "'Cascadia Code', 'Fira Code', monospace",
    theme: {
      background: '#0d1117', foreground: '#c9d1d9', cursor: '#e94560',
      selection: 'rgba(233,69,96,0.3)',
      black: '#484f58', red: '#ff7b72', green: '#3fb950', yellow: '#d29922',
      blue: '#58a6ff', magenta: '#bc8cff', cyan: '#39c5cf', white: '#b1bac4',
    },
    rows: Math.floor(container.clientHeight / 20) || 24,
    cols: Math.floor(container.clientWidth / 9) || 80,
  });

  term.open(document.getElementById('xterm-container'));
  terminalState.term = term;

  // First, load any existing console output via REST
  await fetchConsoleHistory(serverId, term);

  // Then try WebSocket for live updates
  tryConnectSocket(serverId, term);

  // Polling fallback
  terminalState.pollTimer = setInterval(() => pollConsole(serverId, term), 1000);
}

function cleanupTerminal() {
  if (terminalState.pollTimer) {
    clearInterval(terminalState.pollTimer);
    terminalState.pollTimer = null;
  }
  if (terminalState.socket) {
    terminalState.socket.disconnect();
    terminalState.socket = null;
  }
  if (terminalState.term) {
    terminalState.term.dispose();
    terminalState.term = null;
  }
  terminalState.lastPos = 0;
  terminalState.serverId = null;
}

async function fetchConsoleHistory(serverId, term) {
  try {
    const data = await api('GET', `/servers/${serverId}/console`);
    if (data.output) {
      term.write(data.output);
    }
    terminalState.lastPos = data.pos || 0;
    setTermStatus(data.running ? 'Connected' : 'Stopped', data.running ? 'connected' : '');
  } catch (e) {
    setTermStatus('Error loading console', 'error');
  }
}

function tryConnectSocket(serverId, term) {
  const socket = io({
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 1000,
  });

  socket.on('connect_error', () => {
    setTermStatus('Live: polling (WebSocket unavailable)', 'polling');
  });

  socket.on('connect', () => {
    setTermStatus('Live: WebSocket', 'connected');
    socket.emit('connect_terminal', { server_id: serverId });
  });

  socket.on('terminal_output', (data) => {
    if (data && data.data) {
      term.write(data.data);
    }
  });

  socket.on('disconnect', () => {
    setTermStatus('Live: polling (disconnected)', 'polling');
  });

  term.onData(data => {
    if (socket && socket.connected) {
      socket.emit('terminal_input', { server_id: serverId, data });
    }
  });

  terminalState.socket = socket;
}

async function pollConsole(serverId, term) {
  try {
    const data = await api('GET', `/servers/${serverId}/console`);
    if (data.output && data.pos > terminalState.lastPos) {
      const newOutput = data.output;
      term.write(newOutput);
      terminalState.lastPos = data.pos;
    }
    if (!data.running) {
      setTermStatus('Server stopped', '');
    }
  } catch (e) {
    // ignore poll errors
  }
}

function setTermStatus(text, cls) {
  const bar = document.getElementById('term-status');
  if (bar) {
    bar.textContent = text;
    bar.className = 'terminal-status-bar' + (cls ? ' ' + cls : '');
  }
}
