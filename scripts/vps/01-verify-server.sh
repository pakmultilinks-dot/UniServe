#!/usr/bin/env bash
# =============================================================================
# UniServe VPS Provisioning — Phase 1: Server Verification
#
# Run this FIRST on a fresh VPS to verify it meets documented requirements.
# Does NOT install anything. Read-only inspection.
#
# Usage: bash 01-verify-server.sh
# Exit code 0 = meets requirements, 1 = does NOT meet requirements
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; FAILURES=$((FAILURES + 1)); }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
info() { echo "  $1"; }

FAILURES=0

echo "=============================================="
echo " UniServe VPS Verification"
echo " $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""

# ---- Hostname ----
echo "--- Hostname ---"
HOSTNAME=$(hostname)
info "Hostname: $HOSTNAME"
pass "Hostname retrieved"
echo ""

# ---- OS Version ----
echo "--- Operating System ---"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    info "OS: ${PRETTY_NAME:-$ID $VERSION_ID}"
    info "ID: ${ID}"
    info "Version ID: ${VERSION_ID:-unknown}"
    info "Codename: ${VERSION_CODENAME:-unknown}"

    # Check Ubuntu 22.04+ or Debian 12+
    OS_OK=false
    if [ "$ID" = "ubuntu" ]; then
        MAJOR=$(echo "$VERSION_ID" | cut -d. -f1)
        MINOR=$(echo "$VERSION_ID" | cut -d. -f2)
        if [ "$MAJOR" -gt 22 ] || { [ "$MAJOR" -eq 22 ] && [ "$MINOR" -ge 4 ]; }; then
            OS_OK=true
            pass "Ubuntu $VERSION_ID meets minimum (22.04+)"
        else
            fail "Ubuntu $VERSION_ID is below minimum (22.04+)"
        fi
    elif [ "$ID" = "debian" ]; then
        MAJOR=$(echo "$VERSION_ID" | cut -d. -f1)
        if [ "$MAJOR" -ge 12 ]; then
            OS_OK=true
            pass "Debian $VERSION_ID meets minimum (12+)"
        else
            fail "Debian $VERSION_ID is below minimum (12+)"
        fi
    else
        fail "Unsupported OS: $ID (expected Ubuntu 22.04+ or Debian 12+)"
    fi
else
    fail "Cannot detect OS — /etc/os-release not found"
fi
echo ""

# ---- CPU ----
echo "--- CPU ---"
CPU_COUNT=$(nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo)
info "CPU cores: $CPU_COUNT"
if [ "$CPU_COUNT" -ge 2 ]; then
    pass "CPU meets minimum (2+ cores)"
else
    fail "CPU below minimum (need 2+ cores, got $CPU_COUNT)"
fi
echo ""

# ---- RAM ----
echo "--- RAM ---"
if command -v free &>/dev/null; then
    RAM_KB=$(free -k | awk '/^Mem:/{print $2}')
    RAM_GB=$((RAM_KB / 1024 / 1024))
    info "RAM: ${RAM_GB} GB ($((RAM_KB / 1024)) MB)"
    if [ "$RAM_GB" -ge 4 ]; then
        pass "RAM meets minimum (4 GB)"
    else
        fail "RAM below minimum (need 4 GB, got ${RAM_GB} GB)"
    fi
else
    fail "Cannot detect RAM (free command not found)"
fi
echo ""

# ---- Disk ----
echo "--- Disk ---"
DISK_INFO=$(df -h / | awk 'NR==2{print $2,$3,$4,$5}')
DISK_SIZE=$(df -h / | awk 'NR==2{print $2}')
DISK_USED=$(df -h / | awk 'NR==2{print $3}')
DISK_AVAIL=$(df -h / | awk 'NR==2{print $4}')
DISK_PCT=$(df -h / | awk 'NR==2{print $5}')

# Convert to GB for comparison
DISK_SIZE_RAW=$(df -BG / | awk 'NR==2{print $2}' | tr -d 'G')
DISK_AVAIL_RAW=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')

info "Disk size: $DISK_SIZE"
info "Disk used: $DISK_USED ($DISK_PCT)"
info "Disk available: $DISK_AVAIL"

