// Grow → 🗂️ Data: public datasets to practise and train on -- a port of the desktop's datasets.py (the reading,
// cleaning and ranking; harvesting runs on GitHub). The list is data/datasets.json, the same file the desktop ships;
// the app reads the newest copy from GitHub at most once a day and falls back to the one it shipped with.
// tests/test_datasets.py checks both apps give the same answers.
import AsyncStorage from '@react-native-async-storage/async-storage';
import bundled from '../data/datasets.json';
import { englishEnough } from './curated';
import { match, type Weights } from './interests';
import { find as findSkill } from './skills';
import { fetchT } from './net';
import { wiseFetch } from './wisep';
import { isStale, readCache, writeCache } from './storage';

export const REMOTE_URL = 'https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/datasets.json';
export const FIELDS = ['Biology & genomics', 'Plants & agriculture', 'Medicine & health', 'Neuroscience', 'Ecology & environment',
  'Earth & climate', 'Chemistry & materials', 'Physics & astronomy', 'Social science & economics', 'Machine learning & AI'];
const LEVELS = ['beginner', 'intermediate', 'advanced'];
/** Grow → Data's parts in the navigation: [part id, planet label, Ionicons name, the field it shows] (datasets.FIELD_PARTS). */
export const FIELD_PARTS: [string, string, string, string][] = [
  ['for-you', 'For you', 'sparkles-outline', 'for you'], ['new', 'New', 'radio-outline', 'new'],
  ['biology', 'Biology', 'git-merge-outline', 'Biology & genomics'],
  ['plants', 'Plants', 'leaf-outline', 'Plants & agriculture'], ['medicine', 'Medicine', 'medkit-outline', 'Medicine & health'],
  ['neuro', 'Neuro', 'pulse-outline', 'Neuroscience'], ['ecology', 'Ecology', 'bug-outline', 'Ecology & environment'],
  ['climate', 'Climate', 'earth-outline', 'Earth & climate'], ['chemistry', 'Chemistry', 'flask-outline', 'Chemistry & materials'],
  ['physics', 'Physics', 'planet-outline', 'Physics & astronomy'], ['social', 'Society', 'people-outline', 'Social science & economics'],
  ['ml', 'ML & AI', 'hardware-chip-outline', 'Machine learning & AI']];

/** 'data:biology' (or 'biology') -> 'Biology & genomics'; anything else -> 'for you' (datasets.field_for_part). */
export function fieldForPart(part: string): string {
  const slug = part.startsWith('data:') ? part.slice(5) : part;
  return FIELD_PARTS.find(([p]) => p === slug)?.[3] ?? 'for you';
}
const OPEN = ['cc0', 'cc-by', 'cc-by-sa', 'odbl', 'odc-by', 'pddl', 'public domain', 'mit', 'bsd', 'apache', 'cc-pddc', 'etalab'];
const LEVEL_BONUS: Record<string, number> = { beginner: 0.4, intermediate: 0.2, advanced: 0 };

export type Dataset = { id: string; title: string; field: string; why: string; about: string; level: string; skills: string[];
  source: string; url: string; download: string; size_mb: number; formats: string[]; license: string; nc: boolean; doi: string;
  tutorial: string; uses: number; core: boolean; checked: string };
export type Ranked = Dataset & { score: number; for: string[]; vote: number };

/** [open?, non-commercial?] for a licence name or id (datasets.licence_ok). */
export function licenceOk(licence: string): [boolean, boolean] {
  const s = (licence || '').toLowerCase().replace(/_/g, '-').replace(/ /g, '-').replace('public-domain', 'public domain');
  if (!s) return [false, false];
  const nc = s.includes('-nc');
  if (nc && s.startsWith('cc-by')) return [true, true];
  return [OPEN.some((o) => s.startsWith(o) || s.includes(o)) && !s.includes('-nd'), false];
}

const text = (v: unknown, n: number) => (typeof v === 'string' || typeof v === 'number' ? String(v).split(/\s+/).filter(Boolean).join(' ').slice(0, n).trimEnd() : '');
function https(v: unknown): string {
  const url = String(v ?? '').trim();
  try {
    const u = new URL(url);
    return u.protocol === 'https:' && u.host && !url.includes(' ') ? url.slice(0, 600) : '';
  } catch {
    return '';
  }
}

