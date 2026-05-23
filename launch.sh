#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

info()  { printf "\n[INFO]  %s\n" "$1"; }
warn()  { printf "\n[WARN]  %s\n" "$1"; }
fatal() { printf "\n[FATAL] %s\n" "$1"; exit 1; }
confirm() {
    printf "\n[?] %s [y/N] " "$1"
    read -r ans
    case "$ans" in [yY]|[yY][eE][sS]) return 0 ;; *) return 1 ;; esac
}

trap 'printf "\n[!] Interrupted.\n"; exit 130' INT

# --- Find Python everywhere ---
PYTHON=""
for c in python3.14 python3.13 python3.12 python3.11 python3.10 \
         python3.9 python3.8 python3 python; do
    if command -v "$c" &>/dev/null; then
        ver=$("$c" --version 2>&1 | grep -oP '\d+\.\d+')
        if awk -v v="$ver" 'BEGIN{exit !(v >= 3.8)}'; then
            PYTHON="$c"; break
        fi
    fi
done
# Also check common paths directly
for d in /usr/bin /usr/local/bin "$HOME/.local/bin" /opt/homebrew/bin /opt/bin; do
    [ -n "$PYTHON" ] && break
    for c in python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
        p="$d/$c"
        if [ -x "$p" ]; then
            ver=$("$p" --version 2>&1 | grep -oP '\d+\.\d+')
            if awk -v v="$ver" 'BEGIN{exit !(v >= 3.8)}'; then
                PYTHON="$p"; break
            fi
        fi
    done
done

if [ -z "$PYTHON" ]; then
    warn "Python 3.8+ not found anywhere."
    if confirm "Install Python 3?"; then
        if command -v apt &>/dev/null; then
            sudo apt update && sudo apt install -y python3 python3-pip python3-venv
        elif command -v pacman &>/dev/null; then
            sudo pacman -Sy --noconfirm python python-pip
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y python3 python3-pip
        elif command -v apk &>/dev/null; then
            sudo apk add python3 py3-pip
        elif command -v brew &>/dev/null; then
            brew install python@3.12
        else
            fatal "Unsupported package manager. Install Python 3.8+ manually."
        fi
        PYTHON="python3"
    else
        fatal "Python 3 is required. Aborting."
    fi
fi

info "Using $($PYTHON --version 2>&1)"

# --- Java check ---
JAVA=""
for c in java java21 java17; do
    if command -v "$c" &>/dev/null; then
        ver=$("$c" -version 2>&1 | grep -oP '(?<=version ")\d+')
        if [ "$ver" -ge 17 ] 2>/dev/null; then
            JAVA="$c"; break
        fi
    fi
done
for d in /usr/lib/jvm/*/bin /usr/lib/jvm/java-*-openjdk-*/bin /opt/homebrew/opt/openjdk/bin; do
    [ -n "$JAVA" ] && break
    p="$d/java"
    if [ -x "$p" ]; then
        ver=$("$p" -version 2>&1 | grep -oP '(?<=version ")\d+')
        if [ "$ver" -ge 17 ] 2>/dev/null; then
            JAVA="$p"
        fi
    fi
done

if [ -z "$JAVA" ]; then
    warn "Java 17+ not found."
    if confirm "Install Java 21?"; then
        if command -v apt &>/dev/null; then
            sudo apt update && sudo apt install -y openjdk-21-jre-headless
        elif command -v pacman &>/dev/null; then
            sudo pacman -Sy --noconfirm jre21-openjdk-headless
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y java-21-openjdk-headless
        elif command -v brew &>/dev/null; then
            brew install openjdk@21
        else
            fatal "Unsupported package manager. Install Java 17+ manually."
        fi
        JAVA="java"
    else
        warn "Continuing without Java — servers will not start."
    fi
fi
if [ -n "$JAVA" ]; then
    info "Using $($JAVA -version 2>&1 | head -1)"
fi

# --- Python venv ---
if [ ! -d .venv ]; then
    info "Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi
source .venv/bin/activate

# --- Install deps ---
info "Installing Python dependencies..."
pip install --upgrade pip -q 2>/dev/null || true
pip install -r requirements.txt -q 2>/dev/null || true
info "Dependencies ready."

# --- Build static assets ---
if command -v node &>/dev/null; then
    if [ ! -f "static/js/windfall.min.js" ]; then
        if [ ! -f "node_modules/esbuild/package.json" ]; then
            npm install 2>/dev/null || true
        fi
        if [ -f "node_modules/esbuild/package.json" ]; then
            npm run build 2>/dev/null || true
        fi
    fi
fi

# --- Autostart setup ---
SERVICE_NAME="windfall-ecu"
SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME.service"
if confirm "Add Windfall ECU to startup?"; then
    mkdir -p "$HOME/.config/systemd/user"
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Windfall ECU — Minecraft Server Manager
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now "$SERVICE_NAME"
    info "Windfall ECU added to startup (systemd user service)."
    info "Manage: systemctl --user {start,stop,restart,status} $SERVICE_NAME"
fi

# --- Launch detached ---
printf "\n"
info "Starting Windfall ECU on http://0.0.0.0:8080"
echo "  Default login: admin / admin"
echo "  Panel running in background. Close this terminal safely."
printf "\n"

# Detach with setsid (preferred) or nohup
if command -v setsid &>/dev/null; then
    setsid "$PYTHON" "$SCRIPT_DIR/app.py" > /dev/null 2>&1 &
elif command -v nohup &>/dev/null; then
    nohup "$PYTHON" "$SCRIPT_DIR/app.py" > /dev/null 2>&1 &
else
    "$PYTHON" "$SCRIPT_DIR/app.py" > /dev/null 2>&1 &
fi
disown

# Check it started
sleep 2
if lsof -i :8080 -sTCP:LISTEN 2>/dev/null || ss -tlnp 2>/dev/null | grep -q :8080; then
    info "Windfall ECU is running on http://localhost:8080"
else
    warn "Panel may not have started. Check with: ps aux | grep app.py"
fi
