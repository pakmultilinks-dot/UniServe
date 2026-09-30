#!/usr/bin/env bash
# =============================================================================
# UniServe VPS Provisioning — Phase 8: Post-Reboot Verification
#
# Run this AFTER rebooting the VPS to verify everything came back correctly.
#
# Usage: bash 08-verify-after-reboot.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; FAILURES=$((FAILURES + 1)); }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

FAILURES=0

echo "=============================================="
echo " UniServe VPS — Post-Reboot Verification"
echo " $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""

# ---- Uptime ----
echo "--- System Uptime ---"
UPTIME=$(uptime -p 2>/dev/null || uptime)
info "Uptime: $UPTIME"
BOOT_TIME=$(who -b 2>/dev/null | awk '{print $3, $4}')
info "Last boot: $BOOT_TIME"
pass "System is running"
echo ""

# ---- SSH ----
echo "--- SSH Service ---"
if systemctl is-active sshd &>/dev/null 2>&1; then
    pass "SSH service is active"
else
    fail "SSH service is NOT active"
fi
if systemctl is-enabled sshd &>/dev/null 2>&1; then
    pass "SSH is enabled at boot"
else
    warn "SSH may not start at boot"
fi
echo ""

# ---- Docker ----
echo "--- Docker ---"
if systemctl is-active docker &>/dev/null 2>&1; then
    pass "Docker service is active"
else
    fail "Docker service is NOT active"
fi
if systemctl is-enabled docker &>/dev/null 2>&1; then
    pass "Docker is enabled at boot (auto-start)"
else
    fail "Docker is NOT enabled at boot"
fi
if docker info &>/dev/null 2>&1; then
    DOCKER_VERSION=$(docker --version)
    pass "Docker daemon responding: $DOCKER_VERSION"
else
    fail "Docker daemon not responding"
fi
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || docker compose version)
    pass "Docker Compose available: $COMPOSE_VERSION"
else
    fail "Docker Compose not available"
fi
echo ""

# ---- Firewall ----
echo "--- Firewall ---"
if command -v ufw &>/dev/null; then
    UFW_STATUS=$(ufw status 2>/dev/null | head -1)
    if echo "$UFW_STATUS" | grep -q "active"; then
        pass "UFW is active"
    else
        fail "UFW is NOT active"
    fi

    # Verify rules
    ufw status | grep -q "22/tcp" && pass "TCP 22 (SSH) allowed" || fail "TCP 22 (SSH) NOT allowed"
    ufw status | grep -q "80/tcp" && pass "TCP 80 (HTTP) allowed" || fail "TCP 80 (HTTP) NOT allowed"
    ufw status | grep -q "443/tcp" && pass "TCP 443 (HTTPS) allowed" || fail "TCP 443 (HTTPS) NOT allowed"

    # Verify blocked
    ufw status | grep -q "5432" && fail "PostgreSQL 5432 EXPOSED!" || pass "PostgreSQL (5432) not exposed"
    ufw status | grep -q ":8000" && fail "API 8000 EXPOSED!" || pass "API (8000) not exposed"
else
    fail "UFW not found"
fi
echo ""

# ---- Listening Ports ----
echo "--- Listening Ports (public-facing) ---"
PUBLIC_LISTEN=$(ss -tlnp 2>/dev/null | grep -v "127.0.0.1" | grep -v "::1" | awk '{print $4}' | sort -u)
echo "$PUBLIC_LISTEN" | sed 's/^/  /'
echo ""

# Check for unexpected listeners
if echo "$PUBLIC_LISTEN" | grep -q ":5432"; then
    fail "PostgreSQL is listening on a non-loopback address!"
else
    pass "PostgreSQL not listening publicly"
fi
if echo "$PUBLIC_LISTEN" | grep -q ":8000"; then
    fail "API is listening on a non-loopback address!"
else
    pass "API not listening publicly"
fi
echo ""

# ---- Deployment Directory ----
echo "--- Deployment Directory ---"
DEPLOY_DIR="/opt/uniserve"
if [ -d "$DEPLOY_DIR" ]; then
    pass "$DEPLOY_DIR exists"
    [ -d "$DEPLOY_DIR/backups" ] && pass "backups/ exists" || fail "backups/ missing"
else
    fail "$DEPLOY_DIR missing"
fi
if [ -f "$DEPLOY_DIR/.env.production" ]; then
    fail ".env.production exists — should NOT exist yet"
else
    pass ".env.production does NOT exist (correct)"
fi
echo ""

# ---- No Application Containers ----
echo "--- Application Containers ---"
APP_CONTAINERS=$(docker ps -a --format "{{.Names}}" 2>/dev/null | grep -E "uniserve" || echo "")
if [ -z "$APP_CONTAINERS" ]; then
    pass "No UniServe application containers exist (correct)"
else
    warn "Found containers: $APP_CONTAINERS"
    warn "Application should NOT be deployed yet in Phase 18"
fi
echo ""

# ---- Summary ----
echo "=============================================="
echo " POST-REBOOT VERIFICATION SUMMARY"
echo "=============================================="
echo ""
if [ "$FAILURES" -eq 0 ]; then
    echo -e "${GREEN}ALL CHECKS PASSED — Server is ready after reboot.${NC}"
    exit 0
else
    echo -e "${RED}$FAILURES CHECK(S) FAILED — Investigate before proceeding.${NC}"
    exit 1
fi