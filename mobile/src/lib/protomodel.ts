// The small protocol model -- the same numbers as the desktop's protomodel.py
// (data/protocol_model.json, trained on the maker's computer). It reads what a search
// returns for a repo or article and says how likely it is to be learning material for
// each stage: none, basics, deeper, applied, project. The skill's own name is masked,
// so what it learned carries over to skills it never saw.
import { gh } from './github';
import { wiseFetch } from './wisep';
import { blockedSource, isBench } from './safety';

export const ROLES = ['none', 'basics', 'deeper', 'applied', 'project'] as const;
export type Cand = { kind: 'repo' | 'article'; id: string; title: string; url: string; text: string; topics: string[];
  language?: string; stars?: number; updated?: string; pages?: boolean; archived?: boolean; type?: string; year?: number;
  cited?: number; oa?: boolean; venue?: string; askedBy?: string };
type Model = { roles: string[]; bias: number[]; weights: Record<string, number[]> };
// loaded the first time it's needed, not at startup: the bundle's data files are parsed into memory when imported
// (Metro's inline requires are off), and most people never open this (docs/RESOURCES.md, plan 9)
let M: Model | null = null;
const bundledModel = (): Model => (M ??= require('../data/protocol_model.json') as Model);

const OPENALEX = 'https://api.openalex.org';

export const term = (name: string) => (name.includes(' ') ? `"${name}"` : name);

export function githubQueries(name: string, kind = '', goal = ''): string[] {
  const t = term(name);
  const qs = [`${t} tutorial`, `${t} course`, `${t} workshop`, `awesome ${t}`, `${t} book`];
  if (goal) qs.splice(1, 0, `${t} ${goal}`);
  qs.push(kind !== 'language' ? `${t} ${goal || 'analysis'} example` : `${goal || 'analysis'} language:${name}`);
  return qs;
}

export function articleQueries(name: string, goal = ''): [string, string][] {
  const w = `${name} ${goal}`.trim();
  return [[`${w} tutorial`, ''], [w, 'type:review']];
}

export function fromRepo(r: any): Cand | null {
  if (!r?.full_name || r.fork) return null;
  if (isBench(`${r.full_name} ${r.description ?? ''}`)) return null;   // a repo of bench protocols, not this
  return { kind: 'repo', id: `gh:${String(r.full_name).toLowerCase()}`, title: String(r.full_name).slice(0, 140),
    url: `https://github.com/${r.full_name}`, text: String(r.description ?? '').split(/\s+/).join(' ').slice(0, 400),
    topics: (r.topics ?? []).slice(0, 20).map((t: unknown) => String(t).slice(0, 50)), language: String(r.language ?? '').slice(0, 40),
    stars: Number(r.stargazers_count ?? 0), updated: String(r.pushed_at ?? '').slice(0, 10), pages: !!r.has_pages,
    archived: !!r.archived };
}

function abstract(inv: any, limit = 600): string {
  if (!inv || typeof inv !== 'object') return '';
  const spots: [number, string][] = [];
  for (const [w, ps] of Object.entries(inv)) if (Array.isArray(ps)) for (const p of ps) if (Number.isInteger(p)) spots.push([p as number, w]);
  return spots.sort((a, b) => a[0] - b[0] || (a[1] < b[1] ? -1 : 1)).map((x) => x[1]).join(' ').slice(0, limit);
}

export function fromWork(w: any): Cand | null {
  if (!w?.title) return null;
  const wid = String(w.id ?? '').split('/').pop() ?? '';
  if (!/^W\d{2,12}$/.test(wid)) return null;
  const doi = String(w.doi ?? '');
  const url = doi.startsWith('https://') ? doi : `https://openalex.org/${wid}`;
  const sourceId = String(w.primary_location?.source?.id ?? '');
  if (blockedSource(url, sourceId)) return null;        // a protocol journal is never a candidate at all
  return { kind: 'article', id: `oa:${wid}`, title: String(w.title).split(/\s+/).join(' ').slice(0, 200),
    url, text: abstract(w.abstract_inverted_index), topics: [],
    type: String(w.type ?? '').slice(0, 20), year: Number(w.publication_year ?? 0), cited: Number(w.cited_by_count ?? 0),
    oa: !!w.open_access?.is_oa, venue: String(w.primary_location?.source?.display_name ?? '').slice(0, 80) };
}

