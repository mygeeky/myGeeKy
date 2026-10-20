// Circle → 📄 Researchers: people who publish, not only people on GitHub -- a port of the desktop's researchers.py.
// Follow anyone by name (whois.ts's search, the "is this the right one?" check); suggestions from what's already read
// (who cites you, who leads your field's rising papers: no request); their new work, preprints first, from ONE batched
// OpenAlex search for everyone due (author.id:A1|A2|…, through WISEP), each person checked about as often as they
// publish. A preprint and its published version show as one ("now published in …"). The list stays on this phone.
// tests/test_researchers.py checks both apps agree.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { search as whoisSearch, type Found } from './whois';
import { wiseFetch } from './wisep';

const KEY = 'mygeeky.researchers';
const OPENALEX = 'https://api.openalex.org';
const BATCH = 50, KEEP_DAYS = 400, LOOK_BACK_DAYS = 120, MAX_FOLLOWING = 200, MAX_WORKS = 400;
const AID = /^A\d{4,}$/, WID = /^W\d{4,}$/;
const PREPRINT_SERVERS = ['arxiv', 'biorxiv', 'medrxiv', 'chemrxiv', 'ssrn', 'research square', 'preprints.org', 'osf', 'zenodo', 'authorea',
  'psyarxiv', 'socarxiv', 'eartharxiv', 'techrxiv', 'sciety'];

export type Person = { id: string; name: string; institution: string; country: string; topics: string[]; added: string; checked: string; rate: number };
export type Work = { id: string; title: string; date: string; venue: string; preprint: boolean; url: string; doi: string; by: string[]; authors: number;
  seen?: string; preprint_of?: { venue: string; date: string; id: string }; published_as?: string };
export type State = { following: Person[]; works: Record<string, Work>; seen: string[]; updated_at?: string };

// --------------------------------------------------------------------------- the rules (the desktop has the same)
export const intervalDays = (perMonth: number) => (perMonth >= 2 ? 1 : perMonth >= 0.5 ? 3 : 7);
const days = (a: string, b: string) => Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a.slice(0, 10)}T00:00:00Z`)) / 86400000);

export function rateOf(dates: string[], today: string): number {
  const n = dates.filter((d) => d && days(d, today) >= 0 && days(d, today) <= 365).length;
  return Math.round((n / 12) * 1000) / 1000;
}

export const isDue = (p: Person, today: string) => !p.checked || days(p.checked, today) >= intervalDays(p.rate || 0);

export function since(today: string): string {
  const d = new Date(Date.parse(`${today}T00:00:00Z`) - LOOK_BACK_DAYS * 86400000);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-01`;
}

export const worksUrl = (ids: string[], today: string) => `${OPENALEX}/works?filter=author.id:${[...ids].sort().join('|')},from_publication_date:${since(today)}`
  + '&sort=publication_date:desc&per-page=100&select=id,doi,title,publication_date,type,primary_location,authorships';

