// The lists myGeeKy's maker curates by hand (verified jobs, funding, conferences,
// learning resources): a port of the desktop's curated.py. The whole file is
// downloaded (at most every few hours) and matched to you here, on the phone:
// nobody learns what matched or that you looked. Anything with a deadline
// disappears the day after it.
import { countryOf } from './countries';
import { match, Weights } from './interests';
import { fetchT } from './net';
import { cleanProtocol, type Protocol } from './protocol-shape';
import { isStale, readCache, writeCache } from './storage';
import * as taste from './taste';
import { cleanAll as cleanHighlights, type Highlight } from './highlight-shape';

export const REMOTE_URL = 'https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/curated.json';
const CHECK_EVERY_HOURS = 6;
export const LISTS = ['jobs', 'funding', 'conferences', 'resources'] as const;
export type ListName = (typeof LISTS)[number];
const DATED: ListName[] = ['jobs', 'funding', 'conferences'];
export const VOTE_KIND: Record<ListName, taste.Kind> = { jobs: 'job', funding: 'funding', conferences: 'conference', resources: 'resource' };
export const JOB_TYPES: Record<string, string> = { phd: 'PhD', postdoc: 'Postdoc', master: "Master's", job: 'Job', internship: 'Internship',
  fellowship: 'Fellowship', faculty: 'Faculty', engineer: 'Research engineer' };
export const RESOURCE_TYPES: Record<string, string> = { repo: '📦', website: '🌐', course: '🎓', book: '📖', tutorial: '🧭', video: '🎬' };
const LEVELS = ['beginner', 'intermediate', 'advanced'];
const ID_RE = /^[a-z0-9][a-z0-9-]{2,79}$/;
export const REPORT_EMAIL = 'support@mygeeky.org';

export type Item = {
  id: string; title: string; url: string; keywords: string[]; summary: string; deadline?: string;
  org?: string; place?: string; type?: string; remote?: boolean; who?: string; amount?: string;
  starts?: string; ends?: string; student?: string; skills?: string[]; level?: string; free?: boolean;
  // a listing from a board in another language: the English is in `title`, these say where it came from
  original_title?: string; language?: string;
  // the same listing to read in other languages, each entry carrying its own name and direction
  translations?: Record<string, Said>;
  // the country `place` names, worked out here so a filter never has to guess twice
  country?: string;
};
export type Said = { name: string; rtl: boolean; title: string; summary?: string; who?: string;
  amount?: string; student?: string };
export type Lists = { version: string; protocols: Protocol[]; seasons: unknown[]; highlights: Highlight[]; signals_hidden?: string[] } & Record<ListName, Item[]>;
export type Ranked = Item & { score: number; match: string[]; daysLeft: number | null; vote: number };

const text = (v: unknown, n: number) => (typeof v === 'string' || typeof v === 'number' ? String(v).split(/\s+/).join(' ').trim().slice(0, n) : '');
function https(v: unknown): string {
  const u = String(v ?? '').trim();
  return /^https:\/\/[^\s/]+\.[^\s]*$/.test(u) && !u.includes(' ') ? u.slice(0, 500) : '';
}
function day(v: unknown): string {
  const s = String(v ?? '').slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(`${s}T00:00:00Z`)) ? s : '';
}
const words = (v: unknown, n = 12) => Array.isArray(v)
  ? [...new Set(v.map((x) => text(x, 40).toLowerCase()).filter(Boolean))].slice(0, n) : [];

// The languages a listing can also be read in: (own name, right-to-left). The name is written into the
// lists beside every translation, so a language added later arrives with the lists, not with a new app.
export const LANGUAGES: Record<string, [string, boolean]> = {
  ar: ['العربية', true], fr: ['Français', false], de: ['Deutsch', false], es: ['Español', false], zh: ['中文', false],
};
const CODE_RE = /^[a-z]{2}(-[a-z]{2})?$/;
const SAID: [keyof Said, number][] = [['title', 140], ['summary', 400], ['who', 160], ['amount', 60], ['student', 160]];

/** The same listing in other languages. Only ever a reading aid: nothing here can drop a listing. */
export function cleanTranslations(raw: any): Record<string, Said> {
  const out: Record<string, Said> = {};
  if (!raw || typeof raw !== 'object') return out;
  for (const [key, val] of Object.entries(raw).slice(0, 20)) {
    const code = String(key).trim().toLowerCase();
    if (!CODE_RE.test(code) || !val || typeof val !== 'object') continue;
    const known = LANGUAGES[code];
    const name = text((val as any).name, 30) || (known ? known[0] : '');
    const said: any = { name, rtl: !!((val as any).rtl ?? (known ? known[1] : false)) };
    for (const [f, n] of SAID) { const v = text((val as any)[f], n); if (v) said[f] = v; }
    if (name && said.title) out[code] = said as Said;
  }
  return out;
}

/** The codes a listing is translated into, the known languages first. */
export function languagesOf(it: Item): string[] {
  const known = Object.keys(LANGUAGES);
  const at = (c: string) => (known.indexOf(c) < 0 ? known.length : known.indexOf(c));
  return Object.keys(it.translations ?? {}).sort((a, b) => at(a) - at(b) || a.localeCompare(b));
}

