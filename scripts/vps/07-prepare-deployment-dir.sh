#!/usr/bin/env bash
# =============================================================================
# UniServe VPS Provisioning — Phase 7: Deployment Directory
#
# Prepares the deployment directory structure. Does NOT clone the repo
# or create production secrets.
#
# Usage: bash 07-prepare-deployment-dir.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

DEPLOY_DIR="/opt/uniserve"

echo "=============================================="
echo " UniServe VPS — Deployment Directory Prep"
echo " $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""

# Check if root
if [ "$(id -u)" -ne 0 ]; then
    fail "This script must be run as root (sudo bash $0)"
fi

echo "[1/3] Creating directory structure..."

# Main deployment directory
mkdir -p "$DEPLOY_DIR"
pass "Created $DEPLOY_DIR"

# Subdirectories (from docker-compose.prod.yml and runbook)
mkdir -p "$DEPLOY_DIR/backups"
pass "Created $DEPLOY_DIR/backups"

mkdir -p "$DEPLOY_DIR/infrastructure/caddy/data"
mkdir -p "$DEPLOY_DIR/infrastructure/caddy/config"
pass "Created Caddy runtime directories"

mkdir -p "$DEPLOY_DIR/infrastructure/database/init"
pass "Created database init directory"

echo ""
echo "[2/3] Setting ownership..."

# Ownership: deploy user if it exists, otherwise keep root
DEPLOY_USER="deploy"
if id "$DEPLOY_USER" &>/dev/null 2>&1; then
    chown -R "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_DIR"
    pass "Set ownership to $DEPLOY_USER"
else
    warn "User '$DEPLOY_USER' not found — leaving as root"
    warn "Run 04-create-deploy-user.sh first for proper ownership"
fi

echo ""
echo "[3/3] Setting permissions..."

# Directory permissions: rwxr-xr-x (755)
chmod 755 "$DEPLOY_DIR"
pass "Set directory permissions to 755"

# Backup directory: only deploy user should write
if id "$DEPLOY_USER" &>/dev/null 2>&1; then
    chmod 700 "$DEPLOY_DIR/backups"
    pass "Set backups directory to 700 (owner-only)"
fi

echo ""
echo "--- Directory Structure ---"
ls -la "$DEPLOY_DIR/"
echo ""

# Verify
echo "--- Verification ---"
[ -d "$DEPLOY_DIR" ] && pass "$DEPLOY_DIR exists" || fail "$DEPLOY_DIR missing"
[ -d "$DEPLOY_DIR/backups" ] && pass "backups/ exists" || fail "backups/ missing"
[ -d "$DEPLOY_DIR/infrastructure/caddy/data" ] && pass "caddy/data/ exists" || fail "caddy/data/ missing"
[ -d "$DEPLOY_DIR/infrastructure/caddy/config" ] && pass "caddy/config/ exists" || fail "caddy/config/ missing"
[ ! -f "$DEPLOY_DIR/.env.production" ] && pass ".env.production does NOT exist (correct)" || fail ".env.production exists — it should not yet"

echo ""
echo "=============================================="
echo " Deployment directory ready."
echo "=============================================="
echo ""
echo "Directory: $DEPLOY_DIR"
echo "Structure:"
echo "  $DEPLOY_DIR/"
echo "  ├── backups/"
echo "  ├── infrastructure/caddy/{data,config}/"
echo "  └── infrastructure/database/init/"
echo ""
echo "NOTE: Application code has NOT been cloned yet."
echo "NOTE: No .env.production or secrets have been created."
echo ""
echo "Next: Run 08-verify-after-reboot.sh (after rebooting)"
