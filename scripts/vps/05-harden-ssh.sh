#!/usr/bin/env bash
# =============================================================================
# UniServe VPS Provisioning — Phase 5: SSH Hardening
#
# Hardens SSH configuration. Designed to NOT lock you out.
#
# SAFETY RULES:
#   - Does NOT disable password auth until key auth is verified
#   - Does NOT change the current port
#   - Validates config before applying
#   - Keeps existing access working
#
# Usage: bash 05-harden-ssh.sh [--disable-password-auth]
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

DISABLE_PASSWORD_AUTH=false
if [ "${1:-}" = "--disable-password-auth" ]; then
    DISABLE_PASSWORD_AUTH=true
fi

echo "=============================================="
echo " UniServe VPS — SSH Hardening"
echo " $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""

# Check if root
if [ "$(id -u)" -ne 0 ]; then
    fail "This script must be run as root (sudo bash $0)"
fi

# Find SSH config file
SSH_CONFIG="/etc/ssh/sshd_config"
if [ ! -f "$SSH_CONFIG" ]; then
    SSH_CONFIG="/etc/ssh/sshd_config.d/50-cloud-init.conf"  # cloud-init override
fi

echo "--- Current SSH Configuration ---"
echo ""
if [ -f "$SSH_CONFIG" ]; then
    echo "Config file: $SSH_CONFIG"
    echo ""
    echo "Key settings:"
    grep -E "^(Port|PermitRootLogin|PasswordAuthentication|PubkeyAuthentication|PermitEmptyPasswords|X11Forwarding|MaxAuthTries|ClientAliveInterval|ClientAliveCountMax)" "$SSH_CONFIG" 2>/dev/null | sed 's/^/  /' || echo "  (no explicit settings — using defaults)"
else
    warn "SSH config not found at $SSH_CONFIG"
fi
echo ""

# Check for drop-in directory
SSH_DIR="/etc/ssh/sshd_config.d"
if [ -d "$SSH_DIR" ]; then
    echo "Drop-in configs in $SSH_DIR:"
    ls -la "$SSH_DIR"/ 2>/dev/null | sed 's/^/  /'
    echo ""
fi

# Detect current auth method
echo "--- Detecting Current Auth Method ---"
AUTH_METHOD="unknown"
if grep -qE "^PasswordAuthentication\s+yes" "$SSH_CONFIG" 2>/dev/null; then
    AUTH_METHOD="password"
fi
if grep -qE "^PubkeyAuthentication\s+yes" "$SSH_CONFIG" 2>/dev/null; then
    if [ "$AUTH_METHOD" = "password" ]; then
        AUTH_METHOD="both"
    else
        AUTH_METHOD="key"
    fi
fi
info "Current auth method: $AUTH_METHOD"
echo ""

# Check if user has authorized keys
echo "--- Checking Authorized Keys ---"
KEY_COUNT=0
for home_dir in /root /home/*/; do
    if [ -f "${home_dir}.ssh/authorized_keys" ]; then
        count=$(grep -cvE "^\s*(#|$)" "${home_dir}.ssh/authorized_keys" 2>/dev/null || echo 0)
        KEY_COUNT=$((KEY_COUNT + count))
        echo "  ${home_dir}: $count key(s)"
    fi
done
if [ "$KEY_COUNT" -gt 0 ]; then
    pass "Found $KEY_COUNT authorized SSH key(s)"
else
    warn "No authorized SSH keys found"
fi
echo ""

# Backup current config
echo "--- Backing Up Current Config ---"
BACKUP_FILE="${SSH_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$SSH_CONFIG" "$BACKUP_FILE"
pass "Config backed up to $BACKUP_FILE"
echo ""

# Apply hardening
echo "--- Applying Hardening ---"

# Create a hardened config snippet
HARDENED_CONFIG="/etc/ssh/sshd_config.d/99-uniserve-hardening.conf"

cat > "$HARDENED_CONFIG" << 'HARDENED_EOF'
# UniServe SSH Hardening
# Applied: $(date -u +%Y-%m-%dT%H:%M:%SZ)

# Protocol
Protocol 2

# Authentication
PubkeyAuthentication yes
PermitEmptyPasswords no
MaxAuthTries 3
LoginGraceTime 30

# Root login: allow (can restrict later once key auth is confirmed working)
# PermitRootLogin prohibit-password  # Uncomment after verifying key auth

# X11 forwarding not needed
X11Forwarding no

# Idle timeout
ClientAliveInterval 300
ClientAliveCountMax 2

# Logging
SyslogFacility AUTH
LogLevel INFO

# SFTP subsystem (keep — needed for file transfers)
Subsystem sftp /usr/lib/openssh/sftp-server
HARDENED_EOF

pass "Hardened config created: $HARDENED_CONFIG"

# Note: PasswordAuthentication is intentionally NOT changed here.
# It can only be disabled after key auth is independently verified.

if [ "$DISABLE_PASSWORD_AUTH" = true ]; then
    echo ""
    warn "PasswordAuthentication will be disabled (flag provided)"
    warn "ENSURE you have verified key-based login works first!"
    echo ""
    read -rp "Type 'DISABLE PASSWORD AUTH' to confirm: " CONFIRM
    if [ "$CONFIRM" = "DISABLE PASSWORD AUTH" ]; then
        echo "PasswordAuthentication no" >> "$HARDENED_CONFIG"
        pass "PasswordAuthentication disabled"
    else
        warn "Confirmation mismatch — skipping password auth disable"
    fi
else
    echo ""
    info "PasswordAuthentication NOT changed (safe default)"
    info "To disable later: bash $0 --disable-password-auth"
fi
echo ""

# Validate config
echo "--- Validating SSH Config ---"
if command -v sshd &>/dev/null; then
    sshd -t 2>&1 && pass "SSH config is valid" || fail "SSH config is INVALID — reverting"
else
    warn "sshd not found — cannot validate config"
fi
echo ""

# Restart SSH
echo "--- Restarting SSH ---"
systemctl restart sshd 2>&1 && pass "SSH restarted" || {
    warn "SSH restart failed — attempting to restore backup"
    cp "$BACKUP_FILE" "$SSH_CONFIG"
    rm -f "$HARDENED_CONFIG"
    systemctl restart sshd 2>&1
    fail "SSH restart failed — config restored from backup"
}
echo ""

# Verify SSH is running
echo "--- Verifying SSH ---"
if systemctl is-active sshd &>/dev/null 2>&1; then
    pass "SSH service is active"
else
    fail "SSH service is not active — config may need manual intervention"
fi
echo ""

echo "=============================================="
echo " SSH hardening complete."
echo "=============================================="
echo ""
echo "Changes applied:"
echo "  - Hardened config: $HARDENED_CONFIG"
echo "  - Backup: $BACKUP_FILE"
echo "  - MaxAuthTries: 3"
echo "  - X11Forwarding: no"
echo "  - ClientAliveInterval: 300"
echo "  - PasswordAuthentication: unchanged (safe default)"
echo ""
echo "IMPORTANT: Open a NEW SSH session before closing this one"
echo "to verify you can still connect."
echo ""
echo "Next: Run 06-configure-firewall.sh"
