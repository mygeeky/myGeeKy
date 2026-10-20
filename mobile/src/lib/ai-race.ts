// The AI race (News → 🏁 AI race): who leads, how far open models trail, what's new, and what each model is best at
// -- a port of the desktop's airace.py (tests/test_airace.py checks both give the same answers). The data is Epoch
// AI's open Benchmarking Hub (CC BY 4.0, credited on the page), turned into data/ai_race.json once a day by a GitHub
// Action; the app reads the newest copy from GitHub at most once a day and falls back to the one it shipped with.
import bundled from '../data/ai_race.json';
import { fetchT } from './net';
import { isStale, readCache, writeCache } from './storage';

export const REMOTE_URL = 'https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/ai_race.json';
export const SOURCE = 'Epoch AI, Benchmarking Hub (CC BY 4.0)';
export const GROUPS = ['Reasoning', 'Coding', 'Math', 'Science', 'Agents', 'Knowledge', 'Writing', 'Vision', 'Security'];
const CHECK_EVERY_HOURS = 24;
const FRESH_DAYS = 14;
const SINCE = '2024-01';
const TOP_PER_GROUP = 8;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export type GroupScore = { score: number; pct: number };
export type Model = { model: string; eci: number; date: string; org: string; open: boolean; best: string; groups: Record<string, GroupScore> };
export type Race = { version: string; source: string; models: Model[]; groups: Record<string, { benchmarks: string[]; ranked: number; top: { model: string; score: number; n: number }[] }> };

const num = (x: unknown): number | null => {
  if (x === null || x === undefined || x === '' || typeof x === 'boolean') return null;
  const v = Number(x);
  return Number.isFinite(v) ? v : null;
};
const clip = (v: number) => Math.max(0, Math.min(1, v));
const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
const str = (x: unknown, n: number) => String(x ?? '').trim().slice(0, n);

function cleanModel(m: any): Model | null {
  if (!m || typeof m !== 'object' || Array.isArray(m)) return null;
  const name = str(m.model, 80), e = num(m.eci), d = String(m.date ?? '');
  if (!name || e === null || !DATE.test(d)) return null;
  const groups: Record<string, GroupScore> = {};
  if (m.groups && typeof m.groups === 'object' && !Array.isArray(m.groups)) {
    for (const [g, v] of Object.entries(m.groups as Record<string, any>)) {
      const s = v && typeof v === 'object' ? num(v.score) : null, p = v && typeof v === 'object' ? num(v.pct) : null;
      if (GROUPS.includes(g) && s !== null && p !== null) groups[g] = { score: clip(s), pct: clip(p) };
    }
  }
  const best = String(m.best ?? '');
  return { model: name, eci: e, date: d, org: str(m.org, 80), open: m.open === true, best: best in groups ? best : '', groups };
}

export function clean(data: any): Race {
  data = data && typeof data === 'object' && !Array.isArray(data) ? data : {};
  const models = (Array.isArray(data.models) ? data.models.slice(0, 2000) : []).map(cleanModel).filter((m: Model | null): m is Model => !!m)
    .sort((a: Model, b: Model) => cmp(a.date, b.date) || cmp(a.model, b.model));
  const raw = data.groups && typeof data.groups === 'object' && !Array.isArray(data.groups) ? data.groups : {};
  const groups: Race['groups'] = {};
  for (const g of GROUPS) {
    const v = raw[g] && typeof raw[g] === 'object' && !Array.isArray(raw[g]) ? raw[g] : {};
    const top = (Array.isArray(v.top) ? v.top.slice(0, TOP_PER_GROUP) : [])
      .filter((t: any) => t && typeof t === 'object' && num(t.score) !== null && str(t.model, 80))
      .map((t: any) => ({ model: str(t.model, 80), score: clip(num(t.score)!), n: Math.trunc(num(t.n) ?? 0) }));
    groups[g] = { benchmarks: Array.isArray(v.benchmarks) ? v.benchmarks.slice(0, 30).filter((b: unknown) => typeof b === 'string').map((b: string) => b.slice(0, 60)) : [],
      ranked: Math.trunc(num(v.ranked) ?? 0), top };
  }
  const version = String(data.version ?? '');
  return { version: DATE.test(version) ? version : '', source: SOURCE, models, groups };
}

/** The newest race data: the copy in the app, or a newer one fetched from GitHub (at most once a day). */
export async function loadRace(force = false): Promise<Race> {
  const shipped = clean(bundled);
  const cached = await readCache<Race>('airace');
  let best = cached?.data ? clean(cached.data) : shipped;
  if (!best.models.length || best.version < shipped.version) best = shipped;
  if (force || isStale(cached?.at, CHECK_EVERY_HOURS)) {
    try {
      const r = await fetchT(REMOTE_URL);
      if (r.ok) {
        const fresh = clean(await r.json());
        await writeCache('airace', fresh);
        if (fresh.models.length && fresh.version >= best.version) best = fresh;
      }
    } catch { /* offline: what we have */ }
  }
  return best;
}

// --------------------------------------------------------------------------- what the page shows
export const orgOf = (m: { org?: string }) => (m.org ?? '').split(',')[0].trim() || 'Not given';
const days = (a: string, b: string) => Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86400000);
const monthEnd = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).toISOString().slice(0, 10);   // m: 1..12
const round1 = (v: number) => Math.round(v * 10) / 10;
const round3 = (v: number) => Math.round(v * 1000) / 1000;

