#!/usr/bin/env node
/**
 * UAT smoke test — visits every app route with a logged-in browser,
 * asserts no error boundary / dynamic-import failure / React crash,
 * and filters console errors down to real problems.
 *
 * Run:
 *   node tests/uat/routes.mjs
 *
 * Env:
 *   UAT_BASE_URL  (default http://localhost:5173)
 *   UAT_USERNAME, UAT_PASSWORD   (required for protected routes)
 *   UAT_COLLECTION_UUID  (optional, for /collections/:id)
 *
 * Requires `playwright` on PATH. Uses /opt/homebrew's install when present,
 * else falls back to the local one.
 */

import { createRequire } from "node:module";
import path from "node:path";
import fs from "node:fs";

const require = createRequire(import.meta.url);

function loadPlaywright() {
  const here = path.dirname(new URL(import.meta.url).pathname);
  const projectRoot = path.resolve(here, "..", "..");
  const candidates = [
    path.join(projectRoot, "frontend", "node_modules", "playwright"),
    path.join(projectRoot, "node_modules", "playwright"),
    "/opt/homebrew/lib/node_modules/playwright",
    path.join(process.env.HOME || "", ".npm-global/lib/node_modules/playwright"),
    "playwright",
  ];
  for (const c of candidates) {
    try {
      return require(c);
    } catch {
      // try next
    }
  }
  console.error("ERROR: playwright not found.");
  console.error("Install with one of:");
  console.error("  cd frontend && pnpm add -D playwright && pnpm exec playwright install chromium");
  console.error("  npm i -g playwright && npx playwright install chromium");
  process.exit(2);
}

const { chromium } = loadPlaywright();

const BASE = process.env.UAT_BASE_URL || "http://localhost:5173";
const USER = process.env.UAT_USERNAME || "mcptest1775996183";
const PASS = process.env.UAT_PASSWORD || "Test-PAT-0.2.1!";
const COLL = process.env.UAT_COLLECTION_UUID || "74f04949-8395-414d-aa77-6d2d9ea2ebf4";

const ROUTES = [
  { path: "/login", auth: false },
  { path: "/register", auth: false },
  { path: "/", auth: true },
  { path: "/knowledge", auth: true },
  { path: "/search", auth: true },
  { path: "/collections", auth: true },
  { path: `/collections/${COLL}`, auth: true },
  { path: "/collections/00000000-0000-0000-0000-000000000000", auth: true, expectNotFound: true },
  { path: "/tags", auth: true },
  { path: "/notes", auth: true },
  { path: "/reading-list", auth: true },
  { path: "/settings", auth: true },
  { path: "/add", auth: true },
  { path: "/admin", auth: true },
  { path: "/shared", auth: true },
  { path: "/feed", auth: true },
  { path: "/rules", auth: true },
  { path: "/timeline", auth: true },
  { path: "/highlights", auth: true },
  { path: "/entities", auth: true },
  { path: "/item/00000000-0000-0000-0000-000000000000", auth: true, expectNotFound: true },
];

// Console errors that are known-benign noise (not the user's problem).
const IGNORE_PATTERNS = [
  /google\.com\/s2\/favicons/i,            // external favicon 404
  /429/,                                    // rate-limit during rapid nav
  /Failed to fetch dynamically imported module/i, // stale Vite chunk — benign in dev after HMR
  /net::ERR_ABORTED/i,
];

function isIgnorable(msg) {
  return IGNORE_PATTERNS.some((p) => p.test(msg));
}

const results = [];

async function login(page) {
  // Clear leftover auth from a prior UAT run. AuthGuard reads both the
  // HttpOnly cookie AND a localStorage flag — clear both so /login renders.
  await page.context().clearCookies();
  try {
    await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 10000 });
    await page.evaluate(() => {
      try { localStorage.clear(); sessionStorage.clear(); } catch {}
    });
  } catch { /* ignore */ }
  // Reload /login now that local storage is clean so AuthGuard doesn't redirect.
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 15000 });
  try {
    await page.waitForSelector('input[type="text"]', { timeout: 15000 });
  } catch (err) {
    const url = page.url();
    try {
      const snap = path.join(process.cwd(), "tests", "uat", "login-debug.png");
      await page.screenshot({ path: snap, fullPage: true });
      const body = (await page.textContent("body"))?.slice(0, 400) ?? "";
      throw new Error(
        `login form not visible (url=${url}, screenshot=${snap}, body_start="${body.replace(/\s+/g, " ").slice(0, 200)}"): ${err.message}`
      );
    } catch (inner) {
      throw inner;
    }
  }
  await page.fill('input[type="text"]', USER);
  await page.fill('input[type="password"]', PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 10000 });
}

