# GreatPanel

A lightweight Minecraft server management panel for arm64 Linux. Manage servers through a web UI.

## Quick Start

### Without Docker

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:8080

### With Docker

```bash
docker-compose up -d
```

Open http://localhost:8080

## Usage

1. **Create a server** — Click `+ New` in the sidebar, give it a name, then upload a server JAR through the Files tab.
2. **Import from ZIP** — Click `Import` in the sidebar or go to the Import tab and drop a `.zip` containing your server.
3. **Start** — Select the server and click `Start`. The terminal will show live console output.
4. **Manage** — Use the Files tab to edit configs, Backups tab to snapshot your world.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/servers` | List servers |
| POST | `/api/servers` | Create server |
| DELETE | `/api/servers/:id` | Delete server |
| POST | `/api/servers/:id/start` | Start server |
| POST | `/api/servers/:id/stop` | Stop server |
| GET | `/api/servers/:id/status` | Server status |
| GET | `/api/servers/:id/files` | List files |
| POST | `/api/servers/:id/files/write` | Save file |
| POST | `/api/servers/:id/files/delete` | Delete file |
| POST | `/api/servers/:id/files/upload` | Upload files |
| GET | `/api/servers/:id/backups` | List backups |
| POST | `/api/servers/:id/backups` | Create backup |
| POST | `/api/backups/:id/restore` | Restore backup |
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
