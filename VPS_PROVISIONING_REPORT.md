# UniServe — VPS Provisioning Report

**Date:** 2026-09-30
**Phase:** 18 — VPS Provisioning and Security Hardening
**Status:** ⛔ **BLOCKED — VPS NOT READY**

---

## Executive Summary

Phase 18 requires a real, provisioned VPS to perform server verification, system updates, Docker installation, SSH hardening, firewall configuration, and deployment directory preparation.

**No VPS has been provisioned.** There is no server IP, no SSH credentials, and no cloud provider account connected to this environment. The only SSH entry in `known_hosts` is for `ssh.railway.com` (a PaaS platform, not a VPS).

**I have not fabricated any server verification results.** Instead, I have prepared a complete, production-ready provisioning toolkit that can be executed the moment a VPS exists.

---

## What Was Prepared

### Provisioning Scripts (`scripts/vps/`)

| Script | Phase | Purpose |
|--------|-------|---------|
| `01-verify-server.sh` | 1 | Verify server meets documented requirements (OS, CPU, RAM, disk, arch) |
| `02-system-update.sh` | 2 | Update all OS packages |
| `03-install-docker.sh` | 3 | Install Docker Engine + Compose plugin, enable auto-start |
| `04-create-deploy-user.sh` | 4 | Create deployment user with Docker group access |
| `05-harden-ssh.sh` | 5 | Harden SSH (safe — does NOT disable password auth by default) |
| `06-configure-firewall.sh` | 6 | UFW: allow only 22/80/443, deny everything else |
| `07-prepare-deployment-dir.sh` | 7 | Create `/opt/uniserve/` directory structure |
| `08-verify-after-reboot.sh` | 8 | Post-reboot verification (Docker auto-start, firewall, SSH) |
| `run-all.sh` | — | Master script: runs all phases in order |

### Script Safety Features

- **SSH hardening does NOT lock you out**: Password auth is not disabled unless explicitly requested with `--disable-password-auth` flag AND typed confirmation. Config is validated with `sshd -t` before restart. Backup is created before any changes.
- **Firewall enables SSH first**: UFW allows port 22 before being enabled, preventing lockout.
- **Firewall blocks database/API**: PostgreSQL (5432), API (8000), and Redis (6379) are explicitly NOT exposed.
- **Idempotent**: Scripts check for existing installations and skip if already done.
- **No secrets created**: No `.env.production`, no passwords, no tokens.

---

## What Is Blocking

| Requirement | Status | Notes |
|-------------|--------|-------|
| VPS provisioned | ❌ Missing | No cloud provider account or server exists |
| SSH access | ❌ Missing | No server IP or credentials |
| Ubuntu 22.04+ | ⏳ Pending | Cannot verify without a server |
| Docker installed | ⏳ Pending | Script ready, needs a server to run on |
| Firewall configured | ⏳ Pending | Script ready, needs a server to run on |

---

## Documented Requirements (from `DEPLOYMENT_RUNBOOK.md`)

These are the requirements the provisioning scripts verify against:

| Requirement | Documented Value |
|-------------|------------------|
| OS | Ubuntu 22.04+ / Debian 12+ |
| CPU | 2+ cores |
| RAM | 4 GB minimum |
| Disk | 40 GB+ SSD |
| Deployment directory | `/opt/uniserve` |
| Docker | Engine + Compose plugin |
| Public ports | 22 (SSH), 80 (HTTP), 443 (HTTPS) |
| Internal-only | PostgreSQL 5432, API 8000, Redis 6379 |

---

## Server Details

| Field | Value |
|-------|-------|
| OS | **N/A — no server** |
| CPU | **N/A** |
| RAM | **N/A** |
| Disk | **N/A** |
| Architecture | **N/A** |
| Public IP | **N/A** |

---

## Software

| Software | Version |
|----------|---------|
| Docker | **N/A — not installed (no server)** |
| Docker Compose | **N/A — not installed (no server)** |

---

## Security

| Check | Status |
|-------|--------|
| SSH hardened | ⏳ Script ready (`05-harden-ssh.sh`) |
| Firewall configured | ⏳ Script ready (`06-configure-firewall.sh`) |
| Publicly exposed ports | ⏳ Will be 22/80/443 only |
| PostgreSQL not public | ⏳ Script explicitly blocks 5432 |
| API not public | ⏳ Script explicitly blocks 8000 |
| No production secrets created | ✅ Confirmed — none exist |

---

## Deployment Readiness

| Item | Status |
|------|--------|
| Deployment directory | ⏳ Script ready (`07-prepare-deployment-dir.sh`) |
| Docker status | ⏳ Not installed (no server) |
| Reboot verification | ⏳ Script ready (`08-verify-after-reboot.sh`) |
| Application deployed | ✅ Correctly NOT deployed |
| Migrations run | ✅ Correctly NOT run |
| Compose started | ✅ Correctly NOT started |
| DNS configured | ✅ Correctly NOT configured |
| TLS certificates | ✅ Correctly NOT issued |
| `.env.production` created | ✅ Correctly NOT created |

---

## Problems

| # | Issue | Severity | Resolution |
|---|-------|----------|------------|
| 1 | No VPS provisioned | **Blocker** | Provision a VPS (Ubuntu 22.04 LTS, 2 vCPU, 4 GB RAM, 40 GB SSD) |
| 2 | No SSH access to any server | **Blocker** | Provide server IP and SSH credentials |
| 3 | No cloud provider account connected | **Blocker** | Set up VPS with any provider (AWS, DigitalOcean, Hetzner, etc.) |

---

## How to Unblock

1. **Provision a VPS** with any provider (recommended specs: Ubuntu 22.04 LTS, 2 vCPU, 4 GB RAM, 40 GB SSD)
2. **Note the server's public IP address**
3. **Ensure SSH access works** (root or sudo user with password or key)
4. **Run the provisioning script:**
   ```bash
   ssh root@<server-ip>
   # Upload the scripts/vps/ directory to the server, then:
   cd scripts/vps
   bash run-all.sh
   ```
5. **Reboot and verify:**
   ```bash
   sudo reboot
   # Reconnect, then:
   bash 08-verify-after-reboot.sh
   ```
6. **If all checks pass**, update this report with real server details and change status to `VPS READY FOR APPLICATION DEPLOYMENT`

---

## Final Status

# ⛔ BLOCKED — VPS NOT READY

**Reason:** No VPS has been provisioned. No server exists to connect to. The provisioning toolkit is complete and ready to execute, but cannot be run without a real server.

**Next action:** Provision a VPS, provide SSH access, then run `scripts/vps/run-all.sh`.

---

*This report contains no passwords, private keys, tokens, or server credentials.*
