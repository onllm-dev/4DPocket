#!/usr/bin/env node
// @onllm-dev/4dpocket-mcp — thin launcher that proxies an MCP stdio client
// (Claude Desktop, Cursor, Claude Code, etc.) to a remote 4DPocket server
// over streamable HTTP with PAT auth.
//
// Usage:
//   npx @onllm-dev/4dpocket-mcp --url https://yours.tld --token fdp_pat_xxx
//   FDP_URL=... FDP_TOKEN=... npx @onllm-dev/4dpocket-mcp

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";

const require = createRequire(import.meta.url);

const HELP = `@onllm-dev/4dpocket-mcp — MCP client for 4DPocket

Usage:
  npx @onllm-dev/4dpocket-mcp --url <server-url> --token <pat>

Options:
  --url <url>      4DPocket server URL (e.g. https://pocket.example.com).
                   Reads FDP_URL env var if omitted.
  --token <pat>    Personal Access Token (fdp_pat_...).
                   Reads FDP_TOKEN env var if omitted.
  --help, -h       Show this help.
  --version, -v    Show version.

Claude Desktop / Cursor config example:
  {
    "mcpServers": {
      "4dpocket": {
        "command": "npx",
        "args": ["-y", "@onllm-dev/4dpocket-mcp",
                 "--url", "https://yours.tld",
                 "--token", "fdp_pat_xxx"]
      }
    }
  }
`;

function fail(msg) {
  process.stderr.write(`4dpocket-mcp: ${msg}\n\n${HELP}`);
  process.exit(2);
}

function parseArgs(argv) {
  const out = { url: process.env.FDP_URL ?? null, token: process.env.FDP_TOKEN ?? null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") { process.stdout.write(HELP); process.exit(0); }
    if (a === "--version" || a === "-v") {
      const pkg = require("./package.json");
      process.stdout.write(`${pkg.version}\n`);
      process.exit(0);
    }
    if (a === "--url") { out.url = argv[++i]; continue; }
    if (a === "--token") { out.token = argv[++i]; continue; }
    fail(`unknown argument: ${a}`);
  }
  return out;
}

function normalizeUrl(raw) {
  // Strip trailing slash, strip a trailing /mcp or /mcp/ if the user already
  // included it, then append /mcp/ — FastMCP's streamable-HTTP transport
  // requires the trailing slash.
  let u;
  try { u = new URL(raw); } catch { fail(`invalid --url: ${raw}`); }
  let p = u.pathname.replace(/\/+$/, "");
  if (p.endsWith("/mcp")) p = p.slice(0, -"/mcp".length);
  u.pathname = `${p}/mcp/`;
  return u.toString();
}

function resolveMcpRemoteBin() {
  const pkgPath = require.resolve("mcp-remote/package.json");
  const pkg = require(pkgPath);
  const rel = typeof pkg.bin === "string" ? pkg.bin : pkg.bin?.["mcp-remote"];
  if (!rel) fail("mcp-remote is installed but exposes no 'mcp-remote' bin; reinstall.");
  return path.resolve(path.dirname(pkgPath), rel);
}

const { url, token } = parseArgs(process.argv.slice(2));
if (!url) fail("missing --url (or FDP_URL env var).");
if (!token) fail("missing --token (or FDP_TOKEN env var).");
if (!token.startsWith("fdp_pat_")) {
  process.stderr.write(
    `4dpocket-mcp: warning: token does not start with fdp_pat_ — is this really a 4DPocket PAT?\n`
  );
}

const mcpUrl = normalizeUrl(url);
const binAbs = resolveMcpRemoteBin();

const child = spawn(
  process.execPath,
  [binAbs, mcpUrl, "--header", `Authorization: Bearer ${token}`],
  { stdio: "inherit" }
);
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 0);
});
