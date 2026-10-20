// Who cited you (You → 📑 Cited by): the papers citing your work, the people who cite you most, and where you're
// read -- a port of the desktop's citedby.py (tests/test_citedby.py checks both agree). Once a day: your author
// record, your papers' citation counts, and the newest papers citing the ones whose count went up, in one request
// for up to 50 papers. If OpenAlex is busy, what was found before stays. Kept on this phone only.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { wiseFetch } from './wisep';

const KEY = 'mygeeky.citedby';
const OPENALEX = 'https://api.openalex.org';
const REFRESH_HOURS = 20;
const KEEP = 200;
export const PER_CALL = 50;
const NEW_DAYS = 14;
const MONTH_DAYS = 30;
const TOP = 8;
const WORK = /^W\d{2,12}$/, AUTHOR = /^A\d{2,12}$/;

export type Author = { name: string; id: string; institution: string; country: string };
export type Citing = { id: string; title: string; date: string; url: string; authors: Author[]; cites: string[]; self: boolean; seen: string };
export type CitedState = { author?: string; updated_at?: string; totals?: ReturnType<typeof parseAuthor>;
  counts?: Record<string, number>; papers?: Record<string, { title: string; cited: number }>; citing?: Citing[] };

const idOf = (u: unknown) => String(u ?? '').split('/').pop() ?? '';
const int = (v: unknown) => Math.trunc(Number(v) || 0);
const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
function days(a: string, b: string): number | null {
  const x = Date.parse(`${String(a).slice(0, 10)}T00:00:00Z`), y = Date.parse(`${String(b).slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(x) || Number.isNaN(y) || !/^\d{4}-\d{2}-\d{2}/.test(a) ? null : Math.round((y - x) / 86400000);
}

export function parseAuthor(data: any) {
  const d = data && typeof data === 'object' ? data : {};
  const s = d.summary_stats && typeof d.summary_stats === 'object' ? d.summary_stats : {};
  return { name: String(d.display_name ?? '').slice(0, 120), cited: int(d.cited_by_count), works: int(d.works_count), h: int(s.h_index), i10: int(s.i10_index) };
}

export function parseCiting(data: any, mine: Set<string>, me: string, seenAt: string): Citing[] {
  const out: Citing[] = [];
  for (const w of Array.isArray(data?.results) ? data.results : []) {
    if (!w || typeof w !== 'object') continue;
    const wid = idOf(w.id), title = String(w.title ?? '').split(/\s+/).filter(Boolean).join(' ').slice(0, 220);
    if (!WORK.test(wid) || !title) continue;
    const authors: Author[] = [];
    for (const a of (Array.isArray(w.authorships) ? w.authorships : []).slice(0, 12)) {
      if (!a || typeof a !== 'object') continue;
      const au = a.author && typeof a.author === 'object' ? a.author : {};
      const insts = (Array.isArray(a.institutions) ? a.institutions : []).filter((i: any) => i && typeof i === 'object');
      const inst = insts[0] ?? {};
      const name = String(au.display_name ?? '').trim().slice(0, 80);
      if (name) authors.push({ name, id: AUTHOR.test(idOf(au.id)) ? idOf(au.id) : '', institution: String(inst.display_name ?? '').slice(0, 100),
        country: String(inst.country_code ?? '').slice(0, 2).toUpperCase() });
    }
    const refs = new Set((Array.isArray(w.referenced_works) ? w.referenced_works : []).map(idOf));
    out.push({ id: wid, title, date: String(w.publication_date ?? '').slice(0, 10), url: String(w.doi ?? `https://openalex.org/${wid}`).slice(0, 200),
      authors, cites: [...mine].filter((m) => refs.has(m)).sort(cmp), self: !!me && authors.some((a) => a.id === me), seen: seenAt });
  }
  return out;
}

export function merge(old: Citing[], fresh: Citing[]): Citing[] {
  const by = new Map(old.filter((c) => c && c.id).map((c) => [c.id, c]));
  for (let c of fresh) {
    const b = by.get(c.id);
    if (b) c = { ...c, seen: b.seen ?? c.seen, cites: [...new Set([...(b.cites ?? []), ...c.cites])].sort(cmp) };
    by.set(c.id, c);
  }
  return [...by.values()].sort((a, b) => cmp(b.date ?? '', a.date ?? '') || cmp(b.id, a.id)).slice(0, KEEP);
}

export function toAsk(counts: Record<string, number>, before: Record<string, number> | null): string[] {
  const rose = Object.keys(counts).filter((w) => (before === null ? counts[w] > 0 : counts[w] > int(before[w])));
  rose.sort((a, b) => counts[b] - counts[a] || cmp(a, b));
  return rose.slice(0, 2 * PER_CALL);
}

function rank(m: Map<string, number>): [string, number][] {
  return [...m].sort((a, b) => b[1] - a[1] || cmp(a[0], b[0])).slice(0, TOP);
}
const bump = (m: Map<string, number>, k: string) => m.set(k, (m.get(k) ?? 0) + 1);

