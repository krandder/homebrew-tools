// codex-any-proxy — the ANY-port for codex profiles (sibling of the
// claude-token any-proxy, same loop):
//   per request, pick the healthiest codex profile (fresh JWT AT, not in
//   cooldown; spread-load) and forward to the codex backend with that
//   profile's access_token (+ chatgpt-account-id when known). On upstream
//   401/429: cool the profile down (shared with ai-any's codex side:
//   ~/.codex-profiles/any-state.json, seconds epoch), heal async
//   (leader: ai-token codex publish; follower: codex-any-mirror), and retry
//   the SAME request with the next-best profile — invisible mid-turn failover.
import http from "node:http";
import { readFileSync, writeFileSync, renameSync, appendFileSync, readdirSync, existsSync } from "node:fs";
import { execFile } from "node:child_process";

const HOME = process.env.HOME;
const PROFILES_DIR = process.env.CODEX_PROFILES_DIR || `${HOME}/.codex-profiles`;
const UPSTREAM = process.env.CLAUDE_PROXY_UPSTREAM || "https://chatgpt.com/backend-api/codex";
const ANY_PORT = Number(process.env.CLAUDE_PROXY_ANY_PORT || 7810);
const NO_HEAL = process.env.CLAUDE_PROXY_NO_HEAL === "1";
const STATE_FILE = `${PROFILES_DIR}/any-state.json`;
const ANY_LOG = `${PROFILES_DIR}/any.log`;
const COOLDOWN_401_S = 900;
const COOLDOWN_429_S = 1800;
const MIN_FRESH_S = 60;
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
  try { appendFileSync(ANY_LOG, JSON.stringify({ ts: nowS(), event, via: "codex-any-proxy", ...kv }) + "\n"); } catch {}
}

const loadState = () => readJson(STATE_FILE) || {};
const saveState = (s) => writeJsonAtomic(STATE_FILE, s);

function jwtExp(token) {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(Buffer.from(part, "base64").toString()).exp || 0;
  } catch { return 0; }
}

function freshToken(profile) {
  const d = readJson(`${PROFILES_DIR}/${profile}/.codex/auth.json`);
  if (!d || !d.tokens || !d.tokens.access_token) return null;
  const at = d.tokens.access_token;
  if (jwtExp(at) - nowS() < MIN_FRESH_S) return null;
  return { token: at, accountId: d.tokens.account_id || null };
}

function profiles() {
  try {
    return readdirSync(PROFILES_DIR).filter((p) =>
      !p.startsWith(".") && existsSync(`${PROFILES_DIR}/${p}/.codex/auth.json`));
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
function roleOf() {
  try {
    const cfg = readFileSync(`${HOME}/.codex-token/config`, "utf8");
    const m = cfg.match(/^mode=(\w+)/m);
    if (m) return m[1] === "follower" ? "follower" : "leader";
  } catch {}
  return (process.env.CLAUDE_PROXY_FOLLOWER === "1") ? "follower" : "leader";
}
function heal(profile) {
  if (NO_HEAL || healInFlight.has(profile)) return;
  healInFlight.add(profile);
  const role = roleOf();
  anyLog("heal-start", { profile, role });
  const cmd = role === "follower"
    ? [`${HOME}/.local/bin/codex-any-mirror`, [profile]]
    : [`${HOME}/.local/bin/ai-token`, ["codex", "publish", "--profile", profile]];
  execFile(cmd[0], cmd[1], { timeout: 180_000 }, (err) => {
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
    if (HOP_BY_HOP.has(lk) || lk === "authorization" || lk === "x-api-key" ||
        lk === "host" || lk === "content-length" || lk === "chatgpt-account-id") continue;
    headers[lk] = v;
  }
  headers["authorization"] = `Bearer ${info.token}`;
  if (info.accountId) headers["chatgpt-account-id"] = info.accountId;
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
    ? `codex-any-proxy: upstream error: ${lastErr.message || lastErr}`
    : "codex-any-proxy: no healthy profile available";
  const status = lastErr ? 502 : 503;
  res.writeHead(status, { "content-type": "text/plain", "content-length": Buffer.byteLength(msg) });
  res.end(msg);
  log("any", req.method, req.url, status);
}

const server = http.createServer((req, res) => {
  handleAny(req, res).catch((err) => {
    try {
      const msg = `codex-any-proxy: handler error: ${err.message}`;
      if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" });
      res.end(msg);
    } catch {}
    log("any", req.method, req.url, "502-handler");
  });
});
server.listen(ANY_PORT, "127.0.0.1", () => console.log(`codex-any-proxy: ANY on 127.0.0.1:${ANY_PORT}`));
