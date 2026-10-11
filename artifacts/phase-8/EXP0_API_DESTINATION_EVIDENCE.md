# Phase 8A — Expo Web API-Destination Evidence

**Captured:** 2026-10-11
**Method:** raw CDP (`artifacts/phase-8/cdp.ps1`) against a dedicated Chrome instance
(`--remote-debugging-port=9333`, throwaway profile under `%TEMP%`), reading the live page's
`performance.getEntriesByType('resource')` — i.e. the browser's own record of network
requests actually issued by the running application.

No authentication tokens, passwords, or signing keys appear in this file or in the
associated screenshots.

## Result: PASS

The Expo web application served at `http://localhost:8090/` issues its API requests to
the **isolated Phase 8 API at `127.0.0.1:8001`**, not to any production endpoint.

## Captured resource entry (verbatim, sanitized)

```json
{
  "total": 9,
  "apiCalls": 1,
  "apiHosts": ["127.0.0.1:8001"],
  "samples": ["127.0.0.1:8001/api/v1/cafeterias"],
  "page": "http://localhost:8090/login"
}
```

- `apiHosts` = the distinct hosts of every observed request containing `/api/`.
- The observed call is `GET http://127.0.0.1:8001/api/v1/cafeterias`, issued by the
  app's own data service during startup (cafeteria list for the login/home screen).

## Supporting configuration evidence

The Expo dev server was launched with the isolated API base URL (visible in the launch
command, no secrets):

```
$env:EXPO_PUBLIC_API_BASE_URL='http://127.0.0.1:8001/api/v1'
npm run web --workspace apps/mobile -- --port 8090
```

The observed request host matches this configured base URL exactly.

## Reconciliation with earlier Phase 8 evidence

The Phase 8 menu-sync and item screenshots (`03_expo_web_phase8_item_sync.png`,
`12_expo_home_phase8_item_349.png`, `13_expo_item_detail_349_available.png`) were
captured from the same :8090 instance, whose API destination is now proven to be the
isolated API. Those screenshots therefore also reflect isolated data.

## Limitation

This evidence covers the **web** build of the Expo app (browser network log). It does
not constitute native Android verification; no Android device or emulator was used in
Phase 8 or Phase 8A.
