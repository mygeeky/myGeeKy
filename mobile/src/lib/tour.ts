// GeeKOc's tours and Help (the desktop's tour.py): which tour to show, when, and what each stop says. The data is
// an identical copy of the desktop's (data/tour.json). A stop opens a page (its "at" for the phone: a place in the
// navigation, "you:accounts" for Settings, a Settings section like "settings:cv", or "help") and GeeKOc says one thing
// about it in the language picked for the tours. The general tour depends on what the user gave -- GitHub, ORCID,
// both, a CV, or none -- and opens by itself the first time, and after an update only for the new stops.
// tests/test_tour.py runs this next to tour.py on the same inputs.
import data from '../data/tour.json';

export type Kind = 'github' | 'orcid' | 'both' | 'cv' | 'none';
type Words = Record<string, string>;
type Stop = { at?: Record<string, string>; pose: string; since?: number; core?: boolean; t?: Words; by_kind?: Record<string, Words>; phrase?: Words };
type Data = { version: number; langs: Words; rtl: string[]; ui: Record<string, Words>; stops: Record<string, Stop>;
  tours: Record<string, string[] | Record<string, string[]>>; faq: { q: Words; a: Words }[] };

const D = data as unknown as Data;
const PLATFORM = 'phone';
const FALLBACK = 'en';
export const MAINS = ['home', 'you', 'grow', 'world', 'circle', 'repos', 'chances'];   // Help has a tour for each
export const LANGS: Words = D.langs;
export const version = (): number => D.version;

/** What the user gave at setup, as one word. ORCID counts for an OpenAlex id found by name too. */
export function kind(github: boolean, orcid: boolean, cv: boolean): Kind {
  if (github && orcid) return 'both';
  if (github) return 'github';
  if (orcid) return 'orcid';
  return cv ? 'cv' : 'none';
}

export const langOf = (lang: string): string => (lang in D.langs ? lang : FALLBACK);
export const rtl = (lang: string): boolean => D.rtl.includes(langOf(lang));
export const pose = (stop: string): string => D.stops[stop].pose;

/** Where a stop takes this app ('' for one that only talks, like the welcome). */
export const at = (stop: string, platform = PLATFORM): string => D.stops[stop].at?.[platform] ?? '';

/** A stop that opens a page exists on an app only if that app has the page. */
export const shownOn = (stop: string, platform = PLATFORM): boolean => !D.stops[stop].at || platform in D.stops[stop].at!;

/** The stops of a tour: 'start' (the general one, by kind), 'settings', or a main ('grow'). */
export function stops(name: string, k: string, platform = PLATFORM): string[] {
  const t = D.tours[name];
  const ids = Array.isArray(t) ? t : t[k in t ? k : 'none'];
  return ids.filter((s) => shownOn(s, platform));
}

export function text(stop: string, lang: string, k = 'none'): string {
  const s = D.stops[stop], l = langOf(lang);
  const words = s.by_kind ? s.by_kind[k] ?? s.by_kind.none : s.t!;
  return words[l] || words[FALLBACK];
}

/** The motto under the last stop's words ('' for the others). */
export function phrase(stop: string, lang: string): string {
  const p = D.stops[stop].phrase;
  return p ? p[langOf(lang)] || p[FALLBACK] : '';
}

export function ui(key: string, lang: string, fill: Record<string, string> = {}): string {
  const words = D.ui[key];
  let out = words[langOf(lang)] || words[FALLBACK];
  for (const [k, v] of Object.entries(fill)) out = out.replace(`{${k}}`, v);
  return out;
}

/** The tour that opens by itself, or []: all of it the first time (seen 0), only the newer stops after an update
 *  that brought some, nothing otherwise. (The phone runs no UI tests, so nothing here needs blocking.) */
export function auto(seen: number, k: string, platform = PLATFORM): string[] {
  if (seen >= D.version) return [];
  const full = stops('start', k, platform);
  if (seen <= 0) return full;
  const fresh = full.filter((x) => (D.stops[x].since ?? 1) > seen && x !== 'welcome' && x !== 'end');
  return fresh.length ? ['welcome_new', ...fresh, 'end'] : [];
}

export function faq(lang: string): [string, string][] {
  const l = langOf(lang);
  return D.faq.map((e) => [e.q[l] || e.q[FALLBACK], e.a[l] || e.a[FALLBACK]]);
}
