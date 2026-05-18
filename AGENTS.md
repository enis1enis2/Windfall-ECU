# Windfall ECU — Agent Guide

## Stack
- **Backend**: Flask, Flask-SocketIO (eventlet async), SQLite, Werkzeug
- **Frontend**: Vanilla JS, xterm.js, Socket.IO client, no framework
- **No tests, no linter, no type checker, no formatter** configured

## Run
```bash
pip install -r requirements.txt
python app.py
```
Server starts on `http://0.0.0.0:8080`. Default login: `admin`/`admin`.

> Use `setsid python3 app.py` or Docker to keep the server alive after the shell exits. The startup script kills leftover processes on port 8080 via `fuser`/`lsof`.

## Structure
| Path | Purpose |
|------|---------|
| `app.py` | Routes, server lifecycle, auth, all REST API handlers |
| `config.py` | Env-based config (`GREATPANEL_HOST`, `PORT`, `SECRET`, `JAVA`, `ORIGIN`) |
| `models.py` | SQLite ORM (servers, backups, settings, users tables) |
| `auth.py` | Session-based auth, default `admin`/`admin` user created on first run, user CRUD, role-based permission system (admin/operator/viewer) |
| `server_manager.py` | `ServerProcess` class — spawns Java via `subprocess.Popen`, console buffer, log tailing |
| `server_downloader.py` | Downloads Paper/Folia/Purpur/Vanilla/Fabric/Quilt/Forge/NeoForge JARs |
| `plugin_downloader.py` | Plugin search from Modrinth & Hangar; install only from Modrinth |
| `backup_manager.py` | tar.gz backup/restore per server |
| `file_explorer.py` | Path-restricted file CRUD under server dir |
| `terminal_handler.py` | WebSocket terminal I/O (connect_terminal, terminal_input) |
| `auto_backup.py` | Background scheduler for automatic backups (customizable interval, retention, enable/disable) |
| `docker_manager.py` | Docker container lifecycle (build/run/stop) |
| `zip_importer.py` | ZIP import with server type detection from JAR filename |
| `static/js/*.js` | One JS file per feature (app, backups, download, filemanager, import, plugins, terminal) |
| `templates/login.html` / `index.html` | Two Jinja2 templates |

## Key conventions
- All API routes except auth require `@login_required` (session cookie).
- `eventlet.monkey_patch()` must be the **very first import** in `app.py`.
- No migration system — `init_db()` in `models.py` creates tables on startup.
- Server processes are managed in-memory dict `_servers` keyed by DB id.
- File paths are always sanitized and checked against a base path prefix to prevent traversal.
- `SERVERS_DIR`/`BACKUPS_DIR` created on startup, entries are gitignored.
- `eula=true` written automatically on every server creation.

## Env vars
`GREATPANEL_SECRET`, `GREATPANEL_HOST`, `GREATPANEL_PORT`, `GREATPANEL_JAVA`, `GREATPANEL_ORIGIN`

## Docker
```bash
docker compose up -d
```
Dockerfile uses `python:3.12-slim` with OpenJDK 21 JRE.
