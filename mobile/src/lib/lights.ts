// Circle → Researchers → 🌟 Leading lights: living people who lead a field, a few at a time, picked by your Model --
// a port of the desktop's lights.py. The list (data/lights.json, identical on both) is cleaned here like any text from
// the internet; a new set every EVERY_DAYS days, round the whole fitting list before anyone comes back (the day
// decides, nothing is kept); their latest papers from ONE OpenAlex search (1 credit), and a tap's report from their
// record by id (free) and their five most cited papers (1 credit), through WISEP. tests/test_lights.py checks both agree.
import bundled from '../data/lights.json';
import { wiseFetch } from './wisep';

const OPENALEX = 'https://api.openalex.org';
export const PER_SET = 4, EVERY_DAYS = 3, YEARS = 10, MAX_PEOPLE = 2000;
export const BADGES: Record<string, [string, string]> = { nobel: ['🏅', 'Nobel Prize'], prize: ['🏆', 'Prize'],
  cited: ['📈', 'Most cited'], tool: ['🛠', 'Famous tool'] };
const AID = /^A\d{4,}$/, ORCID = /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/;
const SCHOLAR = /^https:\/\/scholar\.google\.com\/citations\?user=[\w-]{6,20}$/, GITHUB = /^[A-Za-z\d](?:[A-Za-z\d-]{0,38})$/;
const SOURCE = ['https://www.wikidata.org/wiki/Q', 'https://openalex.org/', 'https://www.nobelprize.org/', 'https://amturing.acm.org/'];

export type Light = { id: string; name: string; badge: string; why: string; source: string; field: string; topics: string[];
  institution: string; orcid: string; scholar: string; github: string; cited: number; h: number };
export type Paper = { title: string; url: string; date: string; venue: string };
export type Report = { works: number; cited: number; h: number; i10: number; years: [number, number, number][];
  topics: [string, boolean][]; institution: string; top: (Paper & { year: number; cited: number })[] };

const text = (v: unknown, n: number) => String(v ?? '').split(/\s+/).filter(Boolean).join(' ').slice(0, n);
const int = (v: unknown) => { const x = Math.trunc(Number(v)); return Number.isFinite(x) ? Math.max(0, x) : 0; };

/** lights.clean_person: one person from the list, or null -- only what each field may hold. */
export function cleanPerson(raw: any): Light | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const id = text(raw.id, 20), name = text(raw.name, 120), badge = text(raw.badge, 10);
  if (!AID.test(id) || !name || !(badge in BADGES)) return null;
  const source = text(raw.source, 300), orcid = text(raw.orcid, 19), scholar = text(raw.scholar, 80), github = text(raw.github, 39);
  const topics = Array.isArray(raw.topics) ? raw.topics : [];
  return { id, name, badge, why: text(raw.why, 160), source: SOURCE.some((s) => source.startsWith(s)) ? source : '',
    field: text(raw.field, 60), topics: topics.slice(0, 6).map((x: unknown) => text(x, 80)).filter(Boolean),
    institution: text(raw.institution, 160), orcid: ORCID.test(orcid) ? orcid : '', scholar: SCHOLAR.test(scholar) ? scholar : '',
    github: GITHUB.test(github) ? github : '', cited: int(raw.cited), h: int(raw.h) };
}

export function clean(data: any): { version: string; people: Light[] } {
  const d = data && typeof data === 'object' ? data : {};
  const rows: any[] = Array.isArray(d.people) ? d.people : [];
  const seen = new Set<string>(), people: Light[] = [];
  for (const p of rows.slice(0, MAX_PEOPLE).map(cleanPerson)) if (p && !seen.has(p.id)) { seen.add(p.id); people.push(p); }
  const version = text(d.version, 10);
  return { version: /^\d{4}-\d{2}-\d{2}$/.test(version) ? version : '', people };
}

export const load = () => clean(bundled);

export function links(p: Light): [string, string][] {
  const out: [string, string][] = p.scholar ? [['Google Scholar', p.scholar]] : [];
  if (p.orcid) out.push(['ORCID', `https://orcid.org/${p.orcid}`]);
  out.push(['OpenAlex', `https://openalex.org/${p.id}`]);
  if (p.github) out.push(['GitHub', `https://github.com/${p.github}`]);
  return out;
}

// ---- who you see
export function fit(p: Light, weights: Record<string, number>): number {
  const t = [...p.topics, p.field].join(' ').toLowerCase();
  let s = 0;
  for (const [term, w] of Object.entries(weights)) if (term && t.includes(term.toLowerCase())) s += w;
  return Math.round(s * 1e4) / 1e4;
}

const ordinal = (iso: string) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 86400000 + 719163;
const fromOrdinal = (n: number) => new Date((n - 719163) * 86400000).toISOString().slice(0, 10);
export const period = (today: string, every = EVERY_DAYS) => Math.floor(ordinal(today) / every);
export const nextChange = (today: string, every = EVERY_DAYS) => fromOrdinal((period(today, every) + 1) * every);