/** Everything the page shows, from what's kept (no network). */
export function summary(state: CitedState, today: string) {
  const citing = (state.citing ?? []).filter((c) => c && typeof c === 'object' && !c.self);
  const papers = state.papers ?? {};
  const within = (d: string | undefined, n: number) => { const x = days(String(d ?? ''), today); return x !== null && x <= n; };
  const month = citing.filter((c) => within(c.date, MONTH_DAYS));
  const fresh = citing.filter((c) => within(c.seen, NEW_DAYS));
  const freshIds = new Set(fresh.map((c) => c.id));
  const me = state.author ?? '';
  const people = new Map<string, number>(), who = new Map<string, Author>();
  for (const c of citing) {
    const uniq = new Map<string, Author>();
    for (const x of c.authors ?? []) uniq.set(x.id || x.name, x);
    for (const a of uniq.values()) {
      if (a.id && a.id === me) continue;
      const k = a.id || a.name;
      bump(people, k);
      if (!who.has(k)) who.set(k, a);
    }
  }
  const countries = new Map<string, number>(), places = new Map<string, number>(), most = new Map<string, number>();
  for (const c of citing) {
    for (const k of new Set((c.authors ?? []).map((a) => a.country).filter(Boolean))) bump(countries, k);
    for (const k of new Set((c.authors ?? []).map((a) => a.institution).filter(Boolean))) bump(places, k);
    for (const w of c.cites ?? []) bump(most, w);
  }
  return {
    totals: state.totals ?? {}, updated_at: state.updated_at ?? '',
    found: citing.length, this_month: month.length, new: fresh.length,
    citing: citing.slice(0, 40).map((c) => ({ ...c, new: freshIds.has(c.id), cites_titles: (c.cites ?? []).map((w) => papers[w]?.title ?? '') })),
    people: rank(people).map(([k, n]) => ({ ...who.get(k)!, count: n })),
    countries: rank(countries).map(([k, n]) => ({ code: k, count: n })),
    places: rank(places).slice(0, 5).map(([k, n]) => ({ name: k, count: n })),
    papers: rank(most).slice(0, 5).map(([w, n]) => ({ id: w, title: papers[w]?.title ?? '', count: n, cited: int(papers[w]?.cited) })),
  };
}

// --------------------------------------------------------------------------- once a day
export async function loadCitedBy(): Promise<CitedState> {
  try { const d = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '{}'); return d && typeof d === 'object' ? d : {}; } catch { return {}; }
}

const due = (s: CitedState, author: string) =>
  s.author !== author || !s.updated_at || Date.now() - Date.parse(s.updated_at) >= REFRESH_HOURS * 3600000;
const busy = (status: number) => status === 429 || status >= 500;

/** Read what's new (when due) and keep it. `author`: your OpenAlex author id (A…). */
export async function refreshCitedBy(author: string, force = false): Promise<{ ok: boolean; busy?: boolean; state: CitedState }> {
  const state = await loadCitedBy();
  if (!AUTHOR.test(author)) return { ok: false, state };
  if (!force && !due(state, author)) return { ok: true, state };
  const when = new Date().toISOString().slice(0, 19) + '+00:00';
  const freshAuthor = state.author !== author;
  try {
    let r = await wiseFetch(`${OPENALEX}/authors/${author}?select=id,display_name,cited_by_count,works_count,summary_stats`, { page: 'you:cited' });
    if (busy(r.status) || !r.ok) return { ok: false, busy: true, state };
    const totals = parseAuthor(await r.json());
    r = await wiseFetch(`${OPENALEX}/works?filter=author.id:${author}&per-page=200&select=id,title,cited_by_count`, { page: 'you:cited' });
    if (busy(r.status) || !r.ok) return { ok: false, busy: true, state };
    const papers: NonNullable<CitedState['papers']> = {};
    for (const w of (await r.json())?.results ?? []) {
      const wid = idOf(w?.id);
      if (WORK.test(wid) && w.title) papers[wid] = { title: String(w.title).split(/\s+/).join(' ').slice(0, 200), cited: int(w.cited_by_count) };
    }
    const counts = Object.fromEntries(Object.entries(papers).map(([w, p]) => [w, p.cited]));
    const ask = toAsk(counts, freshAuthor ? null : state.counts ?? null);
    let found: Citing[] = [];
    for (let i = 0; i < ask.length; i += PER_CALL) {
      const chunk = ask.slice(i, i + PER_CALL);
      r = await wiseFetch(`${OPENALEX}/works?filter=cites:${chunk.join('|')}&sort=publication_date:desc&per-page=50`
        + '&select=id,title,publication_date,doi,authorships,referenced_works', { page: 'you:cited' });
      if (busy(r.status) || !r.ok) break;
      // the first read only sets the starting point: what's there already isn't "new" (no flood of NEW)
      found = found.concat(parseCiting(await r.json(), new Set(Object.keys(papers)), author, freshAuthor ? '' : when));
    }
    const next: CitedState = { author, updated_at: when, totals, counts, papers, citing: merge(freshAuthor ? [] : state.citing ?? [], found) };
    await AsyncStorage.setItem(KEY, JSON.stringify(next));
    return { ok: true, state: next };
  } catch {
    return { ok: false, busy: true, state };
  }
}

/** Your OpenAlex author id: the one you confirmed ("Is this you?"), or the one OpenAlex keeps for your ORCID. */
export async function authorFor(orcid: string, openalex: string): Promise<string> {
  if (AUTHOR.test(openalex)) return openalex;
  if (!/^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(orcid)) return '';
  try {
    const r = await wiseFetch(`${OPENALEX}/authors/orcid:${orcid}?select=id`, { page: 'you:cited' });
    if (!r.ok) return '';
    const id = idOf((await r.json())?.id);
    return AUTHOR.test(id) ? id : '';
  } catch { return ''; }
}