const normTitle = (t: string) => (t || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

export function isPreprint(w: any): boolean {
  if (String(w?.type ?? '') === 'preprint') return true;
  const src = w?.primary_location && typeof w.primary_location === 'object' ? (w.primary_location.source ?? {}) : {};
  const name = String(src?.display_name ?? '').toLowerCase();
  return src?.type === 'repository' && PREPRINT_SERVERS.some((s) => name.includes(s));
}

export function parseWorks(data: any, following: string[]): Work[] {
  const mine = new Set(following), out: Work[] = [];
  for (const w of Array.isArray(data?.results) ? data.results : []) {
    if (!w || typeof w !== 'object') continue;
    const wid = String(w.id ?? '').split('/').pop() ?? '';
    const title = String(w.title ?? '').split(/\s+/).filter(Boolean).join(' ').slice(0, 300);
    const day = String(w.publication_date ?? '').slice(0, 10);
    if (!WID.test(wid) || !title || !/^\d{4}-\d{2}-\d{2}$/.test(day)) continue;
    const by: string[] = [];
    for (const a of Array.isArray(w.authorships) ? w.authorships : []) {
      const aid = String(a?.author?.id ?? '').split('/').pop() ?? '';
      if (mine.has(aid) && !by.includes(aid)) by.push(aid);
    }
    if (!by.length) continue;
    const loc = w.primary_location && typeof w.primary_location === 'object' ? w.primary_location : {};
    const src = loc.source ?? {};
    const doi = String(w.doi ?? '').replace('https://doi.org/', '').slice(0, 200);
    const url = doi ? `https://doi.org/${doi}` : String(loc.landing_page_url ?? `https://openalex.org/${wid}`);
    out.push({ id: wid, title, date: day, venue: String(src.display_name ?? '').slice(0, 120), preprint: isPreprint(w),
      url: url.startsWith('https://') ? url : `https://openalex.org/${wid}`, doi, by, authors: Array.isArray(w.authorships) ? w.authorships.length : 0 });
  }
  return out;
}

const byDateId = (a: Work, b: Work) => (a.date < b.date ? 1 : a.date > b.date ? -1 : a.id < b.id ? 1 : a.id > b.id ? -1 : 0);

export function mergeWorks(kept: Record<string, Work>, found: Work[], today: string, firstSeen: string): Record<string, Work> {
  let works: Record<string, Work> = Object.fromEntries(Object.entries(kept).map(([k, v]) => [k, { ...v }]));
  for (const w of found) works[w.id] = { ...w, seen: works[w.id]?.seen || firstSeen };
  works = Object.fromEntries(Object.entries(works).filter(([, v]) => days(v.date, today) <= KEEP_DAYS));
  const byTitle: Record<string, Work[]> = {};
  for (const w of Object.values(works)) {
    delete w.preprint_of;
    delete w.published_as;
    (byTitle[normTitle(w.title)] ??= []).push(w);
  }
  const asc = (a: Work, b: Work) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0);
  for (const group of Object.values(byTitle)) {
    const pre = group.filter((w) => w.preprint).sort(asc), pub = group.filter((w) => !w.preprint).sort(asc);
    if (pre.length && pub.length && pre[0].by.some((a) => pub[pub.length - 1].by.includes(a))) {
      pub[pub.length - 1].preprint_of = { venue: pre[0].venue, date: pre[0].date, id: pre[0].id };
      pre[0].published_as = pub[pub.length - 1].id;
    }
  }
  const keep = Object.values(works).sort(byDateId).slice(0, MAX_WORKS);
  return Object.fromEntries(keep.map((w) => [w.id, w]));
}

export type FeedItem = Work & { names: string[]; new: boolean };
export function feed(state: State, today: string): FeedItem[] {
  void today;
  const names = Object.fromEntries((state.following ?? []).map((p) => [p.id, p.name]));
  const seen = new Set(state.seen ?? []);
  return Object.values(state.works ?? {}).sort(byDateId).filter((w) => !w.published_as)
    .map((w) => ({ ...w, names: w.by.filter((a) => a in names).map((a) => names[a]), new: !seen.has(w.id) }));
}

/** Who leads the papers rising in your field (the desktop's papers.people_behind): first and last authors, counted. */
export function fieldPeople(papers: { leads?: { name: string; openalex: string }[] }[]): { openalex: string; name: string; papers: number }[] {
  const by: Record<string, { openalex: string; name: string; papers: number }> = {};
  for (const p of papers) for (const a of p.leads ?? []) {
    if (!AID.test(a.openalex)) continue;
    (by[a.openalex] ??= { openalex: a.openalex, name: a.name, papers: 0 }).papers++;
  }
  return Object.values(by).sort((a, b) => b.papers - a.papers || (a.name < b.name ? -1 : 1)).slice(0, 8);
}

