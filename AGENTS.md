# Windfall ECU

Minecraft server management panel — Flask backend, vanilla JS frontend.

## Quick reference

| Command | Description |
|---------|-------------|
| `python app.py` | Start server on `:8080` |
| `npm run build` | Bundle JS + minify CSS |
| `python -m py_compile *.py` | Verify syntax |

## Stack

- **Backend**: Flask, Flask-SocketIO (eventlet), SQLite
- **Frontend**: Vanilla JS, xterm.js, Socket.IO client
- **Build**: esbuild (JS), csso (CSS)
- **Compression**: Automatic gzip for text responses >200B

## Structure

| Path | Purpose |
|------|---------|
| `app.py` | Routes, lifecycle, auth, REST API, gzip |
| `config.py` | Env-based config |
| `models.py` | SQLite ORM |
| `auth.py` | Session auth, roles (admin/operator/viewer) |
| `server_manager.py` | Java process lifecycle |
| `server_downloader.py` | Paper/Folia/Purpur/Vanilla/Fabric/Quilt/Forge/NeoForge |
| `plugin_downloader.py` | Plugin search from Modrinth |
| `backup_manager.py` | tar.gz backup/restore |
| `file_explorer.py` | Path-restricted file CRUD |
| `terminal_handler.py` | WebSocket terminal I/O |
| `auto_backup.py` | Background backup scheduler |
| `docker_manager.py` | Docker lifecycle |
| `zip_importer.py` | ZIP import with chunked upload |
| `discovery.py` | Background directory scanner |
| `update_manager.py` | Git pull + pip + restart |
| `path_util.py` | Path safety (`safe_join`, `sanitize_name`) |

## Key conventions

- No tests. No test frameworks, directories, or dependencies.
- All routes except auth require `@login_required` (session cookie).
- `eventlet.monkey_patch()` must be the very first import in `app.py`.
- `init_db()` creates tables on startup — no migration system.
- Server processes are managed in-memory dict `_servers` keyed by DB id.
- All user-controlled paths use `safe_join` to prevent traversal.
- `SERVERS_DIR`/`BACKUPS_DIR` created on startup, gitignored.
- `eula=true` written on every server creation.
- Discovery polls `SERVERS_DIR` every 5s, skips `_dl_*` dirs.
- Import: direct (≤10MB) or chunked (4MB chunks, 3 retries).
- Static assets built via `npm run build`; falls back to source files.
- Admin panel: four-tab dashboard via `GET /api/admin/info`.
- Live metrics poll every 2s (RAM/CPU/Disk).
- CI validates syntax, `str(e)` audit, `os.path.join` audit on every push.
- `get_db()` context manager for all DB access.
- Port freed via `fuser -k PORT/tcp` before starting servers.
- No `formatSize`/`formatBytes` duplication (use from `app.js`).

## Env vars

`GREATPANEL_SECRET`, `GREATPANEL_HOST`, `GREATPANEL_PORT`, `GREATPANEL_JAVA`, `GREATPANEL_ORIGIN`

## Docker

```bash
docker compose up -d
```
Multi-stage: Node 22 builder → `python:3.12-slim` + OpenJDK 21 JRE.
