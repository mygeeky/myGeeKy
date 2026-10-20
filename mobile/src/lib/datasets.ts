// Grow → 🗂️ Data: public datasets to practise and train on -- a port of the desktop's datasets.py (the reading,
// cleaning and ranking; harvesting runs on GitHub). The list is data/datasets.json, the same file the desktop ships;
// the app reads the newest copy from GitHub at most once a day and falls back to the one it shipped with.
// tests/test_datasets.py checks both apps give the same answers.
import bundled from '../data/datasets.json';
import { match, type Weights } from './interests';
import { fetchT } from './net';
import { isStale, readCache, writeCache } from './storage';

export const REMOTE_URL = 'https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/datasets.json';
export const FIELDS = ['Biology & genomics', 'Plants & agriculture', 'Medicine & health', 'Neuroscience', 'Ecology & environment',
  'Earth & climate', 'Chemistry & materials', 'Physics & astronomy', 'Social science & economics', 'Machine learning & AI'];
const LEVELS = ['beginner', 'intermediate', 'advanced'];
/** Grow → Data's parts in the navigation: [part id, planet label, Ionicons name, the field it shows] (datasets.FIELD_PARTS). */
export const FIELD_PARTS: [string, string, string, string][] = [
  ['for-you', 'For you', 'sparkles-outline', 'for you'], ['biology', 'Biology', 'git-merge-outline', 'Biology & genomics'],
  ['plants', 'Plants', 'leaf-outline', 'Plants & agriculture'], ['medicine', 'Medicine', 'medkit-outline', 'Medicine & health'],
  ['neuro', 'Neuroscience', 'pulse-outline', 'Neuroscience'], ['ecology', 'Ecology', 'bug-outline', 'Ecology & environment'],
  ['climate', 'Earth & climate', 'earth-outline', 'Earth & climate'], ['chemistry', 'Chemistry', 'flask-outline', 'Chemistry & materials'],
  ['physics', 'Physics & space', 'planet-outline', 'Physics & astronomy'], ['social', 'Society', 'people-outline', 'Social science & economics'],
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
