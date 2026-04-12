# UAT smoke test

Visits every route in a real browser (headless Chromium via Playwright) and
fails the run if any page shows the React error boundary, fails to fetch a
chunk, or throws an uncaught error.

## Prerequisites

- Backend running: `./app.sh start --postgres` (or `--sqlite`)
- Frontend running: `pnpm --filter frontend dev` or the bundled app at port 4040
- Playwright available on PATH (`brew install playwright` or
  `npm i -g playwright && npx playwright install chromium`)

## Run

```bash
UAT_BASE_URL=http://localhost:5173 \
UAT_USERNAME=yourname \
UAT_PASSWORD='secret' \
node tests/uat/routes.mjs
```

Or simply use Makefile target (defined in `Makefile`):

```bash
make uat
```

Environment variables:
- `UAT_BASE_URL` — app URL (default `http://localhost:5173`)
- `UAT_USERNAME`, `UAT_PASSWORD` — account to log in with
- `UAT_COLLECTION_UUID` — a real collection UUID for `/collections/:id`

## What it asserts per route

- Page loads without crashing
- No `Something went wrong` text (error boundary)
- No uncaught `pageerror`
- No red console errors (benign ones like external favicon 404s are filtered)
- Bad-UUID routes render a friendly "not found" instead of crashing

## Report

`tests/uat/last-run.json` is written after each run for CI consumption.

## Gotchas

- **Rate limiting** — the backend has IP-based rate limits on auth and API
  endpoints. Running this UAT back-to-back (>3 times per 5 minutes against
  the same backend) may trigger `429 Too Many Requests`, which cascades
  into "login form not visible" or "Something went wrong" error boundaries.
  Wait a few minutes between runs, or temporarily raise/disable rate limits
  when testing.
- **Service worker** — `sw.js` is served by the bundled app. A 429 on it
  fires a `pageerror` which the UAT filters.
- **Lazy chunks** — the app uses Vite lazy imports. If you restart the
  frontend dev server mid-run, a stale chunk reference can trigger a chunk
  fetch failure; hard-refresh your browser and re-run.
