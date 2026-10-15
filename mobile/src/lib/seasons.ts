// A season is a scholarship, grant or programme that comes back every year: a port of the desktop's
// seasons.py, kept deliberately close to it so the two cannot drift apart.
//
// 🎯 Chances holds listings that die at their deadline. Seasons are the opposite: MEXT through the
// Japanese Embassy in Cairo does not stop being real when it closes in May -- it returns next April. The
// whole point is that
//
//     the preparing takes longer than the applying.
//
// MEXT wants a research proposal, two recommendation letters, and transcripts certified and apostilled,
// in a three-week window. Getting an apostille is not a three-week job. So "this opens in about ten
// weeks" is worth more than "this is open now".
//
// What a season may NOT do is pretend to know next year's date. Everything else rests on a sentence
// quoted word for word from a page, and next year's call has no page yet. So a season carries the
// occurrences it was actually SEEN to have, each with its quote and link, and the next is offered as an
// expectation -- said as one, never as a fact.
// type-only: seasons.ts must stay free of anything that needs a phone to run, so the date logic can be
// checked on a plain Node run against the same file the desktop uses
import type { Lists } from './curated';

export const LEVELS = ['master', 'phd', 'postdoc', 'undergraduate', 'short'] as const;
export const KINDS = ['scholarship', 'grant', 'fellowship', 'programme'] as const;
export const EVERY: Record<string, number> = { year: 365, '2-years': 730, 'half-year': 182 };
export const LEAST_NOTICE = 15;   // the user's floor: never less than a fortnight's warning
export const MOST_NOTICE = 300;   // beyond this it is not news, it is a calendar
export const TOGETHER = 45;       // programmes opening within this many days belong to one period
const ID_RE = /^[a-z0-9]+(-[a-z0-9]+){1,9}$/;
const MD_RE = /^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export type Seen = { cycle: number; opens: string; closes: string; url: string; quote: string; checked: boolean };
export type Season = {
  id: string; title: string; url: string; org: string; through: string; kind: string; every: string;
  levels: string[]; for: string[]; goes_to: string; opens_about: string; closes_about: string;
  prepare_weeks: number; prepare: string[]; summary: string; keywords: string[]; seen: Seen[];
};
export type State = {
  state: 'open' | 'soon' | 'later' | 'unknown'; opens: string; closes: string;
  days_to_open: number | null; days_to_close: number | null; confirmed: boolean; years: number; notice: number;
};
export type Occurrence = { opens: string; closes: string; confirmed: boolean; quote: string; url: string };
export type Dated = Season & { when: State; occurrence?: Occurrence };
export type Window = {
  id: string; label: string; from: string; to: string; opens_to: string;
  now: boolean; past: boolean; seasons: Dated[];
};

// --------------------------------------------------------------------------- the small readers
const text = (v: unknown, n: number) =>
  (typeof v === 'string' || typeof v === 'number' ? String(v).split(/\s+/).join(' ').trim().slice(0, n) : '');
function https(v: unknown): string {
  const u = String(v ?? '').trim();
  return /^https:\/\/[^\s/]+\.[^\s]*$/.test(u) && !u.includes(' ') ? u.slice(0, 500) : '';
}
function day(v: unknown): string {
  const s = String(v ?? '').slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(`${s}T00:00:00Z`)) ? s : '';
}
const words = (v: unknown, n = 12) => (Array.isArray(v)
  ? [...new Set(v.map((x) => text(x, 40).toLowerCase()).filter(Boolean))].slice(0, n) : []);
const md = (v: unknown) => { const s = text(v, 5); return MD_RE.test(s) ? s : ''; };
function year(v: unknown): number {
  const n = parseInt(String(v ?? '').slice(0, 4), 10);
  return Number.isFinite(n) && n >= 2000 && n <= 2100 ? n : 0;
}
function weeks(v: unknown): number {
  const n = Math.trunc(Number(v));
  return Number.isFinite(n) ? Math.max(1, Math.min(52, n)) : 4;
}
function places(v: unknown): string[] {
  const list = typeof v === 'string' ? [v] : Array.isArray(v) ? v : [];
  const out: string[] = [];
  for (const p of list.slice(0, 40)) {
    const name = text(p, 60);
    if (name && !out.some((x) => x.toLowerCase() === name.toLowerCase())) out.push(name);
  }
  return out;
}

export const iso = (d: Date) => d.toISOString().slice(0, 10);
export const todayIso = () => iso(new Date());
const at = (s: string) => Date.parse(`${s}T00:00:00Z`);
export function daysBetween(a: string, b: string): number | null {
  const [x, y] = [at(a), at(b)];
  return Number.isNaN(x) || Number.isNaN(y) ? null : Math.round((y - x) / 86400000);
}

