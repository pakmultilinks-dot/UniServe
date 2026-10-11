# UniServe — Demo Safety Checklist

**Purpose:** Complete pre-demo safety verification. Run every item before the audience arrives. The demo must never expose secrets, never destroy data, and never depend on a single live step.

**Verification date of current environment:** 2026-10-08 (all items below were passing at capture time).

---

## 1. Infrastructure health

| # | Check | How to verify | Passing state | ✅ |
|---|---|---|---|---|
| 1.1 | Docker Desktop running | Taskbar icon / `docker ps` | Engine responsive | ☐ |
| 1.2 | PostgreSQL container healthy | `docker ps` — `uniserve_postgres` (postgres:16-alpine) | Status `Up` / healthy | ☐ |
| 1.3 | API container healthy | `docker ps` — `uniserve_api` (image `uniserve-prod-api`) | Status `Up` / healthy | ☐ |
| 1.4 | API health endpoint | Open `http://localhost:8000/api/v1/health` | `{"status":"ready","service":"uniserve-api","database":"connected","schema":"present"}` | ☐ |
| 1.5 | Database reachable | API health `"database":"connected"` is sufficient; if needed: read-only query via psql in container | Query returns rows | ☐ |
| 1.6 | Web console running | Open `http://localhost:3000` | Page loads (login screen or dashboard) | ☐ |
| 1.7 | Mobile app (Expo web) running | Open `http://localhost:8081` | Login screen or app home loads | ☐ |

**If 1.2/1.3 fail:** restart Docker Desktop (non-standard path on this machine: `C:\Users\Lenovo\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`), wait for containers, re-check 1.4. **Never** run `docker compose down -v` — it destroys demo data.

**If 1.6 fails:** from `apps/web` run `npx next dev`. First compile takes 30–60 s.

**If 1.7 fails:** from `apps/mobile` run `npx expo start --web --port 8081`. First bundle takes 30–60 s.

---

## 2. Configuration correctness

| # | Check | How to verify | Passing state | ✅ |
|---|---|---|---|---|
| 2.1 | API base URL used by web console | `apps/web/.env.local` → `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` (local demo value) | ☐ |
| 2.2 | API base URL used by mobile app | App config / env used by Expo build | Points at `http://localhost:8000/api/v1` for local demo | ☐ |
| 2.3 | No production URLs in demo config | Skim `.env.local` (do not display) | Only localhost values | ☐ |
| 2.4 | Web dev server on port 3000 | Browser tab | `localhost:3000` | ☐ |
| 2.5 | Expo web on port 8081 | Browser tab | `localhost:8081` | ☐ |

> **Presenter rule:** never project `.env` or `.env.local` content on screen. Check values privately before the demo.

---

## 3. Demo accounts

| # | Check | How to verify | Passing state | ✅ |
|---|---|---|---|---|
| 3.1 | Correct demo accounts exist | See `DEMO_ACCOUNTS.md` — 8 fixture accounts | All 8 present | ☐ |
| 3.2 | Correct passwords known | Students/faculty/staff/manager `TestPass123!`; admin `Admin123!` | Rehearsed logins succeed | ☐ |
| 3.3 | Correct account per demo beat | Runbook 5/10/15-min tables | Each beat mapped to an account | ☐ |
| 3.4 | No personal credentials used | Logins only with fixture accounts | No personal emails/passwords in browser | ☐ |
| 3.5 | No new accounts created | `git status` — no DB/seed changes | Working tree free of data changes | ☐ |
| 3.6 | Cafeteria scopes known | Staff ahmed.raza → Student Cafeteria; manager sana.malik → Faculty Cafeteria; faculty → both | Stated in runbook | ☐ |

---

## 4. Browser state

| # | Check | How to verify | Passing state | ✅ |
|---|---|---|---|---|
| 4.1 | Only demo tabs open | Inspect tab bar | Health endpoint + web console + mobile app (3 tabs) | ☐ |
| 4.2 | No unrelated tabs | Inspect tab bar | No email, banking, personal, or work tabs visible | ☐ |
| 4.3 | No session leaked between roles | Sign out between role beats | Each role logs in fresh | ☐ |
| 4.4 | Private/incognito window ready | Open one for the unauthenticated-redirect beat | Blank, no cookies | ☐ |
| 4.5 | Notification widget reachable | Mobile app Notifications tab + admin Notifications screen | Screens load | ☐ |
| 4.6 | Screenshot fallbacks available | `presentation/` folder (41 PNGs) | Folder open in file browser | ☐ |
| 4.7 | Bookmarks bar clean | Inspect bookmarks bar | No personal bookmarks visible | ☐ |

