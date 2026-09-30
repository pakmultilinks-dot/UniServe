#!/usr/bin/env bash
# =============================================================================
# UniServe VPS Provisioning — Phase 2: System Updates
#
# Updates all OS packages to latest. Does NOT install extra software.
#
# Usage: bash 02-system-update.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

echo "=============================================="
echo " UniServe VPS — System Update"
echo " $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""

# Check if root
if [ "$(id -u)" -ne 0 ]; then
    fail "This script must be run as root (sudo bash $0)"
fi

# Check apt exists
if ! command -v apt-get &>/dev/null; then
    fail "apt-get not found — this script is for Debian/Ubuntu"
fi

echo "[1/3] Updating package list..."
apt-get update -y 2>&1 | tail -3
pass "Package list updated"

echo ""
echo "[2/3] Upgrading packages..."
apt-get upgrade -y 2>&1 | tail -5
pass "Packages upgraded"

echo ""
echo "[3/3] Removing unnecessary packages..."
apt-get autoremove -y 2>&1 | tail -3
apt-get autoclean 2>&1 | tail -3
pass "Cleanup complete"

echo ""
echo "=============================================="
echo " System is up to date."
echo "=============================================="
echo ""
echo "Note: A reboot may be required if kernel packages were updated."
echo "Check with: cat /var/run/reboot-required 2>/dev/null || echo 'No reboot required'"
