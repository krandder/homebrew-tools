// kimi-any-proxy — the ANY-port for kimi profiles (sibling of the claude/codex
// any-proxies): per request, pick the healthiest kimi profile (fresh
// access_token, not in cooldown; spread-load) and forward to api.kimi.com
// with it. On 401/429: cool down, heal (leader: ai-token kimi publish;
// follower: kimi-any-mirror), retry the SAME request with the next profile.
// Token source: ~/.kimi-profiles/<p>/credentials.json (900s TTL tokens).
import http from "node:http";
import { readFileSync, writeFileSync, renameSync, appendFileSync, readdirSync, existsSync } from "node:fs";
import { execFile } from "node:child_process";

const HOME = process.env.HOME;
const PROFILES_DIR = process.env.KIMI_PROFILES_DIR || `${HOME}/.kimi-profiles`;
const UPSTREAM = process.env.CLAUDE_PROXY_UPSTREAM || "https://api.kimi.com";
const ANY_PORT = Number(process.env.CLAUDE_PROXY_ANY_PORT || 7812);
const NO_HEAL = process.env.CLAUDE_PROXY_NO_HEAL === "1";
const STATE_FILE = `${HOME}/.kimi-code/any-state.json`;
const ANY_LOG = `${HOME}/.kimi-code/any.log`;
const COOLDOWN_401_S = 900;
const COOLDOWN_429_S = 1800;
const MIN_FRESH_S = 30;
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
  try { appendFileSync(ANY_LOG, JSON.stringify({ ts: nowS(), event, via: "kimi-any-proxy", ...kv }) + "\n"); } catch {}
}

const loadState = () => readJson(STATE_FILE) || {};
const saveState = (s) => writeJsonAtomic(STATE_FILE, s);

function freshToken(profile) {
  const d = readJson(`${PROFILES_DIR}/${profile}/credentials.json`);
  if (!d || !d.access_token) return null;
  if ((d.expires_at || 0) - nowS() < MIN_FRESH_S) return null;
  return { token: d.access_token };
}

function profiles() {
  try {
    return readdirSync(PROFILES_DIR).filter((p) =>
      !p.startsWith(".") && existsSync(`${PROFILES_DIR}/${p}/credentials.json`));
  } catch { return []; }
}

function pickAny(state, exclude) {
  let best = null;
  for (const p of profiles()) {
    if (exclude.has(p)) continue;
    const ent = state[p] || {};
    if ((ent.cooldown_401_until || 0) > nowS()) continue;
    if ((ent.cooldown_429_until || 0) > nowS()) continue;
    const info = freshToken(p);
    if (!info) continue;
    const last = ent.last_used || 0;
    if (!best || last < best.last) best = { profile: p, last, ...info };
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
function heal(profile) {
  if (NO_HEAL || healInFlight.has(profile)) return;
  healInFlight.add(profile);
  anyLog("heal-start", { profile });
  execFile(`${HOME}/.local/bin/ai-token`, ["kimi", "publish", "--profile", profile],
    { timeout: 180_000 }, (err) => {
      healInFlight.delete(profile);
      anyLog("heal-done", { profile, ok: !err });
    });
}

async function collectBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return chunks.length ? Buffer.concat(chunks) : undefined;
}

function upstreamHeaders(reqHeaders, info) {
  const headers = {};
  for (const [k, v] of Object.entries(reqHeaders)) {
    const lk = k.toLowerCase();
    if (HOP_BY_HOP.has(lk) || lk === "authorization" || lk === "x-api-key" || lk === "host" || lk === "content-length") continue;
    headers[lk] = v;
  }
  headers["authorization"] = `Bearer ${info.token}`;
  return headers;
}

async function forward(req, body, info) {
  return fetch(UPSTREAM + req.url, {
    method: req.method,
    headers: upstreamHeaders(req.headers, info),
    body,
    redirect: "manual",
  });
}

function relayHeaders(up) {
  const outHeaders = {};
  up.headers.forEach((v, k) => {
    const lk = k.toLowerCase();
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
      up = await forward(req, body, pick);
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
    ? `kimi-any-proxy: upstream error: ${lastErr.message || lastErr}`
    : "kimi-any-proxy: no healthy profile available";
  const status = lastErr ? 502 : 503;
  res.writeHead(status, { "content-type": "text/plain", "content-length": Buffer.byteLength(msg) });
  res.end(msg);
  log("any", req.method, req.url, status);
}

const server = http.createServer((req, res) => {
  handleAny(req, res).catch((err) => {
    try {
      const msg = `kimi-any-proxy: handler error: ${err.message}`;
      if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" });
      res.end(msg);
    } catch {}
    log("any", req.method, req.url, "502-handler");
  });
});
server.listen(ANY_PORT, "127.0.0.1", () => console.log(`kimi-any-proxy: ANY on 127.0.0.1:${ANY_PORT}`));