export function cleanItem(raw: any): Dataset | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const title = text(raw.title, 160), url = https(raw.url), download = https(raw.download);
  if (!title || !(url || download) || !FIELDS.includes(raw.field) || !LEVELS.includes(raw.level)) return null;
  const [open, nc] = licenceOk(text(raw.license, 40));
  if (!open) return null;
  const size = raw.size_mb;
  return {
    id: text(raw.id, 80) || title.toLowerCase(), title, field: raw.field, why: text(raw.why, 200), about: text(raw.about, 300), level: raw.level,
    skills: Array.isArray(raw.skills) ? raw.skills.slice(0, 6).map((s: unknown) => text(s, 60)).filter(Boolean) : [],
    source: text(raw.source, 60), url: url || download, download,
    size_mb: typeof size === 'number' && Number.isFinite(size) && size >= 0 && size < 1e6 ? size : 0,
    formats: Array.isArray(raw.formats) ? raw.formats.slice(0, 6).map((f: unknown) => text(f, 16)) : [],
    license: text(raw.license, 40), nc, doi: text(raw.doi, 80), tutorial: https(raw.tutorial),
    uses: Number.isInteger(raw.uses) && raw.uses >= 0 ? raw.uses : 0, core: raw.core === true, checked: text(raw.checked, 10),
  };
}

export function clean(data: any): { version: string; datasets: Dataset[] } {
  data = data && typeof data === 'object' && !Array.isArray(data) ? data : {};
  const rows = (Array.isArray(data.datasets) ? data.datasets.slice(0, 3000) : []).map(cleanItem).filter((d: Dataset | null): d is Dataset => !!d);
  const version = text(data.version, 10);
  return { version: version.length === 10 && version[4] === '-' ? version : '', datasets: rows };
}

/** The newest list: the copy in the app, or a newer one fetched from GitHub (at most once a day). */
export async function loadDatasets(): Promise<Dataset[]> {
  const shipped = clean(bundled);
  const cached = await readCache<{ version: string; datasets: Dataset[] }>('datasets');
  let best = cached?.data ? clean(cached.data) : shipped;
  if (!best.datasets.length || best.version < shipped.version) best = shipped;
  if (isStale(cached?.at, 24)) {
    try {
      const r = await fetchT(REMOTE_URL);
      if (r.ok) {
        const fresh = clean(await r.json());
        await writeCache('datasets', fresh);
        if (fresh.datasets.length && fresh.version >= best.version) best = fresh;
      }
    } catch { /* offline: what we have */ }
  }
  return best.datasets;
}

export const textOf = (d: Dataset) => `${d.title} ; ${d.why} ; ${d.about} ; ${d.skills.join(' ')} ; ${d.field}`;
const round4 = (x: number) => Math.round(x * 10000) / 10000;

/** Best first (datasets.rank): `field` is '' for all, 'for you', or one of FIELDS; `votes` {id: +1/-1}. */
export function rank(items: Dataset[], weights: Weights, wanted: string[] = [], field = '', votes: Record<string, number> = {}, top = 40):
  { items: Ranked[]; hidden: number } {
  const want = new Set(wanted.map((w) => w.toLowerCase()));
  const out: Ranked[] = [];
  let hidden = 0;
  for (const d of items) {
    const v = votes[d.id] ?? 0;
    if (v < 0) { hidden++; continue; }
    const fit = Object.keys(weights).length ? match(textOf(d), weights)[0] : 0;
    const hit = d.skills.filter((s) => want.has(s.toLowerCase()));
    if (field === 'for you' && !(fit || hit.length)) continue;
    if (field && field !== 'for you' && d.field !== field) continue;
    let score = 1 + 2 * fit + (hit.length ? 1.5 : 0) + LEVEL_BONUS[d.level] + (d.core ? 0.3 : 0) + 0.1 * Math.log10(1 + d.uses);
    score *= v > 0 ? 1.3 : 1;
    out.push({ ...d, score: round4(score), for: hit, vote: v });
  }
  out.sort((a, b) => b.score - a.score || (a.title < b.title ? -1 : a.title > b.title ? 1 : 0));
  return { items: out.slice(0, top), hidden };
}