// curated.english_enough: the boards may be in any language; what people are shown is English. Function words are
// counted, not accents: a London post at the Universite de Paris is still English, a French listing is full of
// "de", "pour", "la"; nothing marking either (a short title) counts as English.
const ENGLISH = new Set(['about', 'an', 'and', 'applications', 'apply', 'are', 'as', 'at', 'be', 'by', 'candidate', 'candidates', 'closing', 'conference', 'date', 'deadline', 'department', 'engineer', 'fellowship', 'for', 'from', 'funding', 'grant', 'has', 'have', 'in', 'institute', 'into', 'is', 'it', 'its', 'meeting', 'of', 'on', 'or', 'our', 'phd', 'position', 'postdoc', 'postdoctoral', 'research', 'researcher', 'school', 'scientist', 'student', 'that', 'the', 'this', 'to', 'under', 'university', 'we', 'what', 'who', 'will', 'with', 'within', 'workshop', 'years', 'you', 'your']);
const OTHER = new Set(['au', 'aux', 'avec', 'bei', 'borsa', 'candidature', 'cette', 'chez', 'como', 'con', 'dans', 'das', 'de', 'degli', 'del', 'della', 'delle', 'dem', 'den', 'der', 'des', 'die', 'dont', 'dos', 'du', 'een', 'ein', 'eine', 'einen', 'emploi', 'en', 'für', 'het', 'investigación', 'la', 'laboratoire', 'las', 'le', 'les', 'leur', 'los', 'met', 'mit', 'nel', 'nicht', 'nous', 'não', 'offre', 'ont', 'par', 'para', 'pela', 'pelo', 'plaza', 'por', 'poste', 'pour', 'questo', 'recrute', 'ricerca', 'sao', 'sein', 'ses', 'sind', 'sobre', 'sono', 'sont', 'stage', 'sur', 'una', 'und', 'une', 'van', 'voor', 'vous', 'zijn']);
export function englishEnough(...parts: unknown[]): boolean {
  const ws = parts.map((p) => String(p ?? '')).join(' ').toLowerCase().match(/[a-zà-öø-ÿ']+/g) ?? [];
  if (!ws.length) return false;
  return ws.filter((w) => ENGLISH.has(w)).length >= ws.filter((w) => OTHER.has(w)).length;
}

export function cleanItem(kind: ListName, raw: any): Item | null {
  if (!raw || typeof raw !== 'object' || !ID_RE.test(String(raw.id ?? ''))) return null;
  const it: Item = { id: raw.id, title: text(raw.title, 140), url: https(raw.url), keywords: words(raw.keywords), summary: text(raw.summary, 400) };
  if (!it.title || !it.url) return null;
  const original = text(raw.original_title, 140), language = text(raw.language, 30);
  if (original && language) Object.assign(it, { original_title: original, language });   // translated, and says so
  if (DATED.includes(kind) && !englishEnough(it.title, it.summary)) return null;
  if (DATED.includes(kind)) {
    it.deadline = day(raw.deadline);
    if (!it.deadline) return null;
    const said = cleanTranslations(raw.translations);
    if (Object.keys(said).length) it.translations = said;
  }
  if (kind === 'jobs') {
    const t = String(raw.type ?? 'job').toLowerCase();
    Object.assign(it, { org: text(raw.org, 100), place: text(raw.place, 80), type: t in JOB_TYPES ? t : 'job', remote: !!raw.remote });
    it.country = countryOf(it.place);
  } else if (kind === 'funding') {
    Object.assign(it, { org: text(raw.org, 100), who: text(raw.who, 160), amount: text(raw.amount, 60) });
  } else if (kind === 'conferences') {
    Object.assign(it, { place: text(raw.place, 80), starts: day(raw.starts), ends: day(raw.ends), student: text(raw.student, 160) });
    it.country = countryOf(it.place);
  } else {
    const t = String(raw.type ?? 'website').toLowerCase();
    const lv = String(raw.level ?? '').toLowerCase();
    Object.assign(it, { type: t in RESOURCE_TYPES ? t : 'website', skills: words(raw.skills), level: LEVELS.includes(lv) ? lv : '',
      free: raw.free !== false });
  }
  return it;
}

export function clean(data: any): Lists {
  // `seasons` is passed through raw and cleaned by seasons.ts, the way protocols are by protocol-shape.ts
  const out = { version: text(data?.version, 40), protocols: [] as Protocol[],
    seasons: Array.isArray(data?.seasons) ? data.seasons.slice(0, 300) : [],
    highlights: cleanHighlights(data?.highlights),                  // the maker's stories (highlight-shape.ts)
    // beacons hidden from everyone for breaking the Signals terms (curated.clean)
    signals_hidden: (Array.isArray(data?.signals_hidden) ? data.signals_hidden.slice(0, 500) : [])
      .filter((u: unknown) => typeof u === 'string' && /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/.test(u)) } as Lists;
  const pids = new Set<string>();
  for (const raw of (Array.isArray(data?.protocols) ? data.protocols : []).slice(0, 200)) {
    const p = cleanProtocol(raw, true);                 // reviewed protocols: a skill as ordered stages (protocols.ts)
    if (p && !pids.has(p.id)) {
      pids.add(p.id);
      out.protocols.push(p);
    }
  }
  for (const kind of LISTS) {
    const seen = new Set<string>();
    out[kind] = (Array.isArray(data?.[kind]) ? data[kind].slice(0, 500) : [])
      .map((r: any) => cleanItem(kind, r)).filter((x: Item | null): x is Item => !!x && !seen.has(x.id) && !!seen.add(x.id));
  }
  return out;
}

/** The newest lists we have: the ones in the app, or newer ones fetched since (every few hours). */
export async function loadLists(force = false): Promise<Lists> {
  // loaded the first time it's needed, not at startup: the bundle's data files are parsed into memory when imported
  // (Metro's inline requires are off), and most people never open this (docs/RESOURCES.md, plan 9)
  const shipped = clean(require('../data/curated.json'));
  const cached = await readCache<Lists>('curated');
  // the newest version wins; on a tie the fetched copy (the maker may have edited without a new version)
  let best = cached?.data && cached.data.version >= shipped.version ? clean(cached.data) : shipped;
  if (force || isStale(cached?.at, CHECK_EVERY_HOURS)) {
    try {
      const r = await fetchT(REMOTE_URL);
      if (r.ok) {
        const fresh = clean(await r.json());
        await writeCache('curated', fresh);
        if (fresh.version >= best.version) best = fresh;
      }
    } catch {
      /* offline: what we have */
    }
  }
  return best;
}

const todayIso = () => new Date().toISOString().slice(0, 10);
export function daysLeft(it: Item, today = todayIso()): number | null {
  if (!it.deadline) return null;
  return Math.round((Date.parse(`${it.deadline}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86400000);
}
export const live = (items: Item[], today = todayIso()) => items.filter((it) => {
  const d = daysLeft(it, today);
  return d === null || d >= 0;
});

/** A whole word (or phrase), plural allowed. No lookbehind: older phone JS engines lack it. */
export const wordRe = (t: string) => new RegExp(`(^|[^a-z0-9])${t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}s?(?![a-z0-9])`);

const textOf = (it: Item) => [it.title, it.summary, it.org ?? '', it.keywords.join(' '), (it.skills ?? []).join(' ')].join(' ; ');

/** Best first; 👎 ones are hidden (counted). Matching runs here, with your model and your votes. */
export async function ranked(kind: ListName, lists: Lists, weights: Weights, extra: Weights = {}):
  Promise<{ items: Ranked[]; hidden: number }> {
  const votes = await taste.load();
  const w = { ...weights };
  for (const [t, v] of Object.entries(extra)) w[t] = Math.max(w[t] ?? 0, v);
  const leanW = taste.weights(votes, [VOTE_KIND[kind]]);
  let hidden = 0;
  const items: Ranked[] = [];
  for (const it of live(lists[kind])) {
    const v = taste.voteOf(votes, VOTE_KIND[kind], it.id);
    if (v < 0) {
      hidden++;
      continue;
    }
    const [fit, why] = match(textOf(it), w);
    const tilt = taste.lean(textOf(it), [...it.keywords, ...(it.skills ?? [])], leanW);
    items.push({ ...it, score: 0.15 + 0.6 * fit + 0.35 * tilt + (v > 0 ? 0.3 : 0), match: why, daysLeft: daysLeft(it), vote: v });
  }
  items.sort((a, b) => b.score - a.score || (a.daysLeft ?? 9999) - (b.daysLeft ?? 9999));
  return { items, hidden };
}

/** Learning resources that teach a skill (its own tag first, then a mention). */
export function forSkill(name: string, aliases: string[], lists: Lists): Item[] {
  const names = new Set([name.toLowerCase(), ...aliases.map((a) => a.toLowerCase())]);
  const tagged: Item[] = [];
  const mentioned: Item[] = [];
  for (const r of lists.resources) {
    if ((r.skills ?? []).some((s) => names.has(s))) tagged.push(r);
    else if ([...names].some((n) => wordRe(n).test(textOf(r).toLowerCase()))) mentioned.push(r);
  }
  return [...tagged, ...mentioned];
}

/** Report a listing that looks fake: a prefilled GitHub issue, or a private email to support. */
export function reportLinks(kind: ListName, it: Item): { issue: string; email: string } {
  const what = { jobs: 'job', funding: 'funding call', conferences: 'conference', resources: 'resource' }[kind];
  const title = `Looks fake: ${it.title}`.slice(0, 110);
  const body = `This ${what} on myGeeKy looks fake or is no longer real.\n\n- id: \`${it.id}\`\n- link: ${it.url}\n\nWhy I think so: \n`
    + '\n---\n<sub>Sent from the 🚩 in the myGeeKy phone app</sub>';
  const q = new URLSearchParams({ title: `🚩 ${title}`, body, labels: 'report' });
  return {
    issue: `https://github.com/mygeeky/myGeeKy-ideas/issues/new?${q.toString()}`,
    email: `mailto:${REPORT_EMAIL}?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`,
  };
}