export type Suggestion = { id: string; name: string; institution: string; why: string; score: number };
export function suggestions(citedPeople: any[], fieldPeople: any[], following: string[], me = ''): Suggestion[] {
  const skip = new Set([...following, me]);
  const out: Record<string, Suggestion> = {};
  for (const p of citedPeople) {
    const aid = String(p?.id ?? '').split('/').pop() ?? '';
    if (AID.test(aid) && !skip.has(aid)) {
      const n = Math.trunc(Number(p.count) || 0);
      out[aid] = { id: aid, name: String(p.name ?? ''), institution: String(p.institution ?? ''), why: `cites your work (${n}×)`, score: 2 + n };
    }
  }
  for (const p of fieldPeople) {
    const aid = String(p?.openalex ?? '').split('/').pop() ?? '';
    if (!AID.test(aid) || skip.has(aid)) continue;
    const n = Math.trunc(Number(p.papers) || 0);
    const why = n > 1 ? `leads ${n} of the papers rising in your field` : 'leads a paper rising in your field';
    if (out[aid]) { out[aid].why += `; ${why}`; out[aid].score += 1 + n; }
    else out[aid] = { id: aid, name: String(p.name ?? ''), institution: '', why, score: 1 + n };
  }
  return Object.values(out).sort((a, b) => b.score - a.score || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0)).slice(0, 20);
}

// --------------------------------------------------------------------------- the state
export async function load(): Promise<State> {
  try {
    const d = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '{}');
    return { following: Array.isArray(d.following) ? d.following : [], works: d.works && typeof d.works === 'object' ? d.works : {},
      seen: Array.isArray(d.seen) ? d.seen : [], updated_at: d.updated_at };
  } catch {
    return { following: [], works: {}, seen: [] };
  }
}
const save = (s: State) => AsyncStorage.setItem(KEY, JSON.stringify(s)).catch(() => undefined);

export async function follow(p: { id: string; name: string; institution?: string; country?: string; topics?: string[] }, today = new Date().toISOString().slice(0, 10)): Promise<State> {
  const s = await load();
  if (!AID.test(p.id) || s.following.some((x) => x.id === p.id)) return s;
  s.following = [...s.following, { id: p.id, name: String(p.name ?? '').slice(0, 120), institution: String(p.institution ?? '').slice(0, 160),
    country: String(p.country ?? '').slice(0, 2), topics: (p.topics ?? []).slice(0, 3).map((t) => String(t).slice(0, 80)), added: today, checked: '', rate: 0 }].slice(-MAX_FOLLOWING);
  await save(s);
  return s;
}

export async function unfollow(id: string): Promise<State> {
  const s = await load();
  s.following = s.following.filter((p) => p.id !== id);
  s.works = Object.fromEntries(Object.entries(s.works).map(([k, w]) => [k, { ...w, by: w.by.filter((a) => a !== id) }] as [string, Work]).filter(([, w]) => w.by.length));
  await save(s);
  return s;
}

export async function markSeen(ids: string[]): Promise<void> {
  const s = await load();
  for (const i of ids) if (!s.seen.includes(i)) s.seen.push(i);
  s.seen = s.seen.slice(-MAX_WORKS * 2);
  await save(s);
}

/** Look for new work by everyone due: one batched search per 50 people, through WISEP. */
export async function refresh(force = false, today = new Date().toISOString().slice(0, 10)): Promise<{ ok: boolean; busy: boolean; state: State }> {
  const s = await load();
  const due = s.following.filter((p) => force || isDue(p, today));
  if (!due.length) return { ok: true, busy: false, state: s };
  let busy = false;
  for (let i = 0; i < due.length; i += BATCH) {
    const chunk = due.slice(i, i + BATCH);
    try {
      const r = await wiseFetch(worksUrl(chunk.map((p) => p.id), today), { page: 'circle:researchers', force });
      if (r.status !== 200) { busy = true; break; }
      s.works = mergeWorks(s.works, parseWorks(await r.json(), s.following.map((p) => p.id)), today, today);
      for (const p of chunk) {
        const mine = s.following.find((x) => x.id === p.id)!;
        mine.checked = today;
        mine.rate = rateOf(Object.values(s.works).filter((w) => w.by.includes(p.id)).map((w) => w.date), today);
      }
    } catch { busy = true; break; }
  }
  s.updated_at = new Date().toISOString();
  await save(s);
  return { ok: !busy, busy, state: s };
}

/** Find someone to follow by name (whois.ts's search, through WISEP). */
export const search = (name: string): Promise<Found> => whoisSearch(name, '', 'circle:researchers');
