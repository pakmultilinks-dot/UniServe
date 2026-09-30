#!/usr/bin/env bash
# =============================================================================
# UniServe VPS Provisioning — Phase 6: Firewall Configuration
#
# Configures UFW firewall to only expose required ports:
#   - TCP 22 (SSH)
#   - TCP 80 (HTTP)
#   - TCP 443 (HTTPS)
#
# PostgreSQL (5432), API (8000), and dev ports are NOT exposed.
#
# Usage: bash 06-configure-firewall.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo "=============================================="
echo " UniServe VPS — Firewall Configuration"
echo " $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""

# Check if root
if [ "$(id -u)" -ne 0 ]; then
    fail "This script must be run as root (sudo bash $0)"
fi

# Check UFW exists
if ! command -v ufw &>/dev/null; then
    echo "[1/5] Installing UFW..."
    apt-get install -y ufw 2>&1 | tail -3
    pass "UFW installed"
else
    pass "UFW already installed"
fi

echo ""
echo "--- Current Firewall Status ---"
ufw status | head -5
echo ""

# Configure UFW
echo "[2/5] Configuring firewall rules..."

# Reset to defaults (allow outgoing, deny incoming)
ufw --force reset 2>&1 | tail -2
pass "Firewall reset to defaults"

# Default policies
ufw default deny incoming 2>&1 | tail -1
ufw default allow outgoing 2>&1 | tail -1
pass "Default policies: deny incoming, allow outgoing"

echo ""
echo "[3/5] Adding allowed ports..."

# SSH — MUST be allowed before enabling!
ufw allow 22/tcp comment 'SSH' 2>&1 | tail -1
pass "Allowed: TCP 22 (SSH)"

# HTTP
ufw allow 80/tcp comment 'HTTP' 2>&1 | tail -1
pass "Allowed: TCP 80 (HTTP)"

# HTTPS
ufw allow 443/tcp comment 'HTTPS' 2>&1 | tail -1
pass "Allowed: TCP 443 (HTTPS)"

echo ""
echo "[4/5] Enabling firewall..."

# Enable UFW — this is the critical step
# The --force flag skips the confirmation prompt
# SSH is already allowed, so we won't lock ourselves out
echo "Enabling UFW (SSH is already allowed, you will not be locked out)..."
ufw --force enable 2>&1
pass "Firewall enabled"

echo ""
echo "[5/5] Verifying firewall rules..."
echo ""

echo "--- Firewall Status ---"
ufw status verbose
echo ""

# Verify specific ports
echo "--- Verification ---"
ufw status | grep -q "22/tcp" && pass "TCP 22 (SSH) is allowed" || fail "TCP 22 (SSH) is NOT allowed"
ufw status | grep -q "80/tcp" && pass "TCP 80 (HTTP) is allowed" || fail "TCP 80 (HTTP) is NOT allowed"
ufw status | grep -q "443/tcp" && pass "TCP 443 (HTTPS) is allowed" || fail "TCP 443 (HTTPS) is NOT allowed"

# Verify blocked ports
ufw status | grep -q "5432" && fail "WARNING: PostgreSQL port 5432 appears to be exposed!" || pass "PostgreSQL (5432) is NOT exposed"
ufw status | grep -q "8000" && fail "WARNING: API port 8000 appears to be exposed!" || pass "API (8000) is NOT exposed"
ufw status | grep -q "6379" && fail "WARNING: Redis port 6379 appears to be exposed!" || pass "Redis (6379) is NOT exposed"
ufw status | grep -q "5433" && warn "Dev Postgres port 5433 appears in rules" || pass "Dev Postgres (5433) is NOT exposed"

echo ""
echo "=============================================="
echo " Firewall configuration complete."
echo "=============================================="
echo ""
echo "Publicly exposed ports:"
echo "  - TCP 22   (SSH)"
echo "  - TCP 80   (HTTP)"
echo "  - TCP 443  (HTTPS)"
echo ""
echo "Internal only (NOT exposed):"
echo "  - PostgreSQL 5432"
echo "  - API 8000"
echo "  - Redis 6379"
echo ""
echo "IMPORTANT: Keep this SSH session open and verify you can"
echo "still connect from a new session before closing this one."
echo ""
echo "Next: Run 07-prepare-deployment-dir.sh"
