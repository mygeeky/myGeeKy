// WISEP -- Wisely, a Systematic Statistically adapted system for API calling: a port of the desktop's wisep.py.
// Every call to an open database (OpenAlex first) goes through wiseFetch: the kept answer when it is good enough, a
// fresh one when it is worth it -- the chance it changed (its own change history) x how much you care (what you open,
// and when), against a bar that rises as the day's budget runs ahead of the day. A daily budget per source, spaced
// calls, backing off on 429/503, OpenAlex's polite pool, and the kept answer when a source is down. The rules are the
// desktop's (tests/test_wisep.py checks both decide the same). Nothing leaves the phone but the requests themselves.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fetchT } from './net';
import { getOpenAlexKey, setOpenAlexKey } from './storage';

export const CONTACT = 'support@mygeeky.org';
const KEY = 'mygeeky.wisep';
const MAX_ANSWERS = 300;              // the phone keeps fewer than the computer
const HALF_LIFE_DAYS = 14;
const FORCE_ALLOWANCE = 1.2;
const TOP_UP_HOUR = 20, TOP_UP_SHARE = 0.5, TOP_UP_MAX = 15, TOP_UP_FLOOR = 0.15;
export const TUNE_MIN_ANSWERS = 5, TUNE_MIN_HOURS = 14 * 24;
export const PROVEN_DAYS = 14, PROVEN_LOOKS = 100, PROVEN_SAVED = 0.4, PROVEN_FAILED = 0.15;
const MODULE_GAP_HOURS = 0.5;
export const RESERVE = 0.05;
export type Mode = 'auto' | 'on' | 'off';

export const SOURCES: Record<string, [number, number, string[]]> = {     // the budget: a guess until the source says
  openalex: [900, 0.12, ['api.openalex.org']], crossref: [500, 0.2, ['api.crossref.org']], arxiv: [300, 3.1, ['export.arxiv.org']],
  biorxiv: [300, 0.5, ['api.biorxiv.org']], zenodo: [300, 2.1, ['zenodo.org']], ncbi: [500, 0.35, ['eutils.ncbi.nlm.nih.gov']],
  figshare: [300, 0.3, ['api.figshare.com']], huggingface: [300, 0.2, ['huggingface.co']],
};
export const KINDS: Record<string, [number, number, number]> = {
  search: [24, 1, 72], citations: [48, 6, 168], entity: [72, 6, 336], static: [720, 168, 2160],
};

// --------------------------------------------------------------------------- the rules (the desktop has the same)
const r4 = (x: number) => Math.round(x * 10000) / 10000;
export const changeRate = (changes: number, watchedHours: number, priorHours: number) => (changes + 1) / (Math.max(watchedHours, 0) + priorHours);
export const pChanged = (rate: number, ageHours: number) => 1 - Math.exp(-rate * Math.max(ageHours, 0));

export function care(opens: number[], hour: number, most: number): number {
  const total = opens.reduce((a, b) => a + b, 0);
  if (most <= 0) return 0.5;
  if (total <= 0) return 0.1;
  let soon = 0;
  for (let i = 0; i < 3; i++) soon += opens[(hour + i) % 24];
  soon /= total;
  return r4(0.1 + 0.9 * Math.min(1, total / most) * (0.5 + 0.5 * Math.min(1, soon / 0.125)));
}

export function threshold(used: number, budget: number, dayFrac: number): number {
  if (used >= budget) return Infinity;
  const pace = used / Math.max(1, budget * Math.max(dayFrac, 0.02));
  return r4(0.15 * (1 + 3 * Math.max(0, pace - 0.5)));
}

export type Decision = { action: 'fetch' | 'cache' | 'none'; why: string; worth: number; bar: number | null };

