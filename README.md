# GreatPanel

A lightweight Minecraft server management panel for arm64 Linux. Manage servers through a web UI.

## Quick Start

### Without Docker

```bash
python -m venv .venv
source .venv/bin/activate     # Linux/Mac
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
python app.py
```

Open http://localhost:8080

### With Docker

```bash
docker-compose up -d
```

Open http://localhost:8080

## Features

### Server Management
- **Create** — Download server jars directly for Paper, Folia, Purpur, Vanilla, Fabric, Quilt, Forge, NeoForge
- **Import ZIP** — Upload existing server directories
- **Start/Stop** — One-click controls per server
- **Terminal** — Live console via WebSocket + REST polling, ANSI/Minecraft color stripped
- **Launch Arguments** — Editable JVM args per server
- **Files** — Browse, edit, upload, and delete server files
- **Backups** — Create and restore world snapshots

### Server Downloader
- Supports **Paper**, **Folia**, **Purpur**, **Vanilla**, **Fabric**, **Quilt**, **Forge**, **NeoForge**
- Versions fetched from official APIs (PaperMC, PurpurMC, Mojang, FabricMC, QuiltMC, NeoForged Maven, Forge)
- Build selection for Paper, Folia, Purpur
- Latest build auto-selected when none chosen

### Plugin Downloader
- Search **Modrinth** and **Hangar** simultaneously
- Results filtered by server type (Bukkit/Paper/Purpur/Spigot for Paper-family, Fabric, Quilt, NeoForge, Forge)
- Plugin install downloads directly to the server's `plugins/` directory
- Installed plugin listing with delete support

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/servers` | List servers |
| POST | `/api/servers` | Create server |
| GET | `/api/servers/:id` | Get server details |
| DELETE | `/api/servers/:id` | Delete server |
| POST | `/api/servers/:id/start` | Start server |
| POST | `/api/servers/:id/stop` | Stop server |
| GET | `/api/servers/:id/status` | Server status |
| GET | `/api/servers/:id/console` | Terminal output (since=N) |
| POST | `/api/servers/:id/console` | Send command |
| PUT | `/api/servers/:id/java_args` | Update JVM args |
| GET | `/api/servers/:id/files` | List files |
| POST | `/api/servers/:id/files/write` | Save file |
| POST | `/api/servers/:id/files/delete` | Delete file |
| POST | `/api/servers/:id/files/upload` | Upload files |
| GET | `/api/servers/:id/backups` | List backups |
| POST | `/api/servers/:id/backups` | Create backup |
| POST | `/api/backups/:id/restore` | Restore backup |
| GET | `/api/download/types` | List server types |
| GET | `/api/download/versions/:type` | List versions |
| GET | `/api/download/builds/:type/:version` | List builds |
| POST | `/api/download` | Download & create server |
| GET | `/api/plugins/search` | Search plugins (?q=&server_type=) |
| GET | `/api/plugins/versions/:provider/:id` | List plugin versions |
| POST | `/api/plugins/install` | Install plugin |
| GET | `/api/servers/:id/plugins` | List installed plugins |
| DELETE | `/api/servers/:id/plugins/:file` | Delete plugin |
| POST | `/api/import/zip` | Import server ZIP |

## Stack

- **Backend:** Python, Flask, Flask-SocketIO, eventlet
- **Frontend:** Vanilla JS, xterm.js, Socket.IO client
- **Storage:** SQLite (servers, backups, settings)
- **Protocol:** REST API + WebSocket for terminal I/O

## Requirements

- Python 3.10+
- Java 17+ (to run Minecraft servers)
- Works on arm64 (Raspberry Pi, Oracle ARM, Apple Silicon) and x86_64