// --------------------------------------------------------------------------- what a season is
/** The times this season was actually seen open, newest first: the evidence, and the only checked part.
 *  No link or no quoted sentence means hearsay, and hearsay is dropped however plausible it reads. */
export function cleanSeen(raw: any): Seen[] {
  const out: Seen[] = [];
  for (const r of (Array.isArray(raw) ? raw : []).slice(0, 12)) {
    if (!r || typeof r !== 'object') continue;
    const opens = day(r.opens), closes = day(r.closes);
    const url = https(r.url), quote = text(r.quote, 400);
    if (!closes || !url || !quote) continue;
    if (opens && opens > closes) continue;            // opened after it closed: somebody mistyped
    out.push({ cycle: year(r.cycle), opens, closes, url, quote, checked: r.checked === true });
  }
  return out.sort((a, b) => (a.closes < b.closes ? 1 : a.closes > b.closes ? -1 : 0));
}

/** True once one of this season's occurrences has been found on its own page. A season the maker only
 *  wrote down is a claim; one with a checked occurrence has a sentence behind it, and only the second
 *  kind is shown to people. */
export const evidenced = (s: Season) => (s.seen ?? []).some((o) => o.checked);

export function cleanSeason(raw: any): Season | null {
  if (!raw || typeof raw !== 'object' || !ID_RE.test(String(raw.id ?? ''))) return null;
  const kind = String(raw.kind ?? 'scholarship').toLowerCase();
  const every = String(raw.every ?? 'year').toLowerCase();
  const s: Season = {
    id: raw.id,
    title: text(raw.title, 140),
    url: https(raw.url),
    org: text(raw.org, 140),
    through: text(raw.through, 140),              // the embassy or office you actually apply to
    kind: (KINDS as readonly string[]).includes(kind) ? kind : 'scholarship',
    every: every in EVERY ? every : 'year',
    levels: words(raw.levels, 6).filter((v) => (LEVELS as readonly string[]).includes(v)),
    for: places(raw.for),                          // nationalities it is open to; empty means anyone
    goes_to: text(raw.goes_to, 60),
    opens_about: md(raw.opens_about),
    closes_about: md(raw.closes_about),
    prepare_weeks: weeks(raw.prepare_weeks),
    prepare: (Array.isArray(raw.prepare) ? raw.prepare : []).slice(0, 10).map((p: any) => text(p, 90)).filter(Boolean),
    summary: text(raw.summary, 400),
    keywords: words(raw.keywords),
    seen: cleanSeen(raw.seen),
  };
  if (!s.title || !s.url) return null;
  // a season with neither a history nor a stated window cannot say when anything happens
  if (!s.seen.length && !s.closes_about) return null;
  return s;
}

/** Every usable season in a list, with duplicates by id dropped. */
export function clean(raw: any): Season[] {
  const ids = new Set<string>();
  const out: Season[] = [];
  for (const r of (Array.isArray(raw) ? raw : []).slice(0, 300)) {
    const s = cleanSeason(r);
    if (s && !ids.has(s.id)) { ids.add(s.id); out.push(s); }
  }
  return out;
}

// --------------------------------------------------------------------------- when it next comes round
/** [opens month-day, closes month-day, years of evidence] -- what the history says to expect. Worked out
 *  from the occurrences actually seen, because those have a page behind them; the stated window is only
 *  a fallback, for a season found but not yet checked. */
export function pattern(s: Season): [string, string, number] {
  const seen = s.seen ?? [];
  const closes = seen.map((o) => o.closes).filter(Boolean);
  const opens = seen.map((o) => o.opens).filter(Boolean);
  if (closes.length) {
    return [middle(opens) || s.opens_about, middle(closes), new Set(closes.map((c) => c.slice(0, 4))).size];
  }
  return [s.opens_about, s.closes_about, 0];
}

/** The typical month-day of a handful of dates: the middle one, so one odd year cannot drag it. */
function middle(days: string[]): string {
  if (!days.length) return '';
  const sorted = days.map((d) => d.slice(5)).sort();
  return sorted[Math.floor(days.length / 2)];
}

/** A date, stepping back off a 29 February in a year that hasn't got one. */
export function on(y: number, mmdd: string): Date | null {
  if (!MD_RE.test(mmdd || '')) return null;
  const month = parseInt(mmdd.slice(0, 2), 10);
  let dayOf = parseInt(mmdd.slice(3), 10);
  while (dayOf > 28) {
    const d = new Date(Date.UTC(y, month - 1, dayOf));
    if (d.getUTCMonth() === month - 1 && d.getUTCDate() === dayOf) return d;
    dayOf -= 1;
  }
  return new Date(Date.UTC(y, month - 1, dayOf));
}

