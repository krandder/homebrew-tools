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
const COOLDOWN_5XX_S = 300;
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

const SHARED_DIR = process.env.KIMI_SHARED_DIR || `${HOME}/shared/kimi-tokens`;

function freshToken(profile) {
  let d = readJson(`${PROFILES_DIR}/${profile}/credentials.json`);
  if (!d || !d.access_token) d = readJson(`${SHARED_DIR}/${profile}.json`);
  if (!d || !d.access_token) return null;
  if ((d.expires_at || 0) - nowS() < MIN_FRESH_S) return null;
  return { token: d.access_token };
}

function profiles() {
  // profile universe: local leader layout ∪ published shared files
  const names = new Set();
  try {
    readdirSync(PROFILES_DIR).forEach((p) => {
      if (!p.startsWith(".") && existsSync(`${PROFILES_DIR}/${p}/credentials.json`)) names.add(p);
    });
  } catch {}
  try {
    readdirSync(SHARED_DIR).forEach((fn) => {
      if (fn.endsWith(".json") && !fn.includes(".sync-conflict-")) names.add(fn.slice(0, -5));
    });
  } catch {}
  return [...names];
}

function pickAny(state, exclude) {
  let best = null;
  for (const p of profiles()) {
    if (exclude.has(p)) continue;
    const ent = state[p] || {};
    if ((ent.cooldown_401_until || 0) > nowS()) continue;
    if ((ent.cooldown_429_until || 0) > nowS()) continue;
    if ((ent.cooldown_5xx_until || 0) > nowS()) continue;
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

async function streamBack(res, up, profile, reqUrl) {
  res.writeHead(up.status, relayHeaders(up));
  // usage tap: buffer successful responses so per-request token counts land in
  // any-usage.jsonl with the TRUE serving profile.
  const tap = (up.status === 200 && profile) ? [] : null;
  if (up.body) {
    for await (const chunk of up.body) {
      if (tap) tap.push(chunk);
      if (!res.write(chunk)) await new Promise((resolve) => res.once("drain", resolve));
    }
  }
  res.end();
  if (tap) recordUsage(profile, Buffer.concat(tap).toString("utf8"), up.headers.get("content-type") || "");
}

const USAGE_LOG = `${HOME}/.kimi-code/any-usage.jsonl`;

function usageFromChatAPI(text, isSSE) {
  // kimi (OpenAI-style chat): non-stream JSON carries usage; streams carry it
  // on the final chunk when the client sets stream_options.include_usage.
  let last = null;
  if (isSSE) {
    for (const line of text.split("\n")) {
      if (!line.startsWith("data:")) continue;
      let ev; try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
      if (ev.usage) last = ev;
    }
  } else {
    try { const d = JSON.parse(text); if (d && d.usage) last = d; } catch { last = null; }
  }
  if (!last || !last.usage || !last.id) return null;
  const u = last.usage;
  const cached = (u.prompt_tokens_details || {}).cached_tokens || 0;
  return { id: last.id, model: last.model,
           input_tokens: Math.max(0, (u.prompt_tokens || 0) - cached),
           output_tokens: u.completion_tokens || 0,
           cache_read: cached, cache_write_5m: 0, cache_write_1h: 0 };
}

function recordUsage(profile, text, contentType) {
  try {
    const u = usageFromChatAPI(text, contentType.includes("text/event-stream"));
    if (!u) return;
    appendFileSync(USAGE_LOG, JSON.stringify({
      source: "kimi-proxy", profile, ts: Date.now() / 1000, request_id: u.id,
      model: u.model, input_tokens: u.input_tokens, output_tokens: u.output_tokens,
      cache_read: u.cache_read, cache_write_5m: 0, cache_write_1h: 0,
    }) + "\n");
  } catch {}
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
    await streamBack(res, up, pick.profile, req.url);
    log(`any(${pick.profile})`, req.method, req.url, up.status);
    return;
  }
  const msg = lastErr
    ? `kimi-any-proxy: upstream error: ${lastErr.message || lastErr}`
    : "kimi-any-proxy: no healthy profile available";
  const status = lastErr ? 502 : 503;
  if (!lastErr) {
    anyLog("pool-empty", { tried: [...tried] });
    const s = loadState();
    const last = s.pool_alert_last || 0;
    if (nowS() - last > 1800) {
      s.pool_alert_last = nowS();
      saveState(s);
      execFile(`${HOME}/.local/bin/fleet-msg`, ["send", "--to", "kelvin",
        "--from", "kimi-any-proxy", "--kind", "notify", "--create-actor",
        "--body", `kimi any-proxy pool EMPTY (503): no healthy profile available; tried=[${[...tried].join(",")}]`],
        () => {});
    }
  }
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
