<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/Windfall%20ECU-Minecraft%20Server%20Manager-818cf8?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM4MThjZjgiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTIgM2ExIDEgMCAwIDEgMSAxdjE2YTEgMSAwIDAgMS0yIDBWNGEgMSAxIDAgMCAxIDEtMXoiLz48cGF0aCBkPSJNNSA4YTEgMSAwIDAgMSAxIDF2NmExIDEgMCAwIDEtMiAwVjlhIDEgMSAwIDAgMSAxLTF6Ii8+PHBhdGggZD0iTTE5IDhhMSAxIDAgMCAxIDEgMXY2YTEgMSAwIDAgMS0yIDBWOWExIDEgMCAwIDEgMS0xeiIvPjwvc3ZnPg==">
    <img src="https://img.shields.io/badge/Windfall%20ECU-Minecraft%20Server%20Manager-3b82f6?style=for-the-badge" alt="Windfall ECU">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/enis1enis2/Windfall-ECU/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-3b82f6?style=flat-square" alt="License"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.8%2B-3b82f6?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://flask.palletsprojects.com"><img src="https://img.shields.io/badge/flask-3.1-3b82f6?style=flat-square&logo=flask&logoColor=white" alt="Flask"></a>
  <a href="https://docker.com"><img src="https://img.shields.io/badge/docker-ready-3b82f6?style=flat-square&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="https://github.com/enis1enis2/Windfall-ECU/actions"><img src="https://img.shields.io/github/actions/workflow/status/enis1enis2/Windfall-ECU/autofix.yml?style=flat-square&branch=main" alt="CI"></a>
</p>

<p align="center">
  A self-hosted web panel for managing Minecraft servers — start, stop, configure, back up, and update entirely from your browser.
</p>

---

## Features

- **Server Lifecycle** — Start, stop, restart, delete servers from the browser
- **Web Terminal** — Pterodactyl-style live console with WebSocket + polling fallback
- **File Manager** — Browse, edit, upload, delete server files
- **Backup System** — Create, restore, delete `.tar.gz` backups with auto-scheduler
- **Plugin Manager** — Search and install from Modrinth with automatic update tracking
- **Server Downloader** — Paper, Folia, Purpur, Vanilla, Fabric, Quilt, Forge, NeoForge
- **ZIP Import** — Drag-and-drop import with chunked upload support (>10MB)
- **Server Discovery** — Auto-registers existing server directories
- **Admin Dashboard** — System metrics, process list, storage breakdown, discovery log
- **Role-Based Access** — Admin, operator, viewer roles with granular permissions
- **Docker Support** — Run servers in isolated containers

---

## Quick start

```bash
git clone https://github.com/enis1enis2/Windfall-ECU.git
cd Windfall-ECU

# (Optional) Build optimized assets — requires Node.js 18+
npm install && npm run build

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python app.py
```

Open **http://localhost:8080** — default login `admin`/`admin`.

> Or run `./launch.sh` for an interactive setup with dependency checks and autostart.

---

## Docker

```bash
docker compose up -d
```

Multi-stage build: Node.js 22 → `python:3.12-slim` + OpenJDK 21 JRE. Server data and backups in mounted volumes.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GREATPANEL_SECRET` | `windfall-ecu-secret-change-me` | Flask session secret |
| `GREATPANEL_HOST` | `0.0.0.0` | Bind address |
| `GREATPANEL_PORT` | `8080` | HTTP port |
| `GREATPANEL_JAVA` | `java` | Java binary path |
| `GREATPANEL_ORIGIN` | `http://localhost:8080` | CORS origin |

---

## API

All endpoints except auth require session cookie auth.

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/auth/status` | Check auth status |
| `POST` | `/api/auth/login` | Log in |
| `POST` | `/api/auth/logout` | Log out |

### Servers

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/servers` | List servers |
| `POST` | `/api/servers` | Create server |
| `GET` | `/api/servers/:id` | Get server |
| `DELETE` | `/api/servers/:id` | Delete server |
| `POST` | `/api/servers/:id/start` | Start server |
| `POST` | `/api/servers/:id/stop` | Stop server |
| `POST` | `/api/servers/:id/restart` | Restart server |
| `POST` | `/api/servers/:id/upgrade` | Upgrade JAR |
| `GET` | `/api/servers/:id/status` | Running status |
| `PUT` | `/api/servers/:id/java_args` | Update JVM args |
| `PUT` | `/api/servers/:id/type` | Update server type |
| `PUT` | `/api/servers/:id/version` | Update game version |
| `GET` | `/api/servers/:id/console?since=N` | Console output |

### Files

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/servers/:id/files` | List files |
| `GET` | `/api/servers/:id/files/read` | Read file |
| `POST` | `/api/servers/:id/files/write` | Write file |
| `POST` | `/api/servers/:id/files/delete` | Delete file |
| `POST` | `/api/servers/:id/files/mkdir` | Create directory |
| `POST` | `/api/servers/:id/files/upload` | Upload file |
| `GET` | `/api/servers/:id/files/download` | Download file |

### Backups

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/servers/:id/backups` | List backups |
| `POST` | `/api/servers/:id/backups` | Create backup |
| `POST` | `/api/backups/:id/restore` | Restore backup |
| `DELETE` | `/api/backups/:id` | Delete backup |

### Plugins

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/plugins/search?q=&server_type=&game_version=` | Search Modrinth |
| `GET` | `/api/plugins/versions/:provider/:project_id` | List versions |
| `POST` | `/api/plugins/install` | Install plugin |
| `GET` | `/api/servers/:id/plugins` | List installed |
| `GET` | `/api/servers/:id/plugins/updates` | Check updates |
| `POST` | `/api/servers/:id/plugins/update` | Update plugin |
| `DELETE` | `/api/servers/:id/plugins/:file` | Delete plugin |

### Downloader

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/download/types` | Server types |
| `GET` | `/api/download/versions/:type` | Versions |
| `GET` | `/api/download/builds/:type/:version` | Builds |
| `POST` | `/api/download` | Download & create |

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/system/metrics` | RAM/CPU/Disk |
| `GET` | `/api/admin/info` | Full admin info |
| `GET` | `/api/update/check` | Check panel updates |
| `POST` | `/api/update/install` | Update & restart |

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask, Flask-SocketIO, Eventlet, SQLite |
| Frontend | Vanilla JS + esbuild bundle, xterm.js, Socket.IO |
| Build | esbuild (JS), csso (CSS) |
| Compression | Automatic gzip >200B |
| Container | Docker / Compose |

---

<p align="center">
  <a href="https://github.com/enis1enis2/Windfall-ECU">GitHub</a>
  ·
  <a href="https://github.com/enis1enis2/Windfall-ECU/issues">Issues</a>
  ·
  <a href="https://github.com/enis1enis2/Windfall-ECU/discussions">Discussions</a>
</p>