/** Where this season stands today. `confirmed` is the honest bit: true only while a window myGeeKy
 *  actually read on a page is still running. Every future date is an expectation, and the screens must
 *  say so. */
export function when(s: Season, today = todayIso()): State {
  const [openMd, closeMd, years] = pattern(s);
  const notice = Math.max(LEAST_NOTICE, (s.prepare_weeks ?? 4) * 7);
  const out: State = { state: 'unknown', opens: '', closes: '', days_to_open: null, days_to_close: null,
    confirmed: false, years, notice };
  if (!closeMd) return out;
  // a window myGeeKy actually saw, still running: the one case where nothing is being guessed
  for (const o of s.seen ?? []) {
    const opens = o.opens || o.closes;
    if (opens <= today && today <= o.closes) {
      return { ...out, state: 'open', opens: o.opens, closes: o.closes, confirmed: true,
        days_to_open: 0, days_to_close: daysBetween(today, o.closes) };
    }
  }
  const step = EVERY[s.every] ?? 365;
  const thisYear = Number(today.slice(0, 4));
  let best: [Date, Date] | null = null;
  for (const y of [thisYear - 1, thisYear, thisYear + 1, thisYear + 2]) {
    const closes = on(y, closeMd);
    let opens = openMd ? on(y, openMd) : null;
    if (!closes) continue;
    if (opens && opens > closes) opens = on(y - 1, openMd);      // a window that straddles new year
    if (iso(closes) < today) continue;
    if (opens && iso(opens) <= today && today <= iso(closes)) {  // expected to be open right now
      return { ...out, state: 'open', opens: iso(opens), closes: iso(closes),
        days_to_open: 0, days_to_close: daysBetween(today, iso(closes)) };
    }
    const start = opens ?? closes;
    if (best === null || start < best[0]) best = [start, closes];
  }
  if (best === null) return out;
  const [start, closes] = best;
  const days = daysBetween(today, iso(start)) ?? 0;
  const soon = (step < 365 || days <= MOST_NOTICE) && days <= notice;
  return { ...out, state: soon ? 'soon' : 'later', opens: iso(start), closes: iso(closes),
    days_to_open: days, days_to_close: daysBetween(today, iso(closes)) };
}

// --------------------------------------------------------------------------- what to show, and to whom
/** True if this is open to someone of this nationality. It matters more here than anywhere else: a
 *  postdoc in Lyon is open to all comers, while MEXT-through-Cairo is for Egyptians and noise to everyone
 *  else. A season naming no country is open to anyone, and someone who has not said where they are from
 *  is shown everything. */
export function fits(s: Season, nationality = ''): boolean {
  const who = s.for ?? [];
  const want = nationality.trim().toLowerCase();
  if (!who.length || !want) return true;
  return who.some((p) => { const low = p.toLowerCase(); return want === low || want.includes(low) || low.includes(want); });
}

/** Seasons worth seeing now: open first, then the ones to start preparing for, nearest first -- so the
 *  top of the list is always the thing to do something about today. */
export function ranked(seasons: Season[], today = todayIso(), nationality = '', levels: string[] = []): Dated[] {
  const order: Record<string, number> = { open: 0, soon: 1, later: 2, unknown: 3 };
  const out: Dated[] = [];
  for (const s of seasons) {
    if (!fits(s, nationality)) continue;
    if (levels.length && s.levels.length && !s.levels.some((l) => levels.includes(l))) continue;
    out.push({ ...s, when: when(s, today) });
  }
  return out.sort((a, b) => order[a.when.state] - order[b.when.state]
    || (a.when.days_to_open ?? 9999) - (b.when.days_to_open ?? 9999)
    || a.title.localeCompare(b.title));
}

/** What to say about where a season stands, without ever claiming to know a date it cannot know. */
export function noticeText(st: State): string {
  const days = st.days_to_open;
  if (st.state === 'open' && st.confirmed) {
    return st.days_to_close === null ? 'open now' : `open now · closes in ${st.days_to_close} days`;
  }
  if (st.state === 'open') return 'expected to be open now';
  if (days === null) return 'no dates yet';
  if (days <= 0) return 'expected to open any day';
  if (days <= 31) return `expected to open in about ${days} days`;
  const w = Math.round(days / 7);
  return w <= 12 ? `expected in about ${w} weeks` : `expected in about ${Math.round(days / 30.4)} months`;
}

/** True when it is time to start getting the papers together, rather than time to apply. */
export function prepareNow(s: Season, today = todayIso()): boolean {
  const st = when(s, today);
  if (st.state === 'open') return false;
  return st.days_to_open !== null && st.days_to_open <= st.notice;
}

// --------------------------------------------------------------------------- the periods people step through
/** Every window this season is believed to have had, or to be about to have. One myGeeKy read on a page
 *  comes back `confirmed`; the rest are worked out from the pattern and are expectations, nothing more. */
