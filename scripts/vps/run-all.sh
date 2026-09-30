#!/usr/bin/env bash
# =============================================================================
# UniServe VPS Provisioning — Master Script
#
# Runs all provisioning phases in order. Designed for a fresh Ubuntu 22.04 VPS.
#
# Usage:
#   bash run-all.sh                    # Run all phases interactively
#   bash run-all.sh --dry-run          # Show what would be done (no changes)
#   bash run-all.sh --skip-verify      # Skip server verification
#
# SAFETY: This script does NOT:
#   - Deploy the UniServe application
#   - Run database migrations
#   - Start Docker Compose
#   - Configure DNS
#   - Issue TLS certificates
#   - Create .env.production or production secrets
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
info() { echo "  $1"; }

DRY_RUN=false
SKIP_VERIFY=false

for arg in "$@"; do
    case $arg in
        --dry-run) DRY_RUN=true ;;
        --skip-verify) SKIP_VERIFY=true ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================================="
echo " UniServe VPS Provisioning — Master Script"
echo " $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""
echo "This script will:"
echo "  1. Verify server meets requirements"
echo "  2. Update system packages"
echo "  3. Install Docker Engine + Compose"
echo "  4. Create deployment user"
echo "  5. Harden SSH"
echo "  6. Configure firewall (ports 22, 80, 443 only)"
echo "  7. Prepare deployment directory"
echo ""
echo "This script will NOT:"
echo "  - Deploy the application"
echo "  - Run migrations"
echo "  - Start Docker Compose"
echo "  - Configure DNS or TLS"
echo "  - Create .env.production"
echo ""
echo "=============================================="
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}DRY RUN MODE — No changes will be made.${NC}"
    echo ""
fi

# Phase 1: Verify
if [ "$SKIP_VERIFY" = false ]; then
    echo "--- Phase 1: Server Verification ---"
    if [ "$DRY_RUN" = true ]; then
        info "Would run: $SCRIPT_DIR/01-verify-server.sh"
    else
        bash "$SCRIPT_DIR/01-verify-server.sh" || fail "Server verification failed — STOP"
    fi
    echo ""
else
    warn "Skipping server verification (--skip-verify)"
    echo ""
fi

# Phase 2: System Update
echo "--- Phase 2: System Update ---"
if [ "$DRY_RUN" = true ]; then
    info "Would run: $SCRIPT_DIR/02-system-update.sh"
else
    bash "$SCRIPT_DIR/02-system-update.sh" || fail "System update failed"
fi
echo ""

# Phase 3: Docker
echo "--- Phase 3: Docker Installation ---"
if [ "$DRY_RUN" = true ]; then
    info "Would run: $SCRIPT_DIR/03-install-docker.sh"
else
    bash "$SCRIPT_DIR/03-install-docker.sh" || fail "Docker installation failed"
fi
echo ""

# Phase 4: Deployment User
echo "--- Phase 4: Deployment User ---"
if [ "$DRY_RUN" = true ]; then
    info "Would run: $SCRIPT_DIR/04-create-deploy-user.sh deploy"
else
    bash "$SCRIPT_DIR/04-create-deploy-user.sh" deploy || fail "Deployment user creation failed"
fi
echo ""

# Phase 5: SSH Hardening
echo "--- Phase 5: SSH Hardening ---"
if [ "$DRY_RUN" = true ]; then
    info "Would run: $SCRIPT_DIR/05-harden-ssh.sh"
    info "(Password auth will NOT be disabled)"
else
    bash "$SCRIPT_DIR/05-harden-ssh.sh" || fail "SSH hardening failed"
fi
echo ""

# Phase 6: Firewall
echo "--- Phase 6: Firewall ---"
if [ "$DRY_RUN" = true ]; then
    info "Would run: $SCRIPT_DIR/06-configure-firewall.sh"
    info "Would allow: TCP 22, 80, 443"
else
    bash "$SCRIPT_DIR/06-configure-firewall.sh" || fail "Firewall configuration failed"
fi
echo ""

# Phase 7: Deployment Directory
echo "--- Phase 7: Deployment Directory ---"
if [ "$DRY_RUN" = true ]; then
    info "Would run: $SCRIPT_DIR/07-prepare-deployment-dir.sh"
    info "Would create: /opt/uniserve/{backups,infrastructure/caddy,infrastructure/database}"
else
    bash "$SCRIPT_DIR/07-prepare-deployment-dir.sh" || fail "Deployment directory prep failed"
fi
echo ""

echo "=============================================="
echo " PROVISIONING COMPLETE"
echo "=============================================="
echo ""
echo "Completed phases:"
echo "  [1] Server verification"
echo "  [2] System updates"
echo "  [3] Docker installation"
echo "  [4] Deployment user"
echo "  [5] SSH hardening"
echo "  [6] Firewall (22, 80, 443 only)"
echo "  [7] Deployment directory"
echo ""
echo "Next steps:"
echo "  1. REBOOT the VPS: sudo reboot"
echo "  2. Reconnect via SSH"
echo "  3. Run verification: bash $SCRIPT_DIR/08-verify-after-reboot.sh"
echo "  4. If all checks pass, the VPS is ready for Phase 19 (application deployment)"
echo ""
echo "DO NOT deploy the application yet. DNS, TLS, and .env.production"
echo "will be configured in the next phase."
echo ""
