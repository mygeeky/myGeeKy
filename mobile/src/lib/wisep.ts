// WISEP -- Wisely, a Systematic Statistically adapted system for API calling: a port of the desktop's wisep.py.
// Every call to an open database (OpenAlex first) goes through wiseFetch: the kept answer when it is good enough, a
// fresh one when it is worth it -- the chance it changed (its own change history) x how much you care (what you open,
// and when), against a bar that rises as the day's budget runs ahead of the day. A daily budget per source, spaced
// calls, backing off on 429/503, OpenAlex's polite pool, and the kept answer when a source is down. The rules are the
// desktop's (tests/test_wisep.py checks both decide the same). Nothing leaves the phone but the requests themselves.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fetchT } from './net';

export const CONTACT = 'support@mygeeky.org';
const KEY = 'mygeeky.wisep';
const MAX_ANSWERS = 300;              // the phone keeps fewer than the computer
const HALF_LIFE_DAYS = 14;
const FORCE_ALLOWANCE = 1.2;
const TOP_UP_HOUR = 20, TOP_UP_SHARE = 0.5, TOP_UP_MAX = 15, TOP_UP_FLOOR = 0.15;

export const SOURCES: Record<string, [number, number, string[]]> = {
  openalex: [1500, 0.12, ['api.openalex.org']], crossref: [500, 0.2, ['api.crossref.org']], arxiv: [300, 3.1, ['export.arxiv.org']],
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

/** The desktop's wisep.decide. `bar` null where the desktop's is infinite (JSON has no Infinity). */
export function decide(ageHours: number | null, kind: string, changes: number, watchedHours: number, careNow: number, used: number,
  budget: number, dayFrac: number, forced = false, paused = false): Decision {
  const [prior, least, most] = KINDS[kind] ?? KINDS.entity;
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
  'grow:wins': 'grow:wins', 'grow:paths': 'grow:paths', 'grow:data:new': 'grow:data:new', 'you:month': 'you:model', 'model:month': 'you:model' };
export const canonical = (page: string) => (page.startsWith('admin:') || page.startsWith('you:admin') ? 'you:admin' : PAGES[page] ?? page);

// --------------------------------------------------------------------------- the store (one JSON value in AsyncStorage)
type Answer = { url: string; source: string; kind: string; body: string; digest: string; fetched: number; checks: number; changes: number;
  watched: number; used: number; page: string };
type State = { answers: Record<string, Answer>; calls: Record<string, Record<string, { asked: number; saved: number; stale: number; failed: number; topup: number }>>;
  opens: Record<string, { n: number[]; at: number }>; paused: Record<string, number> };
let mem: State | null = null;
const last: Record<string, number> = {};

async function load(): Promise<State> {
  if (mem) return mem;
  try {
    const raw = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '{}');
    mem = { answers: raw.answers ?? {}, calls: raw.calls ?? {}, opens: raw.opens ?? {}, paused: raw.paused ?? {} };
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
function count(st: State, source: string, field: 'asked' | 'saved' | 'stale' | 'failed' | 'topup', now: number) {
  const d = (st.calls[dayOf(now)] ??= {});
  const c = (d[source] ??= { asked: 0, saved: 0, stale: 0, failed: 0, topup: 0 });
  c[field]++;
}

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

/** A GET through WISEP (for POSTs and unmanaged hosts it is plain fetchT). `page` names what the answer is for. */
export async function wiseFetch(url: string, opts: { page?: string; force?: boolean; init?: RequestInit; ms?: number } = {}): Promise<Response> {
  const source = sourceOf(url);
  const method = (opts.init?.method ?? 'GET').toUpperCase();
  if (!source || method !== 'GET') return fetchT(url, opts.init, opts.ms);
  const st = await load(), now = Date.now(), key = keyOf(url), page = opts.page ?? '';
  const kept = st.answers[key];
  const kind = kindOf(source, key);
  const used = st.calls[dayOf(now)]?.[source]?.asked ?? 0;
  const d = decide(kept ? (now - kept.fetched) / 3600000 : null, kind, kept?.changes ?? 0, kept?.watched ?? 0, careFor(st, page, now),
    used, SOURCES[source][0], dayFrac(now), !!opts.force, (st.paused[source] ?? 0) > now);
  if (d.action === 'cache' && kept) { count(st, source, 'saved', now); kept.used = now; save(); return respond(kept.body, 200, `cache:${d.why}`); }
  if (d.action === 'none') { count(st, source, 'failed', now); save(); return respond('{}', 503, 'resting'); }
  await space(source);
  count(st, source, 'asked', now);
  let res: Response;
  try {
    res = await fetchT(withContact(url, source), opts.init, opts.ms);
  } catch (e) {
    if (kept) { count(st, source, 'stale', now); save(); return respond(kept.body, 200, 'stale:offline'); }
    count(st, source, 'failed', now); save();
    throw e;
  }
  if (res.status === 429 || res.status === 503) {
    const wait = Number(res.headers.get('Retry-After')) || 60, before = st.paused[source] ?? 0;
    st.paused[source] = now + Math.min(3600, Math.max(wait, before > now ? (before - now) / 500 : wait)) * 1000;
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
  if (new Date(now).getHours() < TOP_UP_HOUR) return {};
  const tomorrow = (new Date(now).getHours() + 12) % 24;
  const ranked = Object.entries(st.answers).flatMap(([key, a]) => {
    const [prior, least] = KINDS[a.kind] ?? KINDS.entity, age = (now - a.fetched) / 3600000;
    if (!SOURCES[a.source] || age < least || (st.paused[a.source] ?? 0) > now) return [];
    return [{ key, a, worth: pChanged(changeRate(a.changes, a.watched, prior), age + 10) * careFor(st, a.page, now, tomorrow) }];
  }).sort((x, y) => y.worth - x.worth);
  const spent: Record<string, number> = {};
  for (const { key, a, worth } of ranked) {
    const left = SOURCES[a.source][0] - (st.calls[dayOf(now)]?.[a.source]?.asked ?? 0);
    if (worth < TOP_UP_FLOOR || (spent[a.source] ?? 0) >= Math.floor(left * TOP_UP_SHARE)
      || Object.values(spent).reduce((x, y) => x + y, 0) >= TOP_UP_MAX) continue;
    await space(a.source);
    count(st, a.source, 'asked', now);
    count(st, a.source, 'topup', now);
    try {
      const res = await fetchT(withContact(key, a.source));
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

/** What the admin view shows: today's calls per source, saved by the cache, budgets, what was learned. */
export async function stats(): Promise<{ today: Record<string, { asked: number; saved: number; stale: number; failed: number; topup: number; budget: number }>;
  asked: number; saved: number; pages: { page: string; opens: number }[]; answers: number }> {
  const st = await load(), now = Date.now(), today = st.calls[dayOf(now)] ?? {};
  const out = Object.fromEntries(Object.entries(today).map(([s, c]) => [s, { ...c, budget: SOURCES[s]?.[0] ?? 0 }]));
  const pages = Object.entries(opensNow(st, now)).map(([page, v]) => ({ page, opens: Math.round(v.reduce((a, b) => a + b, 0) * 100) / 100 }))
    .sort((a, b) => b.opens - a.opens).slice(0, 8);
  return { today: out, asked: Object.values(today).reduce((a, c) => a + c.asked, 0), saved: Object.values(today).reduce((a, c) => a + c.saved, 0),
    pages, answers: Object.keys(st.answers).length };
}
