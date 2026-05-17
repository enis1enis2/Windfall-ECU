# GreatPanel

A self-hosted web-based Minecraft server management panel. Start, stop, configure, back up, and update Minecraft servers entirely from your browser.

## Features

- **Server Lifecycle** — Start, stop, restart, and delete servers with a single click
- **Web Terminal** — Live server console via WebSocket + xterm.js with polling fallback
- **File Manager** — Browse, edit, upload, and delete server files
- **Backup System** — Create, restore, and delete `.tar.gz` backups
- **Plugin Manager** — Search and install plugins from Modrinth and Hangar
- **Server Downloader** — Download Paper, Folia, Purpur, Vanilla, Fabric, Quilt, Forge, and NeoForge
- **Auto-Upgrade** — Upgrade server JARs to the latest version with automatic backup
- **ZIP Import** — Import existing server directories via drag-and-drop ZIP upload
- **Server Properties Editor** — Edit `server.properties` directly from the UI
- **Authentication** — Login/register system with session-based auth (default: `admin`/`admin`)
- **Dark/Light Theme** — Toggle between dark and light mode (persisted in localStorage)
- **Docker Support** — Run servers in isolated Docker containers
- **EULA Auto-Create** — `eula=true` written automatically on server creation
- **Launch Arguments** — Customize JVM arguments per server

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:8080 in your browser.

**Default login:** username `admin`, password `admin`

> ⚠️ Change the default password after first login by registering a new user or directly editing the database.

### Configuration via Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GREATPANEL_SECRET` | `greatpanel-secret-change-me` | Flask secret key for sessions |
| `GREATPANEL_HOST` | `0.0.0.0` | Web server bind address |
| `GREATPANEL_PORT` | `8080` | Web server port |
| `GREATPANEL_JAVA` | `java` | Java binary path |
| `GREATPANEL_ORIGIN` | `http://localhost:8080` | CORS allowed origin |

### Docker

```bash
docker compose up -d
```

### First Run

On first launch, an `admin` user is created automatically with password `admin`.
All API routes (except auth endpoints) require authentication via session cookie.
Use the login page at `http://localhost:8080` or the auth API.

## API Endpoints

*All endpoints except auth require authentication (session cookie).*

### Auth
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | Check authentication status |
| POST | `/api/auth/login` | Log in (body: `{"username", "password"}`) |
| POST | `/api/auth/register` | Register new user (body: `{"username", "password"}`) |
| POST | `/api/auth/logout` | Log out |

### Servers
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/servers` | List all servers |
| POST | `/api/servers` | Create a server |
| GET | `/api/servers/:id` | Get server details |
| DELETE | `/api/servers/:id` | Delete server and files |
| POST | `/api/servers/:id/start` | Start server |
| POST | `/api/servers/:id/stop` | Stop server |
| POST | `/api/servers/:id/restart` | Restart server |
| POST | `/api/servers/:id/upgrade` | Upgrade server JAR to latest version |
| GET | `/api/servers/:id/status` | Server running status |
| PUT | `/api/servers/:id/java_args` | Update JVM launch arguments |
| GET | `/api/servers/:id/console?since=N` | Get console output since line N |
| GET | `/api/servers/:id/files` | List server files |
| GET | `/api/servers/:id/files/read` | Read file content |
| POST | `/api/servers/:id/files/write` | Write file |
| POST | `/api/servers/:id/files/delete` | Delete file or directory |
| POST | `/api/servers/:id/files/mkdir` | Create directory |
| POST | `/api/servers/:id/files/upload` | Upload files |
| GET | `/api/servers/:id/files/download` | Download a file |
| GET | `/api/servers/:id/backups` | List backups |
| POST | `/api/servers/:id/backups` | Create backup |
| POST | `/api/backups/:id/restore` | Restore backup |
| DELETE | `/api/backups/:id` | Delete backup |
| GET | `/api/download/types` | List server download types |
| GET | `/api/download/versions/:type` | List versions for type |
| GET | `/api/download/builds/:type/:version` | List builds for version |
| POST | `/api/download` | Download and create server |
| GET | `/api/plugins/search` | Search plugins |
| POST | `/api/plugins/install` | Install plugin |
| GET | `/api/servers/:id/plugins` | List installed plugins |
| DELETE | `/api/servers/:id/plugins/:file` | Delete plugin |
| POST | `/api/import/zip` | Import server from ZIP |
| GET | `/api/system/docker` | Check Docker availability |

## Stack

- **Backend**: Flask, Flask-SocketIO, SQLite, Eventlet
- **Frontend**: Vanilla JavaScript, xterm.js, Socket.IO client
- **Container**: Docker / Docker Compose

## License

MIT
