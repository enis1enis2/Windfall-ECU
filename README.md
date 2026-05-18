<div align="center">

  ![Windfall ECU](https://img.shields.io/badge/Windfall%20ECU-Minecraft%20Server%20Manager-3b82f6?style=for-the-badge)
  <br>
  [![License: MIT](https://img.shields.io/badge/License-MIT-3b82f6?style=flat-square)](LICENSE)
  [![Python](https://img.shields.io/badge/Python-3.8%2B-3b82f6?style=flat-square&logo=python&logoColor=white)](https://python.org)
  [![Flask](https://img.shields.io/badge/Flask-3.1-3b82f6?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
  [![Docker](https://img.shields.io/badge/Docker-ready-3b82f6?style=flat-square&logo=docker&logoColor=white)](https://docker.com)

  <h3>A self-hosted web-based Minecraft server management panel</h3>
  <p>Start, stop, configure, back up, and update Minecraft servers entirely from your browser.</p>

  <a href="#features">Features</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#manual-install">Manual Install</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#docker">Docker</a> ·
  <a href="#api">API</a>

</div>

---

## Features

- **Server Lifecycle** — Start, stop, restart, and delete servers with a single click
- **Web Terminal** — Pterodactyl-style live console: read-only xterm.js display, dedicated command input bar with `>` prompt, real-time WebSocket + polling fallback, connection status dot
- **File Manager** — Browse, edit, upload, and delete server files
- **Backup System** — Create, restore, and delete `.tar.gz` backups
- **Auto Backup** — Scheduled backups with customizable interval and retention
- **Plugin Manager** — Search and install plugins from Modrinth and Hangar
- **Server Downloader** — Download Paper, Folia, Purpur, Vanilla, Fabric, Quilt, Forge, and NeoForge
- **Auto-Upgrade** — Upgrade server JARs to the latest version with automatic backup
- **ZIP Import** — Import existing server directories via drag-and-drop ZIP upload
- **Server Properties Editor** — Edit `server.properties` directly from the UI
- **Authentication** — Login/register system with session-based auth
- **Dark/Light Theme** — Toggle between dark and light mode; terminal 16-color ANSI palette adapts per theme
- **Docker Support** — Run servers in isolated Docker containers
- **EULA Auto-Create** — `eula=true` written automatically on server creation
- **Launch Arguments** — Customize JVM arguments per server

---

## Quick Start

### One-Click Scripts

| Platform | Script |
|----------|--------|
| Linux / macOS | `./launch.sh` |
| Windows | Double-click `launch.bat` |

The script installs Python and Java if missing, creates a virtual environment, installs dependencies, optionally sets up autostart, and launches the panel. If `node` is available, static assets are built automatically.

> 💡 For the fastest possible experience, ensure Node.js 18+ is installed (tested on 26.1) — JS files are bundled and minified via esbuild, CSS via csso, and all text responses are gzip-compressed.

---

## Manual Install

```bash
# Clone the repository
git clone https://github.com/enis1enis2/GreatPanel.git
cd GreatPanel

# (Optional) Build optimized static assets
# Requires Node.js 18+ — JS is bundled via esbuild, CSS via csso
npm install && npm run build

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt

# Launch
python app.py
```

Open **http://localhost:8080** in your browser and log in with:

> **Username:** `admin` · **Password:** `admin`

> ⚠️ Change the default password after first login!

> 💡 The app works without the build step using the original JS/CSS files. `npm run build` bundles 7 JS files into 1 via esbuild, minifies CSS via csso. All text responses are gzip-compressed automatically. The terminal layout is Pterodactyl-inspired: read-only xterm display with a dedicated command input bar.

---

## Configuration

Windfall ECU is configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GREATPANEL_SECRET` | `windfall-ecu-secret-change-me` | Flask secret key for sessions |
| `GREATPANEL_HOST` | `0.0.0.0` | Web server bind address |
| `GREATPANEL_PORT` | `8080` | Web server port |
| `GREATPANEL_JAVA` | `java` | Java binary path |
| `GREATPANEL_ORIGIN` | `http://localhost:8080` | CORS allowed origin |

---

## Docker

```bash
docker compose up -d
```

The Dockerfile uses `python:3.12-slim` with OpenJDK 21 JRE. Server data and backups are stored in mounted volumes.

---

## API

All endpoints except auth require authentication via session cookie.

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/auth/status` | Check authentication status |
| `POST` | `/api/auth/login` | Log in |
| `POST` | `/api/auth/register` | Register new user |
| `POST` | `/api/auth/logout` | Log out |

### Servers

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/servers` | List all servers |
| `POST` | `/api/servers` | Create a server |
| `GET` | `/api/servers/:id` | Get server details |
| `DELETE` | `/api/servers/:id` | Delete server and files |
| `POST` | `/api/servers/:id/start` | Start server |
| `POST` | `/api/servers/:id/stop` | Stop server |
| `POST` | `/api/servers/:id/restart` | Restart server |
| `POST` | `/api/servers/:id/upgrade` | Upgrade server JAR |
| `GET` | `/api/servers/:id/status` | Server running status |
| `PUT` | `/api/servers/:id/java_args` | Update JVM arguments |
| `GET` | `/api/servers/:id/console?since=N` | Console output since line N |

### Files

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/servers/:id/files` | List files |
| `GET` | `/api/servers/:id/files/read` | Read file |
| `POST` | `/api/servers/:id/files/write` | Write file |
| `POST` | `/api/servers/:id/files/delete` | Delete file |
| `POST` | `/api/servers/:id/files/mkdir` | Create directory |
| `POST` | `/api/servers/:id/files/upload` | Upload files |
| `GET` | `/api/servers/:id/files/download` | Download file |

### Backups

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/servers/:id/backups` | List backups |
| `POST` | `/api/servers/:id/backups` | Create backup |
| `POST` | `/api/backups/:id/restore` | Restore backup |
| `DELETE` | `/api/backups/:id` | Delete backup |

### Download & Plugins

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/download/types` | List server types |
| `GET` | `/api/download/versions/:type` | List versions |
| `GET` | `/api/download/builds/:type/:version` | List builds |
| `POST` | `/api/download` | Download and create server |
| `GET` | `/api/plugins/search` | Search plugins |
| `POST` | `/api/plugins/install` | Install plugin |
| `GET` | `/api/servers/:id/plugins` | List installed plugins |
| `DELETE` | `/api/servers/:id/plugins/:file` | Delete plugin |

---

## Stack

- **Backend:** Flask, Flask-SocketIO, SQLite, Eventlet
- **Frontend:** Vanilla JavaScript (bundled via esbuild), xterm.js (read-only terminal + command input bar), Socket.IO client
- **Build:** esbuild (JS bundling + minify), csso (CSS minify)
- **Compression:** Automatic gzip for HTML/CSS/JS/JSON responses
- **Container:** Docker / Docker Compose

---

<div align="center">
  <p>
    <a href="https://github.com/enis1enis2/GreatPanel">GitHub</a> ·
    <a href="https://github.com/enis1enis2/GreatPanel/issues">Issues</a> ·
    <a href="https://github.com/enis1enis2/GreatPanel/discussions">Discussions</a>
  </p>
  <p>Built with ❤️ for the Minecraft server community</p>
</div>
