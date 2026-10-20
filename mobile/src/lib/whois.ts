// "Is this you?": find your OpenAlex author record from your name and institution, with no ORCID -- a port of the
// desktop's whois.py (tests/test_whois.py runs both on the same answers). At most two calls. If OpenAlex is busy,
// setup carries on with keywords and the search stays pending: tried again later, and when it works, myGeeKy asks
// "Is this you?". Nothing is saved until you confirm.
import { wiseFetch } from './wisep';

export type Candidate = {
  id: string; name: string; institution: string; country: string; works: number; cited: number;
  topics: string[]; orcid: string; titles: string[]; score?: number;
};
export type Found = { status: 'found' | 'none' | 'busy'; candidates: Candidate[]; retry_after?: number; why?: string };

const OPENALEX = 'https://api.openalex.org';
export const SHOWN = 5;
const TITLES = 3;
export const RETRY_MIN_SECONDS = 1800;
const ID = /^A\d{2,12}$/;
const GENERIC_HOST = ['ac', 'edu', 'com', 'org', 'net', 'gov', 'www'];
const GENERIC_SUB = ['mail', 'med', 'cs', 'bio', 'dept', 'student', 'students'];
const PLACE_SKIP = new Set(['of', 'the', 'and', 'de', 'university', 'institute']);

export function norm(s: string): string {
  return String(s ?? '').normalize('NFKD').replace(/[^\x00-\x7f]/g, '').toLowerCase().replace(/[^a-z]+/g, ' ').trim()
    .split(/\s+/).filter(Boolean).join(' ');
}

export function domainHint(text: string): string {
  const m = /@([A-Za-z0-9.-]+)/.exec(text ?? '');
  if (!m) return text ?? '';
  const parts = m[1].toLowerCase().split('.').filter((p) => !GENERIC_HOST.includes(p))
    .filter((p) => p.length > 2 && !GENERIC_SUB.includes(p));
  return parts.slice(0, 2).map(norm).join(' ');
}

const round4 = (v: number) => Math.round(v * 10000) / 10000;

export function nameScore(query: string, candidate: string): number {
  const q = norm(query).split(' ').filter(Boolean), c = norm(candidate).split(' ').filter(Boolean);
  if (!q.length || !c.length || !c.includes(q[q.length - 1])) return 0;
  let hits = 0;
  for (const w of q) {
    if (c.includes(w)) hits += 1;
    else if (w.length === 1 && c.some((x) => x.startsWith(w))) hits += 0.8;
    else if (c.some((x) => x.length === 1 && w.startsWith(x))) hits += 0.8;
  }
  return round4(hits / Math.max(q.length, c.length));
}

export function placeScore(hint: string, institution: string): number {
  const h = new Set(norm(hint).split(' ').filter((w) => w && !PLACE_SKIP.has(w)));
  const i = new Set(norm(institution).split(' ').filter(Boolean));
  if (!h.size) return 0;
  return round4([...h].filter((w) => i.has(w)).length / h.size);
}

export function parseAuthors(data: any): Candidate[] {
  const out: Candidate[] = [];
  for (const a of Array.isArray(data?.results) ? data.results : []) {
    if (!a || typeof a !== 'object') continue;
    const id = String(a.id ?? '').split('/').pop() ?? '';
    if (!ID.test(id)) continue;
    const insts = (Array.isArray(a.last_known_institutions) ? a.last_known_institutions : []).filter((i: any) => i && typeof i === 'object');
    const inst = insts[0] ?? {};
    out.push({
      id, name: String(a.display_name ?? ''), institution: String(inst.display_name ?? ''), country: String(inst.country_code ?? ''),
      works: Math.trunc(Number(a.works_count) || 0), cited: Math.trunc(Number(a.cited_by_count) || 0),
      topics: (Array.isArray(a.topics) ? a.topics.slice(0, 3) : []).filter((t: any) => t && typeof t === 'object' && t.display_name)
        .map((t: any) => String(t.display_name)),
      orcid: String(a.orcid ?? '').split('/').pop() ?? '', titles: [],
    });
  }
  return out;
}

export function rank(cands: Candidate[], name: string, hint = ''): Candidate[] {
  const scored: Candidate[] = [];
  for (const c of cands) {
    const n = nameScore(name, c.name);
    if (n <= 0) continue;
    const score = 0.6 * n + 0.3 * placeScore(hint, c.institution) + 0.1 * Math.min(Math.log10(1 + c.works) / 3, 1);
    scored.push({ ...c, score: round4(score) });
  }
  scored.sort((a, b) => b.score! - a.score! || b.works - a.works || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return scored.slice(0, SHOWN);
}

export function addTitles(cands: Candidate[], works: any): Candidate[] {
  const by: Record<string, [number, string][]> = Object.fromEntries(cands.map((c) => [c.id, []]));
  for (const w of Array.isArray(works?.results) ? works.results : []) {
    const title = String(w?.title ?? '').trim();
    const year = Math.trunc(Number(w?.publication_year) || 0);
    for (const a of Array.isArray(w?.authorships) ? w.authorships : []) {
      const aid = String(a?.author?.id ?? '').split('/').pop() ?? '';
      if (aid in by && title && by[aid].every(([, t]) => t !== title)) by[aid].push([year, title]);
    }
  }
  return cands.map((c) => {
    const recent = [...by[c.id]].sort((x, y) => y[0] - x[0] || (x[1] < y[1] ? -1 : x[1] > y[1] ? 1 : 0)).slice(0, TITLES);
    return { ...c, titles: recent.map(([y, t]) => (y ? `${t} (${y})` : t)) };
  });
}

export const authorsUrl = (name: string) => `${OPENALEX}/authors?search=${encodeURIComponent(norm(name))}&per-page=25`
  + '&select=id,display_name,last_known_institutions,works_count,cited_by_count,topics,orcid';
export const worksUrl = (ids: string[]) => `${OPENALEX}/works?filter=author.id:${ids.join('|')}&sort=publication_date:desc&per-page=50`
  + '&select=title,publication_year,authorships';
export const busy = (status: number) => status === 429 || status >= 500;

export async function search(name: string, hint = '', page = 'you:whois'): Promise<Found> {
  const h = hint.includes('@') ? domainHint(hint) : hint;
  if (norm(name).split(' ').filter(Boolean).length < 2) return { status: 'none', candidates: [], why: 'Type your first and last name.' };
  try {
    const r = await wiseFetch(authorsUrl(name), { page, force: true });   // a search you typed: asked now, counted
    if (busy(r.status)) return { status: 'busy', candidates: [], retry_after: Number(r.headers.get('retry-after')) || 0 };
    if (!r.ok) return { status: 'busy', candidates: [], retry_after: 0 };
    let cands = rank(parseAuthors(await r.json()), name, h);
    if (!cands.length) return { status: 'none', candidates: [] };
    const w = await wiseFetch(worksUrl(cands.map((c) => c.id)), { page, force: true });
    if (w.status === 200) cands = addTitles(cands, await w.json());
    return { status: 'found', candidates: cands };
  } catch {
    return { status: 'busy', candidates: [], retry_after: 0 };
  }
}

export const nextTry = (now: number, retryAfter = 0) => now + Math.max(RETRY_MIN_SECONDS, Math.trunc(retryAfter || 0));