/** lights.pick: who fits your Model best, n at a time, a new set every `every` days, round the whole list. */
export function pick(people: Light[], weights: Record<string, number>, today: string, n = PER_SET, every = EVERY_DAYS): (Light & { fit: number })[] {
  const scored = people.map((p) => [fit(p, weights), p] as [number, Light]);
  const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
  const pool = scored.filter((x) => x[0] > 0).sort((a, b) => b[0] - a[0] || cmp(a[1].id, b[1].id));
  if (pool.length < n) {
    const famous = (p: Light) => (p.badge === 'nobel' || p.badge === 'prize' ? 0 : 1);
    const rest = scored.filter((x) => x[0] <= 0).sort((a, b) => famous(a[1]) - famous(b[1]) || b[1].cited - a[1].cited || cmp(a[1].id, b[1].id));
    pool.push(...rest.slice(0, Math.max(n, 12) - pool.length));
  }
  if (!pool.length) return [];
  const start = (period(today, every) * n) % pool.length;
  return Array.from({ length: Math.min(n, pool.length) }, (_, i) => pool[(start + i) % pool.length]).map(([f, p]) => ({ ...p, fit: f }));
}

// ---- their latest papers
export function since(today: string): string {
  return `${+today.slice(0, 4) - 1}-${today.slice(5, 7)}-01`;
}

export const recentUrl = (ids: string[], today: string) => `${OPENALEX}/works?filter=author.id:${[...ids].sort().join('|')},`
  + `from_publication_date:${since(today)}&sort=publication_date:desc&per-page=50&select=id,doi,title,publication_date,primary_location,authorships`;

function work(w: any): Paper {
  const doi = String(w.doi ?? '');
  const src = (w.primary_location ?? {}).source ?? {};
  return { title: text(w.title, 300), url: doi.startsWith('https://doi.org/') ? doi : 'https://openalex.org/' + String(w.id ?? '').split('/').pop(),
    date: text(w.publication_date, 10), venue: text(src.display_name, 120) };
}

export function parseRecent(data: any, ids: string[], perPerson = 2): Record<string, Paper[]> {
  const out: Record<string, Paper[]> = Object.fromEntries(ids.map((i) => [i, []]));
  const rows: any[] = data && Array.isArray(data.results) ? data.results : [];
  for (const w of rows) {
    if (!w || typeof w !== 'object' || !w.title) continue;
    const by = new Set((w.authorships ?? []).filter((a: any) => a && typeof a === 'object').map((a: any) => String(a.author?.id ?? '').split('/').pop()));
    for (const aid of Object.keys(out)) {
      if (by.has(aid) && out[aid].length < perPerson && out[aid].every((x) => x.title !== text(w.title, 300))) out[aid].push(work(w));
    }
  }
  return out;
}

// ---- the report
export const authorUrl = (aid: string) => `${OPENALEX}/authors/${aid}`;
export const topUrl = (aid: string) => `${OPENALEX}/works?filter=author.id:${aid}&sort=cited_by_count:desc&per-page=5`
  + '&select=id,doi,title,publication_year,cited_by_count,primary_location';

export function report(author: any, top: any, weights: Record<string, number>, today: string): Report {
  const a = author && typeof author === 'object' ? author : {};
  const stats = a.summary_stats && typeof a.summary_stats === 'object' ? a.summary_stats : {};
  const year = +today.slice(0, 4);
  const per: Record<number, any> = {};
  for (const c of a.counts_by_year ?? []) if (c && typeof c === 'object') per[int(c.year)] = c;
  const years: [number, number, number][] = [];
  for (let y = year - YEARS + 1; y <= year; y++) years.push([y, int(per[y]?.works_count), int(per[y]?.cited_by_count)]);
  const mine = Object.keys(weights).filter(Boolean).map((t) => t.toLowerCase());
  const topics: [string, boolean][] = (a.topics ?? []).slice(0, 8).filter((t: any) => t && typeof t === 'object' && t.display_name)
    .map((t: any) => [text(t.display_name, 80), mine.some((m) => String(t.display_name).toLowerCase().includes(m))]);
  const inst = Array.isArray(a.last_known_institutions) && a.last_known_institutions[0] && typeof a.last_known_institutions[0] === 'object'
    ? a.last_known_institutions[0] : {};
  const rows: any[] = top && Array.isArray(top.results) ? top.results : [];
  const best = rows.slice(0, 5).filter((w) => w && typeof w === 'object' && w.title)
    .map((w) => ({ ...work(w), year: int(w.publication_year), cited: int(w.cited_by_count) }));
  return { works: int(a.works_count), cited: int(a.cited_by_count), h: int(stats.h_index), i10: int(stats.i10_index), years, topics,
    institution: text(inst.display_name, 160), top: best };
}

// ---- asking (through WISEP)
export async function fetchRecent(people: Light[], today = new Date().toISOString().slice(0, 10)): Promise<{ ok: boolean; busy?: boolean; recent: Record<string, Paper[]> }> {
  const ids = people.map((p) => p.id);
  if (!ids.length) return { ok: true, recent: {} };
  try {
    const r = await wiseFetch(recentUrl(ids, today), { page: 'circle:researchers:lights' });
    if (r.status !== 200) return { ok: false, busy: true, recent: {} };
    return { ok: true, recent: parseRecent(await r.json(), ids) };
  } catch {
    return { ok: false, busy: true, recent: {} };
  }
}

export async function fetchReport(aid: string, weights: Record<string, number>, today = new Date().toISOString().slice(0, 10)): Promise<{ ok: boolean; busy?: boolean; report?: Report }> {
  if (!AID.test(aid)) return { ok: false };
  try {
    const ra = await wiseFetch(authorUrl(aid), { page: 'circle:researchers:lights', force: true });
    if (ra.status !== 200) return { ok: false, busy: true };
    const rt = await wiseFetch(topUrl(aid), { page: 'circle:researchers:lights', force: true });
    return { ok: true, report: report(await ra.json(), rt.status === 200 ? await rt.json() : {}, weights, today) };
  } catch {
    return { ok: false, busy: true };
  }
}
