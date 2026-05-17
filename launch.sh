#!/usr/bin/env bash
set -e

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

trap 'printf "\n[!] Script interrupted.\n"; exit 130' INT

# --- Python check ---
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1 | grep -oP '\d+\.\d+')
        if awk -v v="$ver" 'BEGIN{exit !(v >= 3.8)}'; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    warn "Python 3.8+ not found."
    if confirm "Install Python 3?"; then
        if command -v apt &>/dev/null; then
            sudo apt update && sudo apt install -y python3 python3-pip python3-venv
        elif command -v pacman &>/dev/null; then
            sudo pacman -Sy --noconfirm python python-pip
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y python3 python3-pip
        elif command -v apk &>/dev/null; then
            sudo apk add python3 py3-pip
        else
            fatal "Unsupported package manager. Install Python 3 manually."
        fi
        PYTHON="python3"
    else
        fatal "Python 3 is required. Aborting."
    fi
fi

info "Using $($PYTHON --version)"

# --- Java check ---
JAVA=""
for candidate in java java21 java17; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -version 2>&1 | grep -oP '(?<=version ")\d+')
        if [ "$ver" -ge 17 ] 2>/dev/null; then
            JAVA="$candidate"
            break
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
        else
            fatal "Unsupported package manager. Install Java 17+ manually."
        fi
        JAVA="java"
    else
        warn "Continuing without Java — server processes will not start."
    fi
fi

if [ -n "$JAVA" ]; then
    info "Using $($JAVA -version 2>&1 | head -1)"
fi

# --- Python venv ---
if [ ! -d .venv ]; then
    info "Creating Python virtual environment..."
    $PYTHON -m venv .venv
fi

source .venv/bin/activate

# --- Install pip deps ---
info "Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

info "All dependencies installed."

# --- Autostart setup ---
SERVICE_NAME="greatpanel"
SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME.service"
if confirm "Add GreatPanel to startup?"; then
    mkdir -p "$HOME/.config/systemd/user"
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=GreatPanel — Minecraft Server Manager
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
    info "GreatPanel will start automatically on login."
    info "Manage it with: systemctl --user {start,stop,restart,status} $SERVICE_NAME"
fi

# --- Launch ---
printf "\n"
info "Starting GreatPanel on http://localhost:8080"
echo "  Default login: admin / admin"
printf "\n"
if ! $PYTHON app.py; then
    fatal "GreatPanel exited with an error."
fi
