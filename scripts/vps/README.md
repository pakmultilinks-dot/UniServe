# UniServe VPS Provisioning Scripts

Production-ready scripts to provision and harden a VPS for UniServe deployment.

## Quick Start

```bash
# On a fresh Ubuntu 22.04 VPS, as root:
cd /root
# Upload scripts/vps/ directory, then:
bash run-all.sh
```

## What This Does

| Phase | Script | What It Does |
|-------|--------|--------------|
| 1 | `01-verify-server.sh` | Verify OS, CPU, RAM, disk meet requirements |
| 2 | `02-system-update.sh` | Update all OS packages |
| 3 | `03-install-docker.sh` | Install Docker Engine + Compose, enable auto-start |
| 4 | `04-create-deploy-user.sh` | Create `deploy` user with Docker group access |
| 5 | `05-harden-ssh.sh` | Harden SSH (safe — keeps password auth by default) |
| 6 | `06-configure-firewall.sh` | UFW: allow only 22/80/443 |
| 7 | `07-prepare-deployment-dir.sh` | Create `/opt/uniserve/` structure |
| 8 | `08-verify-after-reboot.sh` | Post-reboot verification |

## What This Does NOT Do

- ❌ Deploy the UniServe application
- ❌ Run database migrations
- ❌ Start Docker Compose
- ❌ Configure DNS
- ❌ Issue TLS certificates
- ❌ Create `.env.production` or production secrets

Those are handled in Phase 19 (application deployment).

## Safety Features

- **SSH lockout prevention**: Password auth is not disabled unless explicitly requested with typed confirmation
- **Firewall lockout prevention**: Port 22 is allowed before UFW is enabled
- **Database/API protection**: PostgreSQL (5432), API (8000) are never publicly exposed
- **Config validation**: SSH config is tested with `sshd -t` before restart
- **Backups**: SSH config is backed up before any changes
- **Idempotent**: Safe to run multiple times

## Requirements

- Fresh VPS with Ubuntu 22.04+ or Debian 12+
- Root or sudo access
- 2+ CPU cores, 4+ GB RAM, 40+ GB disk
- Public IPv4 address

## After Provisioning

1. Reboot the VPS
2. Run `bash 08-verify-after-reboot.sh`
3. If all checks pass → proceed to Phase 19 (application deployment)
