#!/usr/bin/env bash
# =============================================================================
# UniServe VPS Provisioning — Phase 3: Docker Installation
#
# Installs Docker Engine and Docker Compose plugin using official method.
# Configures Docker to start automatically after reboot.
#
# Usage: bash 03-install-docker.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

echo "=============================================="
echo " UniServe VPS — Docker Installation"
echo " $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""

# Check if root
if [ "$(id -u)" -ne 0 ]; then
    fail "This script must be run as root (sudo bash $0)"
fi

# Check if Docker is already installed
if command -v docker &>/dev/null; then
    EXISTING_VERSION=$(docker --version 2>/dev/null)
    echo "Docker is already installed: $EXISTING_VERSION"
    echo "Skipping installation. Verifying instead..."
    echo ""
else
    echo "[1/4] Installing Docker Engine..."
    echo ""

    # Install prerequisites
    apt-get install -y ca-certificates curl gnupg 2>&1 | tail -3
    pass "Prerequisites installed"

    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    pass "Docker GPG key installed"

    # Add Docker repository
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
        https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list
    pass "Docker repository added"

    # Install Docker
    apt-get update -y 2>&1 | tail -2
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin 2>&1 | tail -5
    pass "Docker Engine and Compose plugin installed"
fi

echo ""
echo "[2/4] Verifying installation..."

DOCKER_VERSION=$(docker --version)
pass "Docker: $DOCKER_VERSION"

COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || docker compose version)
pass "Docker Compose: $COMPOSE_VERSION"

echo ""
echo "[3/4] Starting Docker and enabling auto-start..."

# Start Docker
systemctl start docker 2>&1
systemctl enable docker 2>&1
pass "Docker service enabled (starts on boot)"

# Verify running
if docker info &>/dev/null 2>&1; then
    pass "Docker daemon is running"
else
    fail "Docker daemon failed to start"
fi

echo ""
echo "[4/4] Running Docker test..."

# Harmless test: run a container that prints and exits
docker run --rm hello-world 2>&1 | head -10
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    pass "Docker container execution works"
else
    fail "Docker container execution failed"
fi

echo ""
echo "=============================================="
echo " Docker installation complete."
echo "=============================================="
echo ""
echo "Docker:    $DOCKER_VERSION"
echo "Compose:   $COMPOSE_VERSION"
echo "Auto-start: enabled"
echo ""
echo "Next: Run 04-create-deploy-user.sh"
