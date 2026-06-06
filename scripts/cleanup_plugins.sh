#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# Purpur 1.21.11 Plugin Cleanup & Replacement Script
# Removes wrong-loader JARs, downloads correct Bukkit/Paper versions
# ──────────────────────────────────────────────────────────────

PLUGINS_DIR="${1:-./plugins}"
[ -d "$PLUGINS_DIR" ] || { echo "Usage: $0 <plugins-dir>"; exit 1; }

echo "=== Step 1: Delete incorrect JARs ==="
declare -a DELETE=(
  'Chunky-Fabric-1.5.3.jar'
  'LuckPerms-Fabric-5.5.54.jar'
  'Geyser-Velocity.jar'
  'Floodgate-Neoforge-2.2.6-b63.jar'
  'SkinsRestorer-Mod-NeoForge-15.12.2.jar'
  'CustomNPCs-1.20.1-GBPort*'   # glob pattern
  'ESO_1.18.2_1.09.jar'
  'fpp-spoof-1.1.0.jar'
)

for pattern in "${DELETE[@]}"; do
  found=0
  for f in "$PLUGINS_DIR"/$pattern; do
    [ -f "$f" ] || continue
    rm -v "$f"
    found=1
  done
  [ "$found" -eq 0 ] && echo "  (not found: $pattern)"
done

echo ""
echo "=== Step 2: Download replacement Bukkit/Paper JARs ==="

# Helper: download via Modrinth API using project slug
# Usage: dl_modrinth <slug> <loader> <output-filename>
dl_modrinth() {
  local slug="$1" loader="$2" outfile="$3"
  local api="https://api.modrinth.com/v2"
  # Resolve project ID from slug
  local proj
  proj=$(curl -sf "$api/project/$slug" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  # Get latest version for this loader
  local ver_id
  ver_id=$(curl -sf "$api/project/$proj/version" | python3 -c "
import sys,json
data=json.load(sys.stdin)
for v in data:
    loaders=v.get('loaders',[])
    if '$loader' in loaders:
        print(v['id'])
        sys.exit(0)
print(data[0]['id'])
")
  # Get download URL
  local url
  url=$(curl -sf "$api/version/$ver_id" | python3 -c "
import sys,json
v=json.load(sys.stdin)
for f in v.get('files',[]):
    if f.get('primary'):
        print(f['url'])
        sys.exit(0)
print(v['files'][0]['url'])
")
  echo "  Downloading $outfile ..."
  curl -sfL "$url" -o "$PLUGINS_DIR/$outfile"
  echo "  Done: $(du -h "$PLUGINS_DIR/$outfile" | cut -f1)"
}

# Vault — use VaultUnlocked from Hangar (supports 1.13–1.21.10)
echo "  Downloading VaultUnlocked (Vault replacement) ..."
VAULT_URL="https://hangarcdn.papermc.io/plugins/TNE/VaultUnlocked/versions/2.17.0/PAPER/VaultUnlocked-2.17.0.jar"
curl -sfL "$VAULT_URL" -o "$PLUGINS_DIR/VaultUnlocked-2.17.0.jar" && \
  echo "  Done: $(du -h "$PLUGINS_DIR/VaultUnlocked-2.17.0.jar" | cut -f1)"

# Chunky (Bukkit)
dl_modrinth "chunky" "bukkit" "Chunky-Bukkit-1.5.3.jar"

# LuckPerms (Bukkit)
dl_modrinth "luckperms" "bukkit" "LuckPerms-Bukkit-5.5.54.jar"

# Geyser-Spigot
dl_modrinth "geyser" "bukkit" "Geyser-Spigot.jar"

# Floodgate-Spigot
dl_modrinth "floodgate" "bukkit" "Floodgate-Spigot.jar"

# SkinsRestorer (Bukkit)
dl_modrinth "skinsrestorer" "bukkit" "SkinsRestorer-Bukkit.jar"

# EssentialsX — full suite matching version 2.22.0
echo ""
echo "=== Step 3: Sync EssentialsX to consistent release ==="
ESS_BASE="https://github.com/EssentialsX/EssentialsX/releases/download/2.22.0.0"
ESS_PLUGINS=(
  "EssentialsX-2.22.0.0.jar"
  "EssentialsXSpawn-2.22.0.0.jar"
  "EssentialsXGeoIP-2.22.0.0.jar"
  "EssentialsXChat-2.22.0.0.jar"
  "EssentialsXProtect-2.22.0.0.jar"
  "EssentialsXAntiBuild-2.22.0.0.jar"
)

for jar_url in "${ESS_PLUGINS[@]}"; do
  fname=$(basename "$jar_url")
  # Remove existing Essentials jars with same base name
  base="${fname%%-2.22*}"
  for old in "$PLUGINS_DIR/$base"*.jar; do
    [ -f "$old" ] || continue
    rm -v "$old"
  done
  echo "  Downloading $fname ..."
  curl -sfL "$ESS_BASE/$fname" -o "$PLUGINS_DIR/$fname"
  echo "  Done: $(du -h "$PLUGINS_DIR/$fname" | cut -f1)"
done

echo ""
echo "=== Cleanup complete ==="
echo "Review the following for any remaining manual steps:"
echo "  - Restart your server (or run /reload confirm)"
echo "  - Verify with /plugins that all JARs loaded green"
echo "  - Check console for missing dependency errors"
echo ""
echo "Removed wrong variants:"
for p in "${DELETE[@]}"; do echo "  - $p"; done
echo ""
echo "Installed replacements:"
ls -1 "$PLUGINS_DIR"/{VaultUnlocked,Chunky-Bukkit,LuckPerms-Bukkit,Geyser-Spigot,Floodgate-Spigot,SkinsRestorer-Bukkit,EssentialsX*,EssentialsXSpawn*,EssentialsXGeoIP*,EssentialsXChat*,EssentialsXProtect*,EssentialsXAntiBuild*} 2>/dev/null | sed 's/^/  /'