export function monthsBetween(first: string, last: string): string[] {
  let y = Number(first.slice(0, 4)), mo = Number(first.slice(5, 7));
  const out: string[] = [];
  for (;;) {
    const end = monthEnd(y, mo);
    out.push(end);
    if (end >= last) return out;
    if (mo === 12) { y += 1; mo = 1; } else mo += 1;
  }
}

function bestUntil(models: Model[], until: string, open?: boolean): Model | null {
  let best: Model | null = null;
  for (const m of models) if (m.date <= until && (open === undefined || m.open === open) && (!best || m.eci > best.eci)) best = m;
  return best;
}

/** Each lab's best model up to `until`, the leaders first. */
export function race(data: Race, until: string, lanes = 6) {
  const best: Record<string, Model> = {};
  for (const m of data.models) {
    const o = orgOf(m);
    if (m.date <= until && (!best[o] || m.eci > best[o].eci)) best[o] = m;
  }
  return Object.entries(best).sort((a, b) => b[1].eci - a[1].eci || cmp(a[0], b[0])).slice(0, lanes)
    .map(([org, m]) => ({ org, model: m.model, eci: m.eci, open: m.open }));
}

/** The models best for a mix of skills: their average over those skills, among models with all of them. */
export function pick(data: Race, skills: string[], n = 5) {
  const sel = skills.filter((s) => GROUPS.includes(s));
  if (!sel.length) return [];
  return data.models.filter((m) => sel.every((s) => m.groups[s]))
    .map((m) => ({ model: m.model, open: m.open, score: round3(sel.reduce((t, s) => t + m.groups[s].score, 0) / sel.length) }))
    .sort((a, b) => b.score - a.score || cmp(a.model, b.model)).slice(0, n);
}

export type Stats = ReturnType<typeof stats>;

export function stats(data: Race) {
  const models = data.models;
  if (!models.length) return { empty: true as const };
  const byEci = [...models].sort((a, b) => b.eci - a.eci || cmp(a.model, b.model));
  const leader = byEci[0], bestOpen = byEci.find((m) => m.open) ?? null;
  const newest = models[models.length - 1].date;
  const months = monthsBetween(models.reduce((a, m) => (m.date < a ? m.date : a), models[0].date), newest);
  const closed = months.map((e) => bestUntil(models, e, false)), opened = months.map((e) => bestUntil(models, e, true));
  const behind = opened.map((o, i) => {
    if (!o) return null;
    const j = closed.findIndex((c) => c && c.eci >= o.eci);
    return j < 0 || j > i ? 0 : Math.floor(days(months[j], months[i]) / 30.44 + 0.5);
  });
  const ago = bestUntil(models, months[Math.max(0, months.length - 13)]);
  const orgs: Record<string, number> = {};
  for (const m of models) orgs[orgOf(m)] = Math.max(orgs[orgOf(m)] ?? 0, m.eci);
  const runner = Object.entries(orgs).filter(([o]) => o !== orgOf(leader)).sort((a, b) => b[1] - a[1] || cmp(a[0], b[0]));
  const rank = new Map(byEci.map((m, i) => [m.model, i + 1]));
  const recent = [...models].sort((a, b) => cmp(b.date, a.date) || cmp(b.model, a.model)).slice(0, 6).map((m) => ({
    model: m.model, date: m.date, org: orgOf(m), open: m.open, best: m.best, rank: rank.get(m.model)!, fresh: days(m.date, newest) <= FRESH_DAYS }));
  const start = Math.max(0, months.findIndex((e) => e.slice(0, 7) >= SINCE));
  const counts: Record<string, number> = {};
  for (const m of models) if (m.best) counts[m.best] = (counts[m.best] ?? 0) + 1;
  const bestAt = [...GROUPS].sort((a, b) => (counts[b] ?? 0) - (counts[a] ?? 0) || GROUPS.indexOf(a) - GROUPS.indexOf(b)).map((g) => ({
    group: g,
    models: models.filter((m) => m.best === g).sort((a, b) => b.eci - a.eci || cmp(a.model, b.model)).map((m) => ({ model: m.model, open: m.open })),
    top: (data.groups[g]?.top ?? []).slice(0, 5).map((t) => ({ ...t, open: models.find((m) => m.model === t.model)?.open ?? false })),
  }));
  const prints = byEci.filter((m) => Object.keys(m.groups).length >= 3).slice(0, 6).map((m) => ({ model: m.model, eci: m.eci, best: m.best, groups: m.groups }));
  return {
    empty: false as const, version: data.version, count: models.length, open_count: models.filter((m) => m.open).length,
    leader: { model: leader.model, org: orgOf(leader), eci: leader.eci },
    runner_up: runner.length ? { org: runner[0][0], eci: runner[0][1] } : null,
    best_open: bestOpen ? { model: bestOpen.model, org: orgOf(bestOpen), eci: bestOpen.eci } : null,
    rise: ago ? round1(leader.eci - ago.eci) : 0,
    behind_now: behind[behind.length - 1] ?? 0,
    months: months.slice(start), closed: closed.slice(start).map((c) => c?.eci ?? null), open: opened.slice(start).map((o) => o?.eci ?? null),
    behind: behind.slice(start), recent, best_at: bestAt, prints, newest,
  };
}