/** "7 MB", "1.2 GB", "under 1 MB" (datasets.size_text: the same words on the computer). */
export function sizeText(mb: number): string {
  if (mb <= 0) return '';
  if (mb < 1) return 'under 1 MB';
  if (mb >= 1000) return `${Math.round(mb / 100) / 10} GB`;
  return `${Math.round(mb)} MB`;
}

// --------------------------------------------------------------------------- 🆕 the radar (datasets.radar_*)
// New public datasets on your own keywords, once a day, from Zenodo (newest first), NCBI GEO's new series and
// Figshare; the same rules as the list where they apply, on topic and in English. Nothing but the search words leaves.
const RADAR_KEY = 'mygeeky.datasets.radar';
const RADAR_TERMS = 3, RADAR_PER_TERM = 8, RADAR_DAYS = 30, RADAR_KEEP_DAYS = 60, RADAR_TOP = 10, RADAR_MAX = 200;
const MAX_TOTAL_MB = 5000;
const GATED = /\b(dbgap|uk ?biobank|mimic|kaggle\.com|ega-archive|controlled access|data access committee|upon request|on request|registration required)\b/i;
export type RadarItem = { id: string; title: string; source: string; url: string; date: string; size_mb: number; license: string; nc: boolean;
  about: string; term: string; formats: string[]; found?: string };
export type RadarState = { items?: RadarItem[]; seen?: string[]; checked_at?: string; terms?: string[] };

export function radarTerms(keywords: string[], weights: Weights): string[] {
  const out: string[] = [];
  // interest words only when they're real topics (in the skills dictionary): they can be names, which find nothing
  const byWeight = Object.entries(weights).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)).map(([w]) => w)
    .filter((w) => findSkill(w));
  for (const raw of [...keywords, ...byWeight]) {
    const t = String(raw).toLowerCase().split(/\s+/).filter(Boolean).join(' ');
    if (t.length >= 3 && !out.includes(t)) out.push(t);
    if (out.length === RADAR_TERMS) break;
  }
  return out;
}

// HTML entities, as Python's html.unescape reads the common ones (the desktop's _plain)
const ENTITIES: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: '\u00a0', auml: 'ä', ouml: 'ö',
  uuml: 'ü', Auml: 'Ä', Ouml: 'Ö', Uuml: 'Ü', szlig: 'ß', eacute: 'é', egrave: 'è', ecirc: 'ê', aacute: 'á', agrave: 'à', acirc: 'â',
  iacute: 'í', oacute: 'ó', uacute: 'ú', ntilde: 'ñ', ccedil: 'ç', aring: 'å', oslash: 'ø', ndash: '–', mdash: '—', hellip: '…',
  rsquo: '\u2019', lsquo: '\u2018', rdquo: '\u201d', ldquo: '\u201c', deg: '°', micro: 'µ', times: '×' };
const unescape = (s: string) => s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e: string) => {
  if (e[0] === '#') { const c = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10); return Number.isFinite(c) && c > 0 && c < 0x110000 ? String.fromCodePoint(c) : m; }
  return ENTITIES[e] ?? m;
});
const plain = (raw: unknown, n: number) => unescape(String(raw ?? '').replace(/<[^>]+>/g, ' '))
  .split(/\s+/).filter(Boolean).join(' ').slice(0, n);
const roundTo1 = (x: number) => Math.round(x * 10) / 10;

function formatsOf(names: string[]): string[] {
  const out: string[] = [];
  for (const n of names) {
    const parts = n.toLowerCase().split('.');
    while (parts.length > 2 && ['gz', 'bz2', 'xz', 'zip', 'tgz', 'tar'].includes(parts[parts.length - 1])) parts.pop();
    const ext = parts.length > 1 ? parts[parts.length - 1] : '';
    if (ext && !out.includes(ext)) out.push(ext);
  }
  return out.length ? out.slice(0, 6) : ['zip'];
}

function radarItem(id: string, title: unknown, source: string, url: unknown, day: unknown, sizeMb: number, licence: string, about: unknown,
  term: string, formats: string[]): RadarItem {
  return { id, title: plain(title, 160), source, url: https(url), date: String(day ?? '').slice(0, 10), size_mb: roundTo1(sizeMb),
    license: text(licence, 40), nc: licenceOk(licence)[1], about: plain(about, 300), term, formats: formats.slice(0, 4) };
}