export async function searchGithub(q: string, token: string | null, perPage = 20): Promise<Cand[]> {
  const d = await gh<{ items?: any[] }>(`/search/repositories?q=${encodeURIComponent(q)}&sort=stars&per_page=${perPage}`, token);
  return (d.items ?? []).map(fromRepo).filter((c): c is Cand => !!c);
}

export async function searchOpenalex(search: string, filter = '', perPage = 12): Promise<Cand[]> {
  const p = new URLSearchParams({ search, 'per-page': String(perPage),
    select: 'id,title,doi,type,publication_year,cited_by_count,open_access,abstract_inverted_index,primary_location' });
  if (filter) p.set('filter', filter);
  const r = await wiseFetch(`${OPENALEX}/works?${p.toString()}`, { page: 'grow:paths' });
  if (!r.ok) return [];
  const d = await r.json();
  return (d.results ?? []).map(fromWork).filter((c: Cand | null): c is Cand => !!c);
}

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const bin = (n: number, edges: number[]) => edges.filter((e) => n >= e).length;

export function mask(text: string, aliases: string[]): string {
  let out = text.toLowerCase();
  for (const a of [...new Set(aliases.map((x) => x.toLowerCase()).filter(Boolean))].sort((x, y) => y.length - x.length)) {
    out = out.replace(new RegExp(`(^|[^a-z0-9])${esc(a)}s?(?![a-z0-9])`, 'g'), '$1 qqskillqq ');
  }
  return out;
}

export function tokens(c: Cand, aliases: string[] = [], today = new Date()): Set<string> {
  const name = (c.title ?? '').replace(/[-_./]+/g, ' ');
  const raw = [name, c.text ?? '', (c.topics ?? []).join(' ')].join(' ; ');
  const words = (mask(raw, aliases).match(/[a-z0-9][a-z0-9+#]*/g) ?? []).map((w) => (w === 'qqskillqq' ? '__skill' : w));
  const out = new Set<string>(words);
  for (let i = 0; i + 1 < words.length; i++) out.add(`${words[i]}_${words[i + 1]}`);
  out.add(`__kind_${c.kind}`);
  if (!(c.text ?? '').trim()) out.add('__no_text');
  if (c.kind === 'repo') {
    out.add(`__stars_${bin(c.stars ?? 0, [10, 100, 1000, 10000])}`);
    const t = Date.parse(`${(c.updated ?? '').slice(0, 10)}T00:00:00Z`);
    if (!Number.isNaN(t)) out.add(`__updated_${bin((today.getTime() - t) / (365.25 * 86400000), [1, 3, 6])}`);
    if (c.pages) out.add('__pages');
    if (c.archived) out.add('__archived');
    const lang = (c.language ?? '').toLowerCase();
    out.add(lang ? `__lang_${lang}` : '__lang_none');
  } else {
    out.add(`__type_${c.type || 'other'}`);
    out.add(`__cited_${bin(c.cited ?? 0, [10, 100, 1000])}`);
    if (c.oa) out.add('__oa');
    out.add(`__age_${bin(today.getUTCFullYear() - (c.year || today.getUTCFullYear()), [3, 8, 15])}`);
  }
  return out;
}

/** {role: probability} for a candidate. */
export function predict(c: Cand, aliases: string[] = [], m: Model = bundledModel(), today = new Date()): Record<string, number> {
  const z = [...m.bias];
  for (const t of tokens(c, aliases, today)) {
    const w = m.weights[t];
    if (w) w.forEach((x, i) => { z[i] += x; });
  }
  const top = Math.max(...z);
  const e = z.map((x) => Math.exp(x - top));
  const sum = e.reduce((a, b) => a + b, 0);
  return Object.fromEntries(m.roles.map((r, i) => [r, e[i] / sum]));
}
