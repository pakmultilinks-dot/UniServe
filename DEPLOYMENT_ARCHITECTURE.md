# UniServe — Production Deployment Architecture

> **Pattern:** Single-server modular monolith
> **Orchestration:** Docker Compose
> **HTTPS:** Caddy (automatic Let's Encrypt)
> **Last verified:** 2026-09-30

---

## Components

```
┌──────────────────────────────────────────────────────────┐
│                    INTERNET (443/80)                      │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│                   CADDY (reverse proxy)                   │
│  • Automatic HTTPS via Let's Encrypt                     │
│  • TLS termination                                       │
│  • Serves Next.js static files directly                  │
│  • Proxies /api/* → FastAPI                              │
│  • Security headers (HSTS, X-Frame-Options, etc.)        │
└───────┬──────────────────────────────────────┬───────────┘
        │ /api/*                               │ /* (static)
        │                                      │
┌───────▼─────────────┐          ┌─────────────▼──────────┐
│   FastAPI API        │          │   Static Web Files      │
│   (internal :8000)   │          │   (served by Caddy)     │
│                      │          │                         │
│  • JWT auth          │          │  • Next.js static       │
│  • Background worker │          │  • JS/CSS/images        │
│  • Structured logs   │          │                         │
└───────┬─────────────┘          └─────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────┐
│                 INTERNAL NETWORK                          │
│                                                           │
│  ┌─────────────────┐    ┌─────────────────┐              │
│  │   PostgreSQL      │    │   Redis          │              │
│  │   (internal:5432) │    │   (internal:6379) │              │
│  │                   │    │                  │              │
│  │  • Persistent vol │    │  • Optional      │              │
│  │  • Health checks  │    │  • No data deps  │              │
│  │  • Not public     │    │  • Can be removed│              │
│  └──────────────────┘    └──────────────────┘              │
└──────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────┐
│              MOBILE APP (React Native / Expo)             │
│                                                           │
│  Connects directly to https://api.example.com/api/v1     │
│  No reverse proxy needed — native HTTP client             │
└──────────────────────────────────────────────────────────┘
```

## Services

| Service | Internal Port | Public? | Purpose |
|---------|--------------|---------|---------|
| **Caddy** | 80, 443 | ✅ Yes | HTTPS termination, static files, API proxy |
| **FastAPI API** | 8000 | ❌ No (via Caddy) | Business logic, background workers |
| **PostgreSQL** | 5432 | ❌ No (internal only) | Primary data store |
| **Redis** | 6379 | ❌ No (internal only) | Placeholder — not used at runtime |

> **Note:** The web static files are built on the server (`apps/web/out/`) and served by Caddy via bind mount. There is no separate web container in production.

## Network Flow

### Web Browser → API
```
Browser → HTTPS :443 → Caddy → HTTP :8000 → FastAPI
                                        ↕
                                   PostgreSQL
```

### Web Browser → Static Assets
```
Browser → HTTPS :443 → Caddy → /var/www/web/_next/static/*
```

### Mobile App → API
```
Mobile → HTTPS :443 → Caddy → HTTP :8000 → FastAPI
                                        ↕
                                   PostgreSQL
```

## Persistent Storage

| Volume | Mount Point | Contents | Backup Priority |
|--------|------------|----------|-----------------|
| `postgres_data` | `/var/lib/postgresql/data` | All database tables, indexes, migrations | **Critical** |
| `./apps/web/out` | `/srv` (Caddy) | Next.js static export files (host bind mount) | Build artifact |

Redis is ephemeral — no persistent storage needed (not used at runtime).

## Environment-Based Configuration

All secrets and configuration are injected via environment variables. No hardcoded values in images.

| Variable Category | Source |
|-------------------|--------|
| Database credentials | `.env.production` |
| JWT secrets | `.env.production` |
| API CORS origins | `.env.production` |
| Web API URL | `.env.local` (build-time) |
| Mobile API URL | `app.json` extra (build-time) |

## Deployment / Update Flow

1. Pull latest code on server
2. Run database migrations
3. Rebuild API image
4. Rebuild web static export
5. Restart services
6. Verify health endpoints

See `DEPLOYMENT_RUNBOOK.md` for exact commands.

## Backup Strategy

- **PostgreSQL:** Daily `pg_dump --format=custom` to timestamped file
- **Retention:** Keep 7 daily backups minimum
- **Restore:** `pg_restore` from backup file
- See `DATABASE_OPERATIONS.md` for exact commands.

## Why This Architecture

| Alternative | Why Not |
|-------------|---------|
| Kubernetes | Overkill — single VPS handles current load, adds operational complexity |
| Multiple servers | Modular monolith runs fine on one machine; split later if needed |
| Serverless (Lambda/Cloud Run) | WebSocket and background worker patterns don't fit well |
| Nginx | Works, but Caddy has automatic HTTPS with zero config — simpler |

## Scaling Notes

If traffic grows beyond a single VPS:
1. Add a second VPS for the API, keep PostgreSQL on the first
2. Move PostgreSQL to a managed service (e.g., Supabase, RDS)
3. Add a CDN for static assets (Cloudflare, Vercel)
4. Consider Redis for caching if database read load increases
5. Consider splitting background workers to a separate process

None of these are needed now. This architecture supports hundreds of concurrent users on a $20/month VPS.