---

## 5. Secrets & data exposure

| # | Check | How to verify | Passing state | ✅ |
|---|---|---|---|---|
| 5.1 | No `.env` content on screen | Tab audit | No env files open | ☐ |
| 5.2 | No terminal with secrets visible | Window audit | Terminals minimized/closed or showing non-secret output | ☐ |
| 5.3 | No API keys/JWTs projected | Screen audit | No token strings visible on projected screen | ☐ |
| 5.4 | No database passwords visible | Screen audit | Postgres creds not shown | ☐ |
| 5.5 | Demo passwords not projected | Presenter discipline | Passwords referenced verbally or from notes, never projected | ☐ |
| 5.6 | No source-code editor open with secrets | Window audit | Editor closed or on non-secret files | ☐ |

---

## 6. Data integrity (do no harm)

| # | Check | How to verify | Passing state | ✅ |
|---|---|---|---|---|
| 6.1 | No data modified for appearance | Working principle | Database only touched through normal app UI if at all | ☐ |
| 6.2 | No fabricated menus/metrics/screenshots | Working principle | All evidence from live app or Phase 62 verification records | ☐ |
| 6.3 | Git HEAD unchanged | `git rev-parse HEAD` | `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` | ☐ |
| 6.4 | package-lock.json unchanged | SHA-256 | `3AE3D031F90A7608E854E4B34A147ECEE12C63634F96F9D7BB70EF9C4694C5D8` | ☐ |
| 6.5 | No source files modified | `git status --short` | Only new untracked presentation artifacts | ☐ |
| 6.6 | Demo DB census unchanged (sanity) | Read-only counts if desired | 18 users · 52 orders · 39 payments · 4 refunds · 150 notifications · 844 audit events · 383 sessions | ☐ |

---

## 7. Landmine avoidance (verbal discipline)

| # | Never | Why |
|---|---|---|
| 7.1 | Run `npx next build` | Known dual-React defect (F-61-03) + clobbers running `.next` |
| 7.2 | Run `docker compose down -v` | Destroys demo database volumes |
| 7.3 | Run `ruff check app` without `--no-fix` | May rewrite source files |
| 7.4 | Send a broadcast / approve refunds / publish menus accidentally | Changes demo state mid-presentation |
| 7.5 | Click "Sign Out All Devices" during a multi-role demo | Invalidates other role sessions |
| 7.6 | Build demo beats on "Phase 56 E2E Cafeteria" | Test residue (F-61-06) |
| 7.7 | Run heavy test suites concurrently | Known memory flake (F-61-14) |
| 7.8 | Edit DB rows to beautify screenshots | Violates presentation constraints |

---

## 8. Presentation fallbacks

| # | Check | Passing state | ✅ |
|---|---|---|---|
| 8.1 | `presentation/` folder contains all 41 screenshots | Listed in `UNISERVE_PRESENTATION_CONTENT.md` appendix | ☐ |
| 8.2 | Slide content doc open (`UNISERVE_PRESENTATION_CONTENT.md`) | Ready for screen-share if app fails | ☐ |
| 8.3 | Demo script open (`FINAL_DEMO_SCRIPT.md`) | Speaker notes at hand | ☐ |
| 8.4 | Evaluator cheat sheet printed/open (`EVALUATOR_CHEAT_SHEET.md`) | 15 Q&A ready | ☐ |
| 8.5 | Known-limitations one-liners memorized | Category-A items from demo script | ☐ |
| 8.6 | Metrics memorized (or open `FINAL_PROJECT_METRICS.md`) | 872/5 · 40/40 · 34/34 · 13/13 · rehearsals | ☐ |

---

## 9. Final go/no-go (60 seconds before start)

1. Health endpoint shows `"status":"ready"` — **GO**.
2. Web console dashboard loads — **GO**.
3. Mobile app home loads (reload once if cafeteria list empty) — **GO**.
4. Browser shows only demo tabs — **GO**.
5. First logged-in beat account ready to type — **GO**.

**If any NO:** use screenshot fallbacks from `presentation/` and narrate from `UNISERVE_PRESENTATION_CONTENT.md`. The demo does not dead-end.