export function parseZenodoNew(data: any, term: string): RadarItem[] {
  const hits: any[] = data?.hits?.hits ?? [];
  return hits.slice(0, RADAR_PER_TERM).filter((h) => h && typeof h === 'object').map((h) => {
    const m = h.metadata ?? {}, files: any[] = h.files ?? [];
    return radarItem(`zenodo-${h.id}`, m.title, 'Zenodo', h.links?.self_html, m.publication_date || h.created,
      files.reduce((a, f) => a + (f.size ?? 0), 0) / 1e6, String(m.license?.id ?? ''), m.description, term, formatsOf(files.map((f) => f.key ?? '')));
  });
}

export function parseGeoNew(result: any, ids: string[], term: string): RadarItem[] {
  const out: RadarItem[] = [];
  for (const i of ids.slice(0, RADAR_PER_TERM)) {
    const s = result?.[i];
    if (!s || typeof s !== 'object' || !/^GSE\d+$/.test(String(s.accession ?? ''))) continue;
    const acc = s.accession, day = String(s.pdat ?? '').replace(/\//g, '-');
    const about = `${s.n_samples ?? '?'} ${s.taxon ?? ''} samples · ${s.gdstype ?? ''}. ${s.summary ?? ''}`;
    out.push(radarItem(`geo-${acc.toLowerCase()}`, s.title, 'GEO (NCBI)', `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${acc}`, day, 0,
      'Public domain', about, term, ['soft']));
  }
  return out;
}

export function parseFigshareNew(d: any, term: string): RadarItem | null {
  if (!d || typeof d !== 'object' || !d.id) return null;
  const files: any[] = d.files ?? [];
  return radarItem(`figshare-${d.id}`, d.title, 'Figshare', d.url_public_html, d.published_date, files.reduce((a, f) => a + (f.size ?? 0), 0) / 1e6,
    String(d.license?.name ?? ''), d.description, term, formatsOf(files.map((f) => f.name ?? '')));
}

const norm = (s: string) => s.toLowerCase().replace(/[\s_-]+/g, ' ');
export const onTopic = (it: RadarItem) => { const t = norm(`${it.title} ${it.about}`); return norm(it.term).split(' ').filter((w) => w.length >= 3).every((w) => t.includes(w)); };

/** datasets.radar_ok: open, no gate, not too big, has a page, on topic and in English. */
export function radarOk(it: RadarItem): boolean {
  return !!it.title && !!it.url && licenceOk(it.license)[0] && !GATED.test(`${it.title} ${it.about}`) && it.size_mb <= MAX_TOTAL_MB
    && onTopic(it) && englishEnough(it.title, it.about);
}

const ageOf = (today: string, day: string) => {
  const a = Date.parse(`${today.slice(0, 10)}T00:00:00Z`), b = Date.parse(`${(day || '').slice(0, 10)}T00:00:00Z`);
  return Number.isFinite(a) && Number.isFinite(b) ? Math.round((a - b) / 86400000) : null;
};
const titleKey = (t: string) => t.toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 80);

export function radarMerge(state: RadarState, found: RadarItem[], today: string): RadarState {
  const items = new Map<string, RadarItem>();
  for (const i of state.items ?? []) if (i?.id && radarOk(i)) items.set(i.id, i);
  const titles = new Set([...items.values()].map((i) => titleKey(i.title)));
  for (const it of found) {
    const key = titleKey(it.title);
    if (radarOk(it) && !items.has(it.id) && !titles.has(key)) { items.set(it.id, { ...it, found: today.slice(0, 10) }); titles.add(key); }
  }
  const keep = [...items.values()].filter((i) => (ageOf(today, i.found ?? '') ?? 0) <= RADAR_KEEP_DAYS);
  const k = (i: RadarItem) => `${i.found ?? ''}\u0000${i.date}\u0000${i.id}`;
  keep.sort((a, b) => (k(a) < k(b) ? 1 : k(a) > k(b) ? -1 : 0));
  return { ...state, items: keep.slice(0, RADAR_MAX), seen: (state.seen ?? []).filter((s) => items.has(s)).slice(-RADAR_MAX * 2) };
}

