# Windfall ECU — Agent Guide

## Stack
- **Backend**: Flask, Flask-SocketIO (eventlet async), SQLite, Werkzeug
- **Frontend**: Vanilla JS (bundled to single file), xterm.js, Socket.IO client
- **Build**: esbuild (JS bundle + minify), csso (CSS minify)
- **Compression**: Automatic gzip for HTML/CSS/JS/JSON > 200 bytes
- **No tests, no linter, no type checker, no formatter** configured

## Run
```bash
# With static build (requires Node.js 18+, tested on 26.1):
npm install && npm run build
pip install -r requirements.txt
python app.py

# Without build (uses raw JS/CSS):
pip install -r requirements.txt
python app.py
```
Server starts on `http://0.0.0.0:8080`. Default login: `admin`/`admin`.

> Use `setsid python3 app.py` or Docker to keep the server alive after the shell exits. The startup script kills leftover processes on port 8080 via `fuser`/`lsof`. Launch scripts auto-detect Node.js and build assets on first run.

## Structure
| Path | Purpose |
|------|---------|
| `app.py` | Routes, server lifecycle, auth, all REST API handlers, gzip compression |
| `config.py` | Env-based config (`GREATPANEL_HOST`, `PORT`, `SECRET`, `JAVA`, `ORIGIN`) |
| `models.py` | SQLite ORM (servers, backups, settings, users tables) |
| `auth.py` | Session-based auth, default `admin`/`admin` user created on first run, user CRUD, role-based permission system (admin/operator/viewer) |
| `server_manager.py` | `ServerProcess` class — spawns Java via `subprocess.Popen`, console buffer, console output (stdout only) |
| `server_downloader.py` | Downloads Paper/Folia/Purpur/Vanilla/Fabric/Quilt/Forge/NeoForge JARs |
| `plugin_downloader.py` | Plugin search from Modrinth & Hangar; install only from Modrinth |
| `backup_manager.py` | tar.gz backup/restore per server |
| `file_explorer.py` | Path-restricted file CRUD under server dir |
| `terminal_handler.py` | WebSocket terminal I/O (connect_terminal, terminal_input) |
| `auto_backup.py` | Background scheduler for automatic backups (customizable interval, retention, enable/disable) |
| `docker_manager.py` | Docker container lifecycle (build/run/stop) |
| `zip_importer.py` | ZIP import with server type detection from JAR filename |
| `update_manager.py` | Git fetch/pull, pip install, restart for panel self-update |
| `path_util.py` | Shared path safety (`safe_join`, `safe_path`, `safe_write`, `sanitize_name`) |
| `build.sh` | Static asset build script (bundles JS via esbuild, minifies CSS via csso) |
| `package.json` | Node.js dev dependencies (esbuild, csso) + `npm run build` |
| `static/js/windfall.min.js` | All 7 JS files bundled and minified into one (39 KB) |
| `static/css/style.min.css` | Minified CSS (15 KB) |
| `static/js/*.js` | Individual JS source files (app, backups, download, filemanager, import, plugins, terminal) |
| `templates/login.html` / `index.html` | Two Jinja2 templates |

## Key conventions
- All API routes except auth require `@login_required` (session cookie).
- `eventlet.monkey_patch()` must be the **very first import** in `app.py`.
- No migration system — `init_db()` in `models.py` creates tables on startup.
- Server processes are managed in-memory dict `_servers` keyed by DB id.
- File paths are always sanitized and checked against a base path prefix to prevent traversal. All user-controlled path construction uses `safe_join` from `path_util.py` (raises ValueError on traversal) instead of raw `os.path.join` + manual prefix check. Fixed CodeQL path traversal alerts in `plugin_downloader.py` (delete_plugin) and `backup_manager.py` (create_backup) — both now use `safe_join` + `sanitize_name`.
- `SERVERS_DIR`/`BACKUPS_DIR` created on startup, entries are gitignored.
- `eula=true` written automatically on every server creation.
- Static assets are built via `npm run build` (`build.sh`). The app falls back to source files if built files are missing.
- Launch scripts (`launch.sh`/`launch.bat`) auto-build if Node.js is detected.
- All text responses (HTML/CSS/JS/JSON) are gzip-compressed via `app.py:after_request`.
- `index.html` references `windfall.min.js` and `style.min.css` instead of 7 separate JS files.
- Terminal redesigned to Pterodactyl-style layout: read-only xterm display, command input bar at bottom with `>` prompt, connection status dot indicator, no status bar. Terminal theme reads from CSS variables and respects light/dark mode (16 ANSI colors per theme, Pterodactyl-inspired palettes).
- Secret admin panel hidden behind double-click on sidebar header ("Windfall ECU") — only accessible to admin role users. Shows system info, disk usage, user/server stats, uptime.

## Env vars
`GREATPANEL_SECRET`, `GREATPANEL_HOST`, `GREATPANEL_PORT`, `GREATPANEL_JAVA`, `GREATPANEL_ORIGIN`

## Docker
```bash
docker compose up -d
```
Dockerfile uses multi-stage build: Node.js 22 builder produces minified assets, then `python:3.12-slim` with OpenJDK 21 JRE runs the app.