export function occurrences(s: Season, today = todayIso(), back = 1, ahead = 2): Occurrence[] {
  const [openMd, closeMd] = pattern(s);
  if (!closeMd) return [];
  const known = new Map((s.seen ?? []).filter((o) => o.checked).map((o) => [o.closes, o]));
  const thisYear = Number(today.slice(0, 4));
  const out: Occurrence[] = [];
  for (let y = thisYear - back; y <= thisYear + ahead; y++) {
    const closes = on(y, closeMd);
    let opens = openMd ? on(y, openMd) : null;
    if (!closes) continue;
    if (opens && opens > closes) opens = on(y - 1, openMd);
    const seen = known.get(iso(closes));
    out.push({ opens: iso(opens ?? closes), closes: iso(closes), confirmed: !!seen,
      quote: seen?.quote ?? '', url: seen?.url ?? '' });
  }
  return out.sort((a, b) => (a.opens < b.opens ? -1 : a.opens > b.opens ? 1 : 0));
}

/** How a period is named in the picker: short, and honest about which one we are in. */
export function label(start: Date, end: Date): string {
  const [sm, em] = [start.getUTCMonth(), end.getUTCMonth()];
  const [sy, ey] = [start.getUTCFullYear(), end.getUTCFullYear()];
  if (sy === ey) {
    const span = sm === em ? MONTHS[sm] : em - sm === 1 ? `${MONTHS[sm]}/${MONTHS[em]}` : `${MONTHS[sm]}–${MONTHS[em]}`;
    return `${span} ${sy}`;
  }
  return `${MONTHS[sm]} ${sy} – ${MONTHS[em]} ${ey}`;
}

/** The periods worth stepping through, in time order, each holding what falls in it.
 *
 *  Only periods that actually have something in them: an empty month is not a season, and a picker full
 *  of nothing teaches people the feature is empty. The period we are in is marked `now`, and the one
 *  before it is kept so there is always a step backwards -- a programme that closed last week is the one
 *  most worth seeing, because it says when to be ready next time. */
export function windows(seasons: Season[], today = todayIso(), nationality = '', levels: string[] = [],
                        onlyEvidenced = true): Window[] {
  const rows: [Occurrence, Season][] = [];
  for (const s of seasons) {
    if (!fits(s, nationality)) continue;
    if (levels.length && s.levels.length && !s.levels.some((l) => levels.includes(l))) continue;
    if (onlyEvidenced && !evidenced(s)) continue;
    for (const o of occurrences(s, today)) rows.push([o, s]);
  }
  rows.sort((a, b) => (a[0].opens < b[0].opens ? -1 : a[0].opens > b[0].opens ? 1 : 0));
  const groups: [Occurrence, Season][][] = [];
  for (const row of rows) {
    const last = groups[groups.length - 1];
    const gap = last ? daysBetween(last[last.length - 1][0].opens, row[0].opens) : null;
    if (last && gap !== null && gap <= TOGETHER) last.push(row);
    else groups.push([row]);
  }
  return groups.map((group) => {
    const opensAll = group.map(([o]) => at(o.opens));
    const closesAll = group.map(([o]) => at(o.closes));
    const start = new Date(Math.min(...opensAll));
    const end = new Date(Math.max(...closesAll));
    // named by when things OPEN, which is what groups them and what people act on. Naming it by the whole
    // span would read "Oct 2026 – Feb 2027" next to a "Jan/Feb 2027" that overlaps it.
    const lastOpen = new Date(Math.max(...opensAll));
    return {
      id: `${iso(start)}-${iso(end)}`,
      label: label(start, lastOpen),
      from: iso(start), to: iso(end), opens_to: iso(lastOpen),
      now: iso(start) <= today && today <= iso(end),
      past: iso(end) < today,
      seasons: group.map(([o, s]) => ({ ...s, occurrence: o, when: when(s, today) })),
    };
  });
}

/** Which period the picker should start on: the one we are in, else the next one coming. */
export function current(wins: Window[], today = todayIso()): number {
  const now = wins.findIndex((w) => w.now);
  if (now >= 0) return now;
  const next = wins.findIndex((w) => !w.past);
  return next >= 0 ? next : Math.max(wins.length - 1, 0);
}

/** The periods to offer: the one we are in, one behind, and a few ahead. Not the whole calendar. */
export function around(wins: Window[], today = todayIso(), back = 1, ahead = 3): Window[] {
  if (!wins.length) return [];
  const i = current(wins, today);
  return wins.slice(Math.max(0, i - back), i + ahead + 1);
}

/** The seasons in the lists, read straight off the downloaded file. */
export function seasonsOf(lists: Lists): Season[] {
  return clean((lists as any).seasons);
}