export type RadarRanked = RadarItem & { score: number; new: boolean; vote: number };
export function radarRank(state: RadarState, weights: Weights, votes: Record<string, number> = {}, today = '', top = RADAR_TOP):
  { items: RadarRanked[]; hidden: number; new: number } {
  const seen = new Set(state.seen ?? []);
  const out: RadarRanked[] = [];
  let hidden = 0;
  for (const i of state.items ?? []) {
    const v = votes[i.id] ?? 0;
    if (v < 0) { hidden++; continue; }
    const a = today ? ageOf(today, i.date || i.found || '') : null;
    const fresh = Math.max(0, 1 - (a !== null && a >= 0 ? a : RADAR_DAYS) / RADAR_DAYS);
    const fit = Object.keys(weights).length ? match(`${i.title} ; ${i.about}`, weights)[0] : 0;
    const score = (1 + 2 * fit + fresh) * (v > 0 ? 1.3 : 1);
    out.push({ ...i, score: round4(score), new: !seen.has(i.id), vote: v });
  }
  out.sort((a, b) => b.score - a.score || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return { items: out.slice(0, top), hidden, new: out.filter((i) => i.new).length };
}

export async function loadRadar(): Promise<RadarState> {
  try {
    return JSON.parse((await AsyncStorage.getItem(RADAR_KEY)) ?? '{}') ?? {};
  } catch {
    return {};
  }
}

export async function radarSeen(ids: string[]): Promise<void> {
  const st = await loadRadar();
  const seen = [...(st.seen ?? [])];
  for (const i of ids) if (!seen.includes(i)) seen.push(i);
  await AsyncStorage.setItem(RADAR_KEY, JSON.stringify({ ...st, seen: seen.slice(-RADAR_MAX * 2) })).catch(() => undefined);
}

/** Search for new datasets on your keywords, at most once a day (datasets.radar_refresh). */
export async function refreshRadar(keywords: string[], weights: Weights, force = false): Promise<RadarState> {
  let st = await loadRadar();
  if (!force && st.checked_at && Date.now() - Date.parse(st.checked_at) < 24 * 3600000) return st;
  const terms = radarTerms(keywords, weights);
  const found: RadarItem[] = [];
  const q = (o: Record<string, string | number>) => Object.entries(o).map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&');
  for (const term of terms) {
    try {
      const r = await wiseFetch(`https://zenodo.org/api/records?${q({ q: term, type: 'dataset', sort: 'mostrecent', size: RADAR_PER_TERM })}`, { page: 'grow:data:new', force });
      if (r.ok) found.push(...parseZenodoNew(await r.json(), term));
    } catch { /* one source down: the others still count */ }
    try {
      const eu = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils';
      const s = await wiseFetch(`${eu}/esearch.fcgi?${q({ db: 'gds', term: `${term} AND gse[ETYP]`, reldate: RADAR_DAYS, datetype: 'pdat', retmax: RADAR_PER_TERM, retmode: 'json' })}`, { page: 'grow:data:new', force });
      const ids: string[] = s.ok ? ((await s.json())?.esearchresult?.idlist ?? []) : [];
      if (ids.length) {
        const r = await wiseFetch(`${eu}/esummary.fcgi?${q({ db: 'gds', id: ids.join(','), retmode: 'json' })}`, { page: 'grow:data:new', force });
        if (r.ok) found.push(...parseGeoNew((await r.json())?.result ?? {}, ids, term));
      }
    } catch { /* as above */ }
    try {
      const r = await fetchT('https://api.figshare.com/v2/articles/search', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_for: term, item_type: 3, order: 'published_date', order_direction: 'desc', page_size: RADAR_PER_TERM / 2 }) });
      const hits: any[] = r.ok ? await r.json() : [];
      for (const h of Array.isArray(hits) ? hits : []) {
        const d = await wiseFetch(`https://api.figshare.com/v2/articles/${Number(h.id)}`, { page: 'grow:data:new', force });
        const it = d.ok ? parseFigshareNew(await d.json(), term) : null;
        if (it) found.push(it);
      }
    } catch { /* as above */ }
  }
  st = { ...radarMerge(st, found, new Date().toISOString().slice(0, 10)), checked_at: new Date().toISOString(), terms };
  await AsyncStorage.setItem(RADAR_KEY, JSON.stringify(st)).catch(() => undefined);
  return st;
}