async function visit(page, route) {
  const errors = [];
  const consoleListener = (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      if (isIgnorable(text)) return;
      // On bad-ID routes, a backend 404 is expected and handled by the UI —
      // don't count it as a failure.
      if (route.expectNotFound && /404|not found|no such/i.test(text)) return;
      errors.push(text);
    }
  };
  const pageErrorListener = (err) => {
    const text = err.message || String(err);
    if (!isIgnorable(text)) errors.push(`uncaught: ${text}`);
  };
  page.on("console", consoleListener);
  page.on("pageerror", pageErrorListener);

  let status = "pass";
  let detail = "";
  try {
    // For bad-ID routes, don't wait for networkidle — 404 queries may retry
    // with backoff and never hit idle. DOMContentLoaded + polling is reliable.
    await page.goto(`${BASE}${route.path}`, {
      waitUntil: route.expectNotFound ? "domcontentloaded" : "networkidle",
      timeout: 20000,
    });
    if (route.expectNotFound) {
      for (let i = 0; i < 30; i++) {
        await page.waitForTimeout(300);
        const txt = (await page.textContent("body"))?.toLowerCase() ?? "";
        if (txt.includes("not found") || txt.includes("doesn't exist") || txt.includes("does not exist")) break;
      }
    } else {
      await page.waitForTimeout(500);
    }

    const bodyText = (await page.textContent("body"))?.toLowerCase() ?? "";

    // Error-boundary: look for the actual h2 text from ErrorBoundary.tsx.
    // Use h2 locator rather than body text so "try again" from form errors
    // doesn't produce false positives.
    const errorH2 = await page.locator('h2:has-text("Something went wrong")').count();
    const hasErrorBoundary =
      errorH2 > 0 ||
      bodyText.includes("failed to fetch dynamically imported module");

    if (hasErrorBoundary) {
      status = "fail";
      detail = 'error-boundary visible ("Something went wrong")';
    } else if (route.expectNotFound) {
      // For bad-ID routes, confirm the app shows a "not found" state, not a crash.
      const found404 =
        bodyText.includes("not found") ||
        bodyText.includes("doesn't exist") ||
        bodyText.includes("does not exist") ||
        bodyText.includes("no longer exists") ||
        bodyText.includes("couldn't find");
      if (!found404) {
        status = "warn";
        detail = "expected a not-found message but none shown";
      } else {
        detail = "shows not-found correctly";
      }
    } else if (errors.length > 0) {
      status = "fail";
      detail = `${errors.length} console error(s): ${errors[0].slice(0, 140)}`;
    }
  } catch (err) {
    status = "fail";
    detail = `navigation failed: ${err.message || err}`;
  }

  page.off("console", consoleListener);
  page.off("pageerror", pageErrorListener);
  results.push({ route: route.path, status, detail });
  const mark = status === "pass" ? "PASS" : status === "warn" ? "WARN" : "FAIL";
  console.log(`[${mark}] ${route.path}${detail ? `  — ${detail}` : ""}`);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();

  try {
    // Public routes first — no login yet.
    for (const r of ROUTES.filter((r) => !r.auth)) {
      await visit(page, r);
    }

    // Login once, then visit protected routes.
    try {
      await login(page);
    } catch (err) {
      console.error(`FATAL: login failed for ${USER}: ${err.message}`);
      results.push({ route: "LOGIN", status: "fail", detail: err.message });
      process.exit(1);
    }

    for (const r of ROUTES.filter((r) => r.auth)) {
      await visit(page, r);
    }
  } finally {
    await browser.close();
  }

  const fail = results.filter((r) => r.status === "fail").length;
  const warn = results.filter((r) => r.status === "warn").length;
  const pass = results.filter((r) => r.status === "pass").length;

  console.log("");
  console.log("=".repeat(64));
  console.log(`  UAT SUMMARY  PASS=${pass}  WARN=${warn}  FAIL=${fail}  TOTAL=${results.length}`);
  console.log("=".repeat(64));

  // Write JSON report for CI.
  try {
    const out = path.join(process.cwd(), "tests", "uat", "last-run.json");
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, JSON.stringify({ base: BASE, results, pass, warn, fail }, null, 2));
    console.log(`report: ${out}`);
  } catch {
    // ignore write failure
  }

  process.exit(fail > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error("fatal:", err);
  process.exit(1);
});