if [ "$DISK_SIZE_RAW" -ge 40 ]; then
    pass "Disk meets minimum (40 GB)"
else
    fail "Disk below minimum (need 40 GB, got ${DISK_SIZE_RAW} GB)"
fi

if [ "$DISK_AVAIL_RAW" -ge 20 ]; then
    pass "Available disk space sufficient (${DISK_AVAIL_RAW} GB free)"
else
    warn "Available disk space is tight (${DISK_AVAIL_RAW} GB free)"
fi
echo ""

# ---- Architecture ----
echo "--- Architecture ---"
ARCH=$(uname -m)
info "Architecture: $ARCH"
if [ "$ARCH" = "x86_64" ]; then
    pass "Architecture is x86_64"
elif [ "$ARCH" = "aarch64" ]; then
    pass "Architecture is aarch64 (ARM64)"
else
    warn "Unusual architecture: $ARCH"
fi
echo ""

# ---- Public IP ----
echo "--- Public IP ---"
PUBLIC_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || curl -s --max-time 10 icanhazip.com 2>/dev/null || echo "unknown")
info "Public IP: $PUBLIC_IP"
if [ "$PUBLIC_IP" != "unknown" ]; then
    pass "Public IP detected: $PUBLIC_IP"
else
    warn "Could not detect public IP (may not have outbound internet)"
fi
echo ""

# ---- Docker ----
echo "--- Docker ---"
if command -v docker &>/dev/null; then
    DOCKER_VERSION=$(docker --version 2>/dev/null)
    info "Docker: $DOCKER_VERSION"
    pass "Docker is installed"

    # Check if running
    if docker info &>/dev/null 2>&1; then
        pass "Docker daemon is running"
    else
        warn "Docker is installed but daemon is not running"
    fi
else
    warn "Docker is not installed (will be installed in Phase 3)"
fi

if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
    COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || docker compose version 2>/dev/null)
    info "Docker Compose: $COMPOSE_VERSION"
    pass "Docker Compose plugin is installed"
else
    warn "Docker Compose plugin not detected (will be installed in Phase 3)"
fi
echo ""

# ---- SSH ----
echo "--- SSH ---"
if systemctl is-active sshd &>/dev/null 2>&1; then
    SSH_STATUS=$(systemctl is-active sshd)
    info "SSH service: $SSH_STATUS"
    pass "SSH is active"
elif systemctl is-active ssh &>/dev/null 2>&1; then
    SSH_STATUS=$(systemctl is-active ssh)
    info "SSH service: $SSH_STATUS"
    pass "SSH is active"
else
    warn "SSH service status unknown"
fi
info "SSH port: $(ss -tlnp 2>/dev/null | grep -E ':22\s' | head -1 || echo 'not detected')"
echo ""

# ---- Firewall ----
echo "--- Firewall ---"
if command -v ufw &>/dev/null; then
    UFW_STATUS=$(ufw status 2>/dev/null | head -1)
    info "UFW: $UFW_STATUS"
else
    info "UFW: not installed"
fi
if command -v iptables &>/dev/null; then
    IPTABLES_RULES=$(iptables -L -n 2>/dev/null | wc -l)
    info "iptables rules count: $IPTABLES_RULES"
fi
echo ""

# ---- Summary ----
echo "=============================================="
echo " SUMMARY"
echo "=============================================="
echo ""
info "Hostname: $HOSTNAME"
info "OS: ${PRETTY_NAME:-unknown}"
info "CPU: $CPU_COUNT cores"
info "RAM: ${RAM_GB:-?} GB"
info "Disk: $DISK_SIZE ($DISK_AVAIL available)"
info "Arch: $ARCH"
info "Public IP: $PUBLIC_IP"
info "Docker: ${DOCKER_VERSION:-not installed}"
info "Compose: ${COMPOSE_VERSION:-not installed}"
echo ""

if [ "$FAILURES" -eq 0 ]; then
    echo -e "${GREEN}ALL CHECKS PASSED — Server meets documented requirements.${NC}"
    exit 0
else
    echo -e "${RED}$FAILURES CHECK(S) FAILED — Server does NOT meet documented requirements.${NC}"
    echo -e "${RED}STOP — Do not proceed with provisioning.${NC}"
    exit 1
fi
