// claude-any-proxy — the ANY-port of the claude-token proxy, standalone.
//
// Per request, picks the healthiest profile (fresh AT, not needsRelogin, not
// in cooldown; spread-load across the pool) and forwards to api.anthropic.com
// with that profile's token. On upstream 401/429: the profile is cooled down
// (shared with ai-any's ~/.claude-token/any-state.json — seconds epoch
// schema), an async heal (ai-token publish) fires for 401s, and the SAME
// request is retried with the next-best profile — mid-turn failover that is
// invisible to the client session.
//
// This file is independent of ai-token's generated per-profile proxy (which
// serves 7801-7806). CLAUDE_PROXY_PROFILES=0 (default here) skips per-profile
// listeners entirely.
import http from "node:http";
import { readFileSync, writeFileSync, renameSync, appendFileSync } from "node:fs";
import { execFile } from "node:child_process";

const [registryPath, sharedDir] = process.argv.slice(2);
const HOME = process.env.HOME;
const UPSTREAM = process.env.CLAUDE_PROXY_UPSTREAM || "https://api.anthropic.com";
const ANY_PORT = Number(process.env.CLAUDE_PROXY_ANY_PORT || 7800);
const NO_HEAL = process.env.CLAUDE_PROXY_NO_HEAL === "1";
const STATE_FILE = `${HOME}/.claude-token/any-state.json`;
const ANY_LOG = `${HOME}/.claude-token/any.log`;
const COOLDOWN_401_S = 900;
const COOLDOWN_429_S = 1800;
const MIN_FRESH_MS = 60_000;
const MAX_TRIES = 3;

const HOP_BY_HOP = new Set([
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailer", "trailers", "transfer-encoding", "upgrade",
]);

const nowS = () => Date.now() / 1000;
const readJson = (p) => { try { return JSON.parse(readFileSync(p, "utf8")); } catch { return null; } };
function writeJsonAtomic(p, v) {
  try { const t = p + ".tmp"; writeFileSync(t, JSON.stringify(v)); renameSync(t, p); } catch {}
}
function anyLog(event, kv) {
  try { appendFileSync(ANY_LOG, JSON.stringify({ ts: nowS(), event, via: "any-proxy", ...kv }) + "\n"); } catch {}
}

const loadRegistry = () => readJson(registryPath) || {};
const loadState = () => readJson(STATE_FILE) || {};
const saveState = (s) => writeJsonAtomic(STATE_FILE, s);

function needsRelogin(profile) {
  if (roleOf() === "follower") return false;  // leader-layout marker; followers rely on pull freshness
  const c = readJson(`${HOME}/.claude-profiles/${profile}/.claude/credentials.json`);
  return !!(c && c.claudeTokenSync && c.claudeTokenSync.needsRelogin);
}

function freshToken(profile) {
  const d = readJson(`${sharedDir}/${profile}.json`);
  if (!d) return null;
  const o = d.claudeAiOauth || d;
  if (!o.accessToken) return null;
  if ((o.expiresAt || 0) - Date.now() < MIN_FRESH_MS) return null;
  return o.accessToken;
}

function pickAny(state, exclude) {
  let best = null;
  for (const p of Object.keys(loadRegistry())) {
    if (exclude.has(p)) continue;
    const ent = state[p] || {};
    if ((ent.cooldown_401_until || 0) > nowS()) continue;
    if ((ent.cooldown_429_until || 0) > nowS()) continue;
    if (!freshToken(p)) continue;
    if (needsRelogin(p)) continue;
    const last = ent.last_used || 0;
    if (!best || last < best.last) best = { profile: p, last, token: freshToken(p) };
  }
  return best;
}

function markCooldown(profile, kindS) {
  const s = loadState();
  const ent = (s[profile] ||= {});
  ent[kindS === "401" ? "cooldown_401_until" : "cooldown_429_until"] =
    nowS() + (kindS === "401" ? COOLDOWN_401_S : COOLDOWN_429_S);
  saveState(s);
  anyLog("cooldown", { profile, kind: kindS });
}

function markUsed(profile) {
  const s = loadState();
  (s[profile] ||= {}).last_used = nowS();
  saveState(s);
}

