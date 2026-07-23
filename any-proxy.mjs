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
import { readFileSync, writeFileSync, renameSync, appendFileSync, readdirSync } from "node:fs";
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
const COOLDOWN_5XX_S = 300;
const MIN_FRESH_MS = 60_000;
const MAX_TRIES = 3;
// wedge fix (2026-07-22): an upstream that accepts but never answers parked
// requests forever; retried clients stacked sockets until the listener wedged.
const UPSTREAM_TIMEOUT_MS = Number(process.env.CLAUDE_PROXY_UPSTREAM_TIMEOUT_MS || 120_000);
const REQUEST_BUDGET_MS = Number(process.env.CLAUDE_PROXY_REQUEST_BUDGET_MS || 900_000);

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
// Profile universe: the published shared files are the source of truth (a new
// vault enrollment appears here with no config change); the registry file is
// kept only as a backward-compatible superset.
function candidates() {
  const names = new Set(Object.keys(loadRegistry()));
  try {
    for (const fn of readdirSync(sharedDir)) {
      if (fn.endsWith(".json") && !fn.includes(".sync-conflict-") && !fn.includes(".suspect"))
        names.add(fn.slice(0, -5));
    }
  } catch {}
  return names;
}
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
  for (const p of candidates()) {
    if (exclude.has(p)) continue;
    const ent = state[p] || {};
    if ((ent.cooldown_401_until || 0) > nowS()) continue;
    if ((ent.cooldown_429_until || 0) > nowS()) continue;
    if ((ent.cooldown_5xx_until || 0) > nowS()) continue;
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
  const secs = kindS === "401" ? COOLDOWN_401_S : kindS === "429" ? COOLDOWN_429_S : COOLDOWN_5XX_S;
  ent[`cooldown_${kindS}_until`] = nowS() + secs;
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
    if (HOP_BY_HOP.has(lk) || lk === "authorization" || lk === "x-api-key" ||
        lk === "x-futarchy-agent" || lk === "host" || lk === "content-length") continue;
    headers[lk] = v;
  }
  headers["authorization"] = `Bearer ${token}`;
  return headers;
}

async function forward(req, body, token) {
  // The timeout covers waiting for the upstream RESPONSE HEADERS only; once
  // headers arrive the timer is cleared and the body streams untimed (legit
  // Anthropic streams run 10+ min). An abort surfaces as a fetch throw ->
  // upstream-error failover to the next profile, same as any fetch error.
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), UPSTREAM_TIMEOUT_MS);
  try {
    return await fetch(UPSTREAM + req.url, {
      method: req.method,
      headers: upstreamHeaders(req.headers, token),
      body,
      redirect: "manual",
      signal: ctrl.signal,
    });
  } finally {
    clearTimeout(timer);
  }
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

async function streamBack(res, up, profile, agent, reqUrl) {
  res.writeHead(up.status, relayHeaders(up));
  // usage tap: buffer only billable message calls (small bodies) so per-request
  // token counts land in any-usage.jsonl with the TRUE serving profile.
  const tap = (up.status === 200 && profile && reqUrl.startsWith("/v1/messages")) ? [] : null;
  if (up.body) {
    for await (const chunk of up.body) {
      if (tap) tap.push(chunk);
      if (!res.write(chunk)) await new Promise((resolve) => res.once("drain", resolve));
    }
  }
  res.end();
  if (tap) recordUsage(profile, agent, Buffer.concat(tap).toString("utf8"), up.headers.get("content-type") || "");
}

const USAGE_LOG = `${HOME}/.claude-token/any-usage.jsonl`;

function splitCacheWrites(u) {
  const cc = u.cache_creation || {};
  let w5 = cc.ephemeral_5m_input_tokens || 0;
  const w1 = cc.ephemeral_1h_input_tokens || 0;
  const tot = u.cache_creation_input_tokens || 0;
  if (tot > w5 + w1) w5 += tot - w5 - w1;
  return [w5, w1];
}

function usageFromSSE(text) {
  let start = null, out = 0;
  for (const line of text.split("\n")) {
    if (!line.startsWith("data:")) continue;
    let ev; try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
    if (ev.type === "message_start" && ev.message) start = ev.message;
    else if (ev.type === "message_delta" && ev.usage && ev.usage.output_tokens != null) out = ev.usage.output_tokens;
  }
  if (!start || !start.id) return null;
  const u = start.usage || {};
  const [w5, w1] = splitCacheWrites(u);
  return { id: start.id, model: start.model, input_tokens: u.input_tokens || 0,
           output_tokens: out, cache_read: u.cache_read_input_tokens || 0,
           cache_write_5m: w5, cache_write_1h: w1 };
}

