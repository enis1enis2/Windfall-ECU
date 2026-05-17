async function loadTerminal(serverId) {
  const container = document.getElementById('terminal-container');
  const server = servers.find(s => s.id === serverId);
  if (!server) return;

  const isRunning = server.status && server.status.running;
  if (!isRunning) {
    container.innerHTML = `
      <div class="empty-state">
        <p>Server is offline</p>
        <p style="font-size:12px;margin-top:4px">Start the server to access the terminal</p>
      </div>`;
    return;
  }

  container.innerHTML = '<div id="xterm-container" style="height:100%"></div>';

  const term = new Terminal({
    cursorBlink: true,
    cursorStyle: 'block',
    fontSize: 14,
    fontFamily: "'Cascadia Code', 'Fira Code', monospace",
    theme: {
      background: '#0d1117',
      foreground: '#c9d1d9',
      cursor: '#e94560',
      selection: 'rgba(233,69,96,0.3)',
      black: '#484f58',
      red: '#ff7b72',
      green: '#3fb950',
      yellow: '#d29922',
      blue: '#58a6ff',
      magenta: '#bc8cff',
      cyan: '#39c5cf',
      white: '#b1bac4',
    },
    rows: Math.floor(document.getElementById('terminal-container').clientHeight / 20) || 24,
    cols: Math.floor(document.getElementById('terminal-container').clientWidth / 9) || 80,
  });

  term.open(document.getElementById('xterm-container'));

  const socket = io();

  socket.on('connect', () => {
    socket.emit('connect_terminal', { server_id: serverId });
  });

  socket.on('terminal_output', (data) => {
    term.write(data.data);
  });

  term.onData(data => {
    if (socket && socket.connected) {
      socket.emit('terminal_input', { server_id: serverId, data });
    }
  });

  window.terminalInstance = term;
  window.terminalSocket = socket;
}