const healInFlight = new Set();
function roleOf() {
  try {
    const cfg = readFileSync(`${HOME}/.claude-token/config`, "utf8");
    const m = cfg.match(/^mode=(\w+)/m);
    if (m) return m[1] === "follower" ? "follower" : "leader";
  } catch {}
  // no config: farol is the leader; anything else is treated as a follower
  return (process.env.CLAUDE_PROXY_FOLLOWER === "1") ? "follower" : "leader";
}
function heal(profile) {
  if (NO_HEAL || healInFlight.has(profile)) return;
  healInFlight.add(profile);
  const role = roleOf();
  anyLog("heal-start", { profile, role });
  const env = { ...process.env };
  if (role === "leader") env.CLAUDE_TOKEN_VAULT_AUTHORITY = "yes";
  // leader: publish refreshes + republishes the shared file. follower: the
  // mirror script re-pulls the profile and rewrites its mirror entry.
  const cmd = role === "follower"
    ? [`${HOME}/.local/bin/claude-any-mirror`, [profile]]
    : [`${HOME}/.local/bin/ai-token`, ["claude", "publish", "--profile", profile]];
  execFile(cmd[0], cmd[1], { env, timeout: 180_000 }, (err) => {
    healInFlight.delete(profile);
    anyLog("heal-done", { profile, ok: !err });
  });
}

async function collectBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return chunks.length ? Buffer.concat(chunks) : undefined;
}

function upstreamHeaders(reqHeaders, token) {
  const headers = {};
  for (const [k, v] of Object.entries(reqHeaders)) {
    const lk = k.toLowerCase();
    if (HOP_BY_HOP.has(lk) || lk === "authorization" || lk === "x-api-key" || lk === "host" || lk === "content-length") continue;
    headers[lk] = v;
  }
  headers["authorization"] = `Bearer ${token}`;
  return headers;
}

async function forward(req, body, token) {
  return fetch(UPSTREAM + req.url, {
    method: req.method,
    headers: upstreamHeaders(req.headers, token),
    body,
    redirect: "manual",
  });
}

function relayHeaders(up) {
  const outHeaders = {};
  up.headers.forEach((v, k) => {
    const lk = k.toLowerCase();
    // fetch() already decoded the body: never forward the original framing
    // or content-encoding, or the client would try to decompress plain bytes.
    if (HOP_BY_HOP.has(lk) || lk === "content-length" || lk === "content-encoding") return;
    outHeaders[lk] = v;
  });
  return outHeaders;
}

async function streamBack(res, up) {
  res.writeHead(up.status, relayHeaders(up));
  if (up.body) {
    for await (const chunk of up.body) {
      if (!res.write(chunk)) await new Promise((resolve) => res.once("drain", resolve));
    }
  }
  res.end();
}

function log(profile, method, path, status) {
  const ts = new Date().toISOString().replace("T", " ").slice(0, 19);
  console.log(`${ts} ${profile} ${method} ${path} -> ${status}`);
}

async function handleAny(req, res) {
  const body = await collectBody(req);
  const tried = new Set();
  let lastErr = null;
  for (let attempt = 0; attempt < MAX_TRIES; attempt++) {
    const pick = pickAny(loadState(), tried);
    if (!pick) break;
    tried.add(pick.profile);
    let up;
    try {
      up = await forward(req, body, pick.token);
    } catch (err) {
      lastErr = err;
      anyLog("upstream-error", { profile: pick.profile, error: String(err.message || err) });
      continue;
    }
    if (up.status === 401 || up.status === 429) {
      const kind = up.status === 401 ? "401" : "429";
      up.body?.cancel();
      markCooldown(pick.profile, kind);
      if (kind === "401") heal(pick.profile);
      anyLog("failover", { profile: pick.profile, kind, attempt: attempt + 1 });
      log(`any(${pick.profile})`, req.method, req.url, `${up.status}-failover`);
      continue;
    }
    markUsed(pick.profile);
    await streamBack(res, up);
    log(`any(${pick.profile})`, req.method, req.url, up.status);
    return;
  }
  const msg = lastErr
    ? `any-proxy: upstream error: ${lastErr.message || lastErr}`
    : "any-proxy: no healthy profile available";
  const status = lastErr ? 502 : 503;
  res.writeHead(status, { "content-type": "text/plain", "content-length": Buffer.byteLength(msg) });
  res.end(msg);
  log("any", req.method, req.url, status);
}

const server = http.createServer((req, res) => {
  handleAny(req, res).catch((err) => {
    try {
      const msg = `any-proxy: handler error: ${err.message}`;
      if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" });
      res.end(msg);
    } catch {}
    log("any", req.method, req.url, "502-handler");
  });
});
server.listen(ANY_PORT, "127.0.0.1", () => console.log(`claude-any-proxy: ANY on 127.0.0.1:${ANY_PORT}`));