function usageFromJSON(text) {
  let d; try { d = JSON.parse(text); } catch { return null; }
  if (!d || !d.usage || !d.id) return null;
  const u = d.usage;
  const [w5, w1] = splitCacheWrites(u);
  return { id: d.id, model: d.model, input_tokens: u.input_tokens || 0,
           output_tokens: u.output_tokens || 0, cache_read: u.cache_read_input_tokens || 0,
           cache_write_5m: w5, cache_write_1h: w1 };
}

function recordUsage(profile, agent, text, contentType) {
  try {
    const u = contentType.includes("text/event-stream") ? usageFromSSE(text) : usageFromJSON(text);
    if (!u) return;
    appendFileSync(USAGE_LOG, JSON.stringify({
      source: "claude-proxy", profile, agent, ts: Date.now() / 1000, request_id: u.id,
      model: u.model, input_tokens: u.input_tokens, output_tokens: u.output_tokens,
      cache_read: u.cache_read, cache_write_5m: u.cache_write_5m, cache_write_1h: u.cache_write_1h,
    }) + "\n");
  } catch {}
}

function requestAgent(req) {
  const auth = String(req.headers.authorization || req.headers["x-api-key"] || "");
  const match = auth.match(/token-proxy-managed:([A-Za-z0-9._/-]{1,96})/);
  return match ? match[1] : null;
}

function log(profile, method, path, status) {
  const ts = new Date().toISOString().replace("T", " ").slice(0, 19);
  console.log(`${ts} ${profile} ${method} ${path} -> ${status}`);
}

async function handleAny(req, res) {
  const body = await collectBody(req);
  const agent = requestAgent(req);
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
    if (up.status === 401 || up.status === 429 || up.status >= 500) {
      const kind = up.status === 401 ? "401" : up.status === 429 ? "429" : "5xx";
      up.body?.cancel();
      markCooldown(pick.profile, kind);
      if (kind === "401") heal(pick.profile);
      anyLog("failover", { profile: pick.profile, kind, status: up.status, attempt: attempt + 1 });
      log(`any(${pick.profile})`, req.method, req.url, `${up.status}-failover`);
      continue;
    }
    markUsed(pick.profile);
    await streamBack(res, up, pick.profile, agent, req.url);
    log(`any(${pick.profile})`, req.method, req.url, up.status);
    return;
  }
  const msg = lastErr
    ? `any-proxy: upstream error: ${lastErr.message || lastErr}`
    : "any-proxy: no healthy profile available";
  const status = lastErr ? 502 : 503;
  if (!lastErr) {
    // pool-empty is a fleet-level event: log it, and alert kelvin at most
    // once per 30 min (a session only ever sees retries; the 503 cause was
    // invisible until now).
    anyLog("pool-empty", { tried: [...tried] });
    const s = loadState();
    const last = s.pool_alert_last || 0;
    if (nowS() - last > 1800) {
      s.pool_alert_last = nowS();
      saveState(s);
      execFile(`${HOME}/.local/bin/fleet-msg`, ["send", "--to", "kelvin",
        "--from", "claude-any-proxy", "--kind", "notify", "--create-actor",
        "--body", `claude any-proxy pool EMPTY (503): no healthy profile available; tried=[${[...tried].join(",")}]`],
        () => {});
    }
  }
  res.writeHead(status, { "content-type": "text/plain", "content-length": Buffer.byteLength(msg) });
  res.end(msg);
  log("any", req.method, req.url, status);
}

let inflight = 0;
const startedMs = Date.now();

const server = http.createServer((req, res) => {
  if (req.url === "/healthz") {
    // cheap liveness for watchdogs/wrappers: answered without touching
    // profile selection or any state file.
    const body = JSON.stringify({ ok: true, inflight, uptime_s: Math.floor((Date.now() - startedMs) / 1000) });
    res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(body) });
    res.end(body);
    return;
  }
  inflight++;
  // hard per-request ceiling: even a never-ending stream is reaped, so a
  // single request can never park a socket past the budget.
  const budget = setTimeout(() => {
    anyLog("request-budget", { url: req.url, ms: REQUEST_BUDGET_MS });
    res.destroy();
  }, REQUEST_BUDGET_MS);
  res.on("close", () => clearTimeout(budget));
  handleAny(req, res).catch((err) => {
    try {
      const msg = `any-proxy: handler error: ${err.message}`;
      if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" });
      res.end(msg);
    } catch {}
    log("any", req.method, req.url, "502-handler");
  }).finally(() => { inflight--; });
});
server.headersTimeout = 65_000;   // stalled client headers die
server.requestTimeout = 300_000;  // stalled client bodies die
server.listen(ANY_PORT, "127.0.0.1", () => console.log(`claude-any-proxy: ANY on 127.0.0.1:${ANY_PORT}`));