/** What an ask costs against the source's budget (wisep.credit_cost): 10 for a text search, 1 for a filtered list, 0 for one record by id. */
/** OpenAlex: a text search costs ten credits (wisep.SEARCH_CREDITS, measured from its own headers). */
export const SEARCH_CREDITS = 10;
export function creditCost(source: string, url: string): number {
  if (source !== 'openalex') return 1;
  let path = '', query = '';
  try { const u = new URL(url); path = decodeURIComponent(u.pathname); query = decodeURIComponent(u.search.slice(1)); } catch { return 1; }
  if (/(^|&)search=|\.search:/.test(query)) return SEARCH_CREDITS;
  if (['filter=', 'sort=', 'group_by=', 'sample='].some((k) => query.includes(k))) return 1;
  const seg = path.split('/');
  const one = (path.match(/\//g) ?? []).length >= 2 && !path.endsWith('/')
    && ['works', 'authors', 'sources', 'institutions', 'topics', 'concepts', 'funders', 'publishers'].includes(seg[1]);
  return one ? 0 : 1;
}

/** [used, budget, dayFrac] to decide with (wisep.server_budget): the source's own numbers when it gave them, else ours. */
export function serverBudget(limit: number, remaining: number, resetSeconds: number, usedHere: number, guess: number, dayFracHere: number): [number, number, number] {
  if (limit <= 0) return [usedHere, guess, dayFracHere];
  const budget = Math.max(1, Math.trunc(limit * (1 - RESERVE)));
  const used = Math.max(0, limit - Math.max(remaining, 0));
  return [used, budget, r4(Math.min(1, Math.max(0, 1 - resetSeconds / 86400)))];
}

/** A kind's prior hours between changes from what this phone watched (wisep.tuned_prior), or null while too little. */
export function tunedPrior(changes: number, hours: number, answers: number, kind: string): number | null {
  const [def, least, most] = KINDS[kind] ?? KINDS.entity;
  if (answers < TUNE_MIN_ANSWERS || hours < TUNE_MIN_HOURS) return null;
  return Math.round(Math.min(Math.max((hours + def) / (changes + 1), least), 4 * most) * 100) / 100;
}

export type Proven = { proven: boolean; days: number; looks: number; saved: number; failed: number };
/** Has WISEP earned the right to decide alone (wisep.proven_by), from the daily tallies. */
export function provenBy(days: { day: string; asked?: number; saved?: number; stale?: number; failed?: number }[]): Proven {
  const used = new Set(days.filter((d) => (d.asked ?? 0) + (d.saved ?? 0)).map((d) => d.day));
  let asked = 0, saved = 0, bad = 0;
  for (const d of days) { asked += d.asked ?? 0; saved += d.saved ?? 0; bad += (d.failed ?? 0) + (d.stale ?? 0); }
  const looks = asked + saved;
  const share = looks ? Math.round((saved / looks) * 1000) / 1000 : 0, failed = asked ? Math.round((bad / asked) * 1000) / 1000 : 0;
  return { proven: used.size >= PROVEN_DAYS && looks >= PROVEN_LOOKS && share >= PROVEN_SAVED && failed < PROVEN_FAILED,
    days: used.size, looks, saved: share, failed };
}

/** The desktop's wisep.decide. `bar` null where the desktop's is infinite (JSON has no Infinity). */
export function decide(ageHours: number | null, kind: string, changes: number, watchedHours: number, careNow: number, used: number,
  budget: number, dayFrac: number, forced = false, paused = false, priorHours: number | null = null): Decision {
  const [defPrior, least, most] = KINDS[kind] ?? KINDS.entity;
  const prior = priorHours || defPrior;
  if (ageHours === null) {
    if (paused || used >= budget * FORCE_ALLOWANCE) return { action: 'none', why: 'nothing kept, and the source is resting', worth: 0, bar: 0 };
    return { action: 'fetch', why: 'nothing kept yet', worth: 1, bar: 0 };
  }
  if (paused) return { action: 'cache', why: 'the source asked us to wait', worth: 0, bar: 0 };
  if (ageHours < least) return { action: 'cache', why: 'asked moments ago', worth: 0, bar: 0 };
  if (forced) {
    const ok = used < budget * FORCE_ALLOWANCE;
    return { action: ok ? 'fetch' : 'cache', why: ok ? 'you asked' : "you asked, but the day's budget is spent", worth: 1, bar: 0 };
  }
  if (ageHours >= most) {
    const ok = used < budget;
    return { action: ok ? 'fetch' : 'cache', why: 'too old to trust', worth: 1, bar: 0 };
  }
  const worth = r4(pChanged(changeRate(changes, watchedHours, prior), ageHours) * careNow);
  const bar = threshold(used, budget, dayFrac);
  const shown = bar === Infinity ? null : r4(bar);
  return worth >= bar ? { action: 'fetch', why: "likely changed, and you'll look", worth, bar: shown }
    : { action: 'cache', why: 'probably unchanged, or not wanted now', worth, bar: shown };
}

export function sourceOf(url: string): string | null {
  let host = '';
  try { host = new URL(url).hostname.toLowerCase(); } catch { return null; }
  for (const [name, [, , hosts]] of Object.entries(SOURCES)) if (hosts.includes(host)) return name;
  return null;
}

export function kindOf(source: string, url: string): string {
  let path = '', query = '';
  try { const u = new URL(url); path = decodeURIComponent(u.pathname); query = decodeURIComponent(u.search.slice(1)); } catch { return 'search'; }
  if (source === 'openalex') {
    if (path.startsWith('/works') && query.includes('cites:')) return 'citations';
    if (path.startsWith('/topics') || path.includes('/doi:') || path.startsWith('/works/https://doi.org')) return 'static';
    if (path.startsWith('/authors') && !query.includes('search=')) return 'entity';
    return 'search';
  }
  return 'search';
}

/** What you open, as WISEP names it (the desktop's PAGES): the navigation's page ids -> the page answers are kept under. */
export const PAGES: Record<string, string> = { 'model:cited': 'you:cited', 'you:cited': 'you:cited', 'model:model': 'you:model', 'you:model': 'you:model',
  'market:research': 'world:papers', papers: 'world:papers', 'market:repos': 'repos:rising', 'repos:rising': 'repos:rising',
  'grow:wins': 'grow:wins', 'grow:paths': 'grow:paths', 'grow:data:new': 'grow:data:new', 'you:month': 'you:model', 'model:month': 'you:model',
  'researchers:new': 'circle:researchers', 'researchers:following': 'circle:researchers', 'researchers:suggested': 'circle:researchers', 'researchers:network': 'circle:researchers' };
export const canonical = (page: string) => (page.startsWith('admin:') || page.startsWith('you:admin') ? 'you:admin' : PAGES[page] ?? page);

// --------------------------------------------------------------------------- the store (one JSON value in AsyncStorage)
type Answer = { url: string; source: string; kind: string; body: string; digest: string; fetched: number; checks: number; changes: number;
  watched: number; used: number; page: string };
type State = { answers: Record<string, Answer>; calls: Record<string, Record<string, { asked: number; saved: number; stale: number; failed: number; topup: number; credits?: number }>>;
  opens: Record<string, { n: number[]; at: number }>; paused: Record<string, number>; priors?: Record<string, number>; tunedDay?: string; mode?: Mode;
  github?: Record<string, { asked: number; saved: number }>; server?: Record<string, { limit: number; remaining: number; resetAt: number; key: boolean }> };
let mem: State | null = null;
const last: Record<string, number> = {};

async function load(): Promise<State> {
  if (mem) return mem;
  try {
    const raw = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '{}');
    mem = { answers: raw.answers ?? {}, calls: raw.calls ?? {}, opens: raw.opens ?? {}, paused: raw.paused ?? {}, priors: raw.priors ?? {},
      tunedDay: raw.tunedDay ?? '', mode: (['auto', 'on', 'off'].includes(raw.mode) ? raw.mode : 'auto') as Mode, github: raw.github ?? {},
      server: raw.server ?? {} };
  } catch {
    mem = { answers: {}, calls: {}, opens: {}, paused: {} };
  }
  return mem;
}

let saving: ReturnType<typeof setTimeout> | null = null;
function save(): void {                       // written once things settle, not on every answer
  if (saving) clearTimeout(saving);
  saving = setTimeout(() => {
    saving = null;
    if (!mem) return;
    const keep = Object.entries(mem.answers).sort((a, b) => b[1].used - a[1].used).slice(0, MAX_ANSWERS);
    mem.answers = Object.fromEntries(keep);
    const days = Object.keys(mem.calls).sort().reverse().slice(0, 30);
    mem.calls = Object.fromEntries(days.map((d) => [d, mem!.calls[d]]));
    AsyncStorage.setItem(KEY, JSON.stringify(mem)).catch(() => undefined);
  }, 1500);
}

const dayOf = (t: number) => { const d = new Date(t); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const dayFrac = (t: number) => { const d = new Date(t); return (d.getHours() * 3600 + d.getMinutes() * 60 + d.getSeconds()) / 86400; };
const fade = (n: number, ms: number) => n * Math.pow(0.5, Math.max(ms, 0) / 86400000 / HALF_LIFE_DAYS);
function digest(s: string): string {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0).toString(16);
}
function count(st: State, source: string, field: 'asked' | 'saved' | 'stale' | 'failed' | 'topup' | 'credits', now: number, n = 1) {
  const d = (st.calls[dayOf(now)] ??= {});
  const c = (d[source] ??= { asked: 0, saved: 0, stale: 0, failed: 0, topup: 0, credits: 0 });
  c[field] = (c[field] ?? 0) + n;
}

function noteServer(st: State, source: string, res: Response, now: number, key: boolean) {
  const limit = Number(res.headers.get('X-RateLimit-Limit')) || 0, remaining = Number(res.headers.get('X-RateLimit-Remaining')) || 0;
  const reset = Number(res.headers.get('X-RateLimit-Reset')) || 0;
  if (limit > 0) (st.server ??= {})[source] = { limit, remaining, resetAt: now + reset * 1000, key };
}

const serverOf = (st: State, source: string, now: number) => { const s = st.server?.[source]; return s && s.resetAt > now ? s : null; };

function opensNow(st: State, now: number): Record<string, number[]> {
  return Object.fromEntries(Object.entries(st.opens).map(([p, o]) => [p, o.n.map((v) => fade(v, now - o.at))]));
}

function careFor(st: State, page: string, now: number, hour = new Date(now).getHours()): number {
  const opens = opensNow(st, now);
  const most = Math.max(0, ...Object.values(opens).map((v) => v.reduce((a, b) => a + b, 0)));
  return care(opens[page] ?? new Array(24).fill(0), hour, most);
}

/** You opened a page: what WISEP learns your day from. */
export async function opened(nav: string): Promise<void> {
  if (!nav) return;
  const page = canonical(nav);
  const st = await load(), now = Date.now();
  const o = st.opens[page] ?? { n: new Array(24).fill(0), at: now };
  o.n = o.n.map((v) => fade(v, now - o.at));
  o.n[new Date(now).getHours()] += 1;
  o.at = now;
  st.opens[page] = o;
  save();
}

const keyOf = (url: string) => { try { const u = new URL(url); u.searchParams.delete('mailto'); u.searchParams.sort(); return u.toString(); } catch { return url; } };

function respond(body: string, status = 200, note = ''): Response {
  return new Response(body, { status, headers: { 'Content-Type': 'application/json', ...(note ? { 'X-Wisep': note } : {}) } });
}

async function space(source: string) {
  const gap = SOURCES[source][1] * 1000, wait = (last[source] ?? 0) + gap - Date.now();
  if (wait > 0) await new Promise((r) => setTimeout(r, Math.min(wait, 5000)));
  last[source] = Date.now();
}

function withContact(url: string, source: string): string {
  if (source !== 'openalex') return url;
  try { const u = new URL(url); if (!u.searchParams.has('mailto')) u.searchParams.set('mailto', CONTACT); return u.toString(); } catch { return url; }
}

async function withKey(source: string, init?: RequestInit): Promise<{ init?: RequestInit; key: boolean }> {
  if (source !== 'openalex') return { init, key: false };
  const key = await getOpenAlexKey().catch(() => null);
  if (!key) return { init, key: false };
  return { init: { ...init, headers: { ...(init?.headers as Record<string, string> ?? {}), Authorization: `Bearer ${key}` } }, key: true };
}

/** Ask OpenAlex for a free key (only when the person asks): they get an email with a link; the key works once clicked. */
export async function requestKey(email: string): Promise<{ ok: boolean; key: boolean; message: string }> {
  email = email.trim();
  if (!email.includes('@') || email.includes(' ') || email.length > 200) return { ok: false, key: false, message: "That doesn't look like an email address." };
  try {
    const r = await fetchT('https://api.openalex.org/api-keys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
    const data: any = await r.json().catch(() => ({}));
    if (!r.ok) return { ok: false, key: false, message: String(data?.message ?? `OpenAlex said ${r.status}.`).slice(0, 300) };
    const key = String(data?.key ?? data?.api_key ?? '');
    if (key) await setOpenAlexKey(key);
    return { ok: true, key: !!key, message: `Check your email and click OpenAlex's link: the key works after that.${key ? '' : ' Then paste the key here.'}` };
  } catch {
    return { ok: false, key: false, message: "OpenAlex didn't answer. Try again later." };
  }
}

export async function saveKey(key: string): Promise<boolean> {
  key = key.trim();
  if (key.length < 8 || key.length > 200 || /\s/.test(key)) return false;
  await setOpenAlexKey(key);
  return true;
}
export const forgetKey = () => setOpenAlexKey(null);
export const hasKey = async () => !!(await getOpenAlexKey().catch(() => null));

/** A GET through WISEP (for POSTs and unmanaged hosts it is plain fetchT). `page` names what the answer is for. */
export async function wiseFetch(url: string, opts: { page?: string; force?: boolean; init?: RequestInit; ms?: number } = {}): Promise<Response> {
  const source = sourceOf(url);
  const method = (opts.init?.method ?? 'GET').toUpperCase();
  if (!source || method !== 'GET') return fetchT(url, opts.init, opts.ms);
  const st = await load(), now = Date.now(), key = keyOf(url), page = opts.page ?? '';
  const kept = st.answers[key];
  const kind = kindOf(source, key), cost = creditCost(source, key), srv = serverOf(st, source, now);
  let [used, budget, frac] = serverBudget(srv?.limit ?? 0, srv?.remaining ?? 0, srv ? (srv.resetAt - now) / 1000 : 0,
    st.calls[dayOf(now)]?.[source]?.credits ?? 0, SOURCES[source][0], dayFrac(now));
  if (cost === 0) { used = 0; budget = Math.max(budget, 1); }       // a free record by id: only spacing and the kept answer matter
  const resting = (st.paused[source] ?? 0) > now || (cost > 0 && !!srv && srv.remaining <= 0);
  const d = decide(kept ? (now - kept.fetched) / 3600000 : null, kind, kept?.changes ?? 0, kept?.watched ?? 0, careFor(st, page, now),
    used, budget, frac, !!opts.force, resting, st.priors?.[kind] ?? null);
  if (d.action === 'cache' && kept) { count(st, source, 'saved', now); kept.used = now; save(); return respond(kept.body, 200, `cache:${d.why}`); }
  if (d.action === 'none') { count(st, source, 'failed', now); save(); return respond('{}', 503, 'resting'); }
  await space(source);
  count(st, source, 'asked', now);
  if (cost) count(st, source, 'credits', now, cost);
  const keyed = await withKey(source, opts.init);
  let res: Response;
  try {
    res = await fetchT(withContact(url, source), keyed.init, opts.ms);
  } catch (e) {
    if (kept) { count(st, source, 'stale', now); save(); return respond(kept.body, 200, 'stale:offline'); }
    count(st, source, 'failed', now); save();
    throw e;
  }
  noteServer(st, source, res, now, keyed.key);
  if (res.status === 429 || res.status === 503) {
    const wait = Number(res.headers.get('Retry-After')) || 60, before = st.paused[source] ?? 0;
    // a 429 with Retry-After (OpenAlex: until its budget resets) is honoured in full; a busy 503 doubles up to an hour
    st.paused[source] = now + (res.status === 429 && Number(res.headers.get('Retry-After')) > 0 ? Math.min(wait, 86400)
      : Math.min(3600, Math.max(wait, before > now ? (before - now) / 500 : wait))) * 1000;
    if (kept) { count(st, source, 'stale', now); save(); return respond(kept.body, 200, 'stale:busy'); }
    save();
    return res;
  }
  if (res.status === 200) {
    const body = await res.text(), dg = digest(body);
    const watched = kept ? kept.watched + Math.max(0, (now - kept.fetched) / 3600000) : 0;
    st.answers[key] = { url: key, source, kind, body, digest: dg, fetched: now, checks: (kept?.checks ?? 0) + 1,
      changes: (kept?.changes ?? 0) + (kept && kept.digest !== dg ? 1 : 0), watched, used: now, page: page || kept?.page || '' };
    save();
    return respond(body, 200);
  }
  save();
  return res;
}

/** The evening top-up (wisep.top_up): budget left at the end of the day, spent on what you'll want fresh tomorrow. */
export async function topUp(): Promise<Record<string, number>> {
  const st = await load(), now = Date.now();
  tune(st, now);                                  // the same look is when the priors are retuned (daily)
  if (new Date(now).getHours() < TOP_UP_HOUR) return {};
  const tomorrow = (new Date(now).getHours() + 12) % 24;
  const ranked = Object.entries(st.answers).flatMap(([key, a]) => {
    const [defPrior, least] = KINDS[a.kind] ?? KINDS.entity, age = (now - a.fetched) / 3600000, prior = st.priors?.[a.kind] || defPrior;
    if (!SOURCES[a.source] || age < least || (st.paused[a.source] ?? 0) > now) return [];
    return [{ key, a, worth: pChanged(changeRate(a.changes, a.watched, prior), age + 10) * careFor(st, a.page, now, tomorrow) }];
  }).sort((x, y) => y.worth - x.worth);
  const spent: Record<string, number> = {};
  for (const { key, a, worth } of ranked) {
    const left = SOURCES[a.source][0] - (st.calls[dayOf(now)]?.[a.source]?.asked ?? 0);
    if (worth < TOP_UP_FLOOR || (spent[a.source] ?? 0) >= Math.floor(left * TOP_UP_SHARE)
      || Object.values(spent).reduce((x, y) => x + y, 0) >= TOP_UP_MAX) continue;
    const srv = serverOf(st, a.source, now), cost = creditCost(a.source, key);
    if (cost && srv && srv.remaining <= srv.limit * RESERVE * 2) continue;   // the network's budget is nearly spent
    await space(a.source);
    count(st, a.source, 'asked', now);
    count(st, a.source, 'topup', now);
    if (cost) count(st, a.source, 'credits', now, cost);
    try {
      const keyed = await withKey(a.source);
      const res = await fetchT(withContact(key, a.source), keyed.init);
      noteServer(st, a.source, res, now, keyed.key);
      if (res.status === 200) {
        const body = await res.text(), dg = digest(body);
        st.answers[key] = { ...a, body, digest: dg, fetched: now, checks: a.checks + 1, changes: a.changes + (a.digest !== dg ? 1 : 0),
          watched: a.watched + (now - a.fetched) / 3600000 };
        spent[a.source] = (spent[a.source] ?? 0) + 1;
      }
    } catch { /* offline: tomorrow */ }
  }
  save();
  return spent;
}

/** Retune each kind's prior from this phone's history, at most once a day (wisep.tune). */
function tune(st: State, now: number): void {
  if (st.tunedDay === dayOf(now)) return;
  const pooled: Record<string, [number, number, number]> = {};
  for (const a of Object.values(st.answers)) {
    if (a.checks < 3) continue;
    const p = (pooled[a.kind] ??= [0, 0, 0]);
    p[0] += a.changes; p[1] += a.watched; p[2] += 1;
  }
  st.priors = {};
  for (const k of Object.keys(KINDS)) {
    const v = tunedPrior(...(pooled[k] ?? [0, 0, 0]), k);
    if (v !== null) st.priors[k] = v;
  }
  st.tunedDay = dayOf(now);
  save();
}

function tallyRows(st: State) {
  return Object.entries(st.calls).flatMap(([day, by]) => Object.values(by).map((c) => ({ day, ...c })));
}

/** Whether WISEP decides alone now: Admin's mode, else provenBy on the last month's tallies (wisep.proven). */
export async function proven(): Promise<Proven & { mode: Mode; alone: boolean }> {
  const st = await load(), p = provenBy(tallyRows(st)), mode = st.mode ?? 'auto';
  return { ...p, mode, alone: mode === 'on' || (mode === 'auto' && p.proven) };
}

export async function setMode(mode: Mode): Promise<void> { const st = await load(); st.mode = mode; save(); }

/** Forget what WISEP learned about you (wisep.forget_learned): the pages you open and the tuned priors. */
export async function forgetLearned(): Promise<void> { const st = await load(); st.opens = {}; st.priors = {}; st.tunedDay = ''; save(); }

/** A module's own "is it time?" -- unless WISEP has taken over (then every half hour, and WISEP decides). */
export async function timerDue(ownDue: boolean, ageHours: number | null = null): Promise<boolean> {
  if (ownDue) return true;
  try { return (await proven()).alone && (ageHours === null || ageHours >= MODULE_GAP_HOURS); } catch { return false; }
}

/** GitHub keeps its own cache (lib/github.ts); its asks and what the cache saved are counted here for the admin view. */
export async function noteGitHub(field: 'asked' | 'saved'): Promise<void> {
  const st = await load(), d = dayOf(Date.now());
  const g = ((st.github ??= {})[d] ??= { asked: 0, saved: 0 });
  g[field]++;
  st.github = Object.fromEntries(Object.entries(st.github).sort(([a], [b]) => (a < b ? 1 : -1)).slice(0, 30));
  save();
}

/** What the admin view shows: today's calls per source, saved by the cache, budgets, what was learned. */
export async function stats(): Promise<{ today: Record<string, { asked: number; saved: number; stale: number; failed: number; topup: number; budget: number }>;
  asked: number; saved: number; pages: { page: string; opens: number }[]; answers: number; github: { asked: number; saved: number };
  priors: Record<string, number>; proven: Proven & { mode: Mode; alone: boolean }; key: boolean;
  server: Record<string, { limit: number; remaining: number; resetIn: number }> }> {
  const st = await load(), now = Date.now(), today = st.calls[dayOf(now)] ?? {};
  const out = Object.fromEntries(Object.entries(today).map(([s, c]) => [s, { ...c, budget: SOURCES[s]?.[0] ?? 0 }]));
  const pages = Object.entries(opensNow(st, now)).map(([page, v]) => ({ page, opens: Math.round(v.reduce((a, b) => a + b, 0) * 100) / 100 }))
    .sort((a, b) => b.opens - a.opens).slice(0, 8);
  return { today: out, asked: Object.values(today).reduce((a, c) => a + c.asked, 0), saved: Object.values(today).reduce((a, c) => a + c.saved, 0),
    pages, answers: Object.keys(st.answers).length, github: st.github?.[dayOf(now)] ?? { asked: 0, saved: 0 }, priors: st.priors ?? {},
    proven: await proven(), key: await hasKey(),
    server: Object.fromEntries(Object.keys(SOURCES).flatMap((s) => { const v = serverOf(st, s, now); return v ? [[s, { limit: v.limit, remaining: v.remaining, resetIn: Math.trunc((v.resetAt - now) / 1000) }]] : []; })) };
}
