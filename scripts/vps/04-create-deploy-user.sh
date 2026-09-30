#!/usr/bin/env bash
# =============================================================================
# UniServe VPS Provisioning — Phase 4: Deployment User
#
# Creates a dedicated deployment user with Docker group access.
# Does NOT disable any security controls.
#
# Usage: bash 04-create-deploy-user.sh [username]
# Default username: deploy
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

DEPLOY_USER="${1:-deploy}"

echo "=============================================="
echo " UniServe VPS — Deployment User Setup"
echo " $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""
echo "Deployment username: $DEPLOY_USER"
echo ""

# Check if root
if [ "$(id -u)" -ne 0 ]; then
    fail "This script must be run as root (sudo bash $0)"
fi

# Check if user already exists
if id "$DEPLOY_USER" &>/dev/null 2>&1; then
    warn "User '$DEPLOY_USER' already exists — skipping creation"
else
    echo "[1/3] Creating deployment user..."
    useradd -m -s /bin/bash "$DEPLOY_USER"
    pass "User '$DEPLOY_USER' created"

    # Set a random password (user should change it)
    TEMP_PASS=$(openssl rand -base64 18)
    echo "$DEPLOY_USER:$TEMP_PASS" | chpasswd
    pass "Temporary password set (user should change it)"
    echo ""
    warn "TEMPORARY PASSWORD for $DEPLOY_USER: $TEMP_PASS"
    warn "Share this securely with the user. They should run: passwd"
    echo ""
fi

echo "[2/3] Adding to docker group..."
if getent group docker &>/dev/null; then
    usermod -aG docker "$DEPLOY_USER"
    pass "User '$DEPLOY_USER' added to docker group"
else
    fail "docker group not found — run 03-install-docker.sh first"
fi

echo ""
echo "[3/3] Verifying permissions..."

# Verify user can run docker (via group)
if sg docker -c "docker info" &>/dev/null 2>&1; then
    pass "User '$DEPLOY_USER' can run Docker commands"
else
    warn "Cannot verify Docker access (requires new login session to take effect)"
fi

# Create deployment directory
DEPLOY_DIR="/opt/uniserve"
if [ ! -d "$DEPLOY_DIR" ]; then
    mkdir -p "$DEPLOY_DIR"
    pass "Created $DEPLOY_DIR"
else
    pass "$DEPLOY_DIR already exists"
fi
chown "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_DIR"
pass "$DEPLOY_DIR owned by $DEPLOY_USER"

echo ""
echo "=============================================="
echo " Deployment user setup complete."
echo "=============================================="
echo ""
echo "User:     $DEPLOY_USER"
echo "Docker:   member of docker group"
echo "Directory: $DEPLOY_DIR"
echo ""
echo "IMPORTANT: The user needs to log out and back in for"
echo "docker group membership to take effect."
echo ""
echo "Next: Run 05-harden-ssh.sh"
