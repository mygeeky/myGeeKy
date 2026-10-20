// Your wins: new stars and forks on your repos, new citations of your papers -- a
// port of the desktop's wins.py. Once a day the phone reads the two public counts
// (GitHub, OpenAlex via your ORCID) and compares them with the last ones. The first
// read only sets the starting point. Your repos and paper titles are kept too: Rising
// Skills and Learning paths read them to see what you already work with.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { gh } from './github';
import { wiseFetch } from './wisep';

const KEY = 'mygeeky.wins';
const REFRESH_HOURS = 20;
const KEEP_DAYS = 60;
const STAR_STEPS = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000];

export type MyRepo = { name: string; url: string; description: string; topics: string[]; language: string; stars: number; forks: number };
export type Paper = { title: string; cited: number; url: string };
export type Win = { kind: 'stars' | 'forks' | 'citations'; id: string; text: string; url: string; at: string; work?: string;
  citing?: { title: string; by: string; url: string } | null };
export type WinsState = { updatedAt?: string; repos?: Record<string, { stars: number; forks: number }>;
  papers?: Record<string, { cited: number }>; wins: Win[]; myRepos: MyRepo[]; myPapers: string[] };

export async function loadWins(): Promise<WinsState> {
  try {
    const raw = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '{}');
    return { wins: [], myRepos: [], myPapers: [], ...raw };
  } catch {
    return { wins: [], myRepos: [], myPapers: [] };
  }
}

const crossed = (before: number, after: number) => STAR_STEPS.filter((s) => before < s && s <= after).pop() ?? null;
const short = (name: string) => name.split('/').pop() ?? name;

/** New wins between the last counts and now (none on the first read). */
export function diff(old: WinsState, repos: MyRepo[], papers: Record<string, Paper>, when: string): Win[] {
  const out: Win[] = [];
  if (old.repos) {
    for (const r of repos) {
      const b = old.repos[r.name];
      if (!b) continue;
      const stars = r.stars - b.stars;
      const forks = r.forks - b.forks;
      if (stars > 0) {
        const step = crossed(b.stars, r.stars);
        out.push({ kind: 'stars', id: `stars:${r.name}:${r.stars}`, url: `${r.url}/stargazers`, at: when,
          text: step && step >= 10 ? `${short(r.name)} reached ${step} ⭐` : `${short(r.name)} got ${stars} new ⭐` });
      }
      if (forks > 0) {
        out.push({ kind: 'forks', id: `forks:${r.name}:${r.forks}`, url: `${r.url}/forks`, at: when,
          text: `${forks} new fork${forks > 1 ? 's' : ''} of ${short(r.name)}` });
      }
    }
  }
  if (old.papers) {
    for (const [wid, p] of Object.entries(papers)) {
      const b = old.papers[wid];
      if (!b) continue;
      const gained = p.cited - b.cited;
      if (gained > 0) {
        out.push({ kind: 'citations', id: `cited:${wid}:${p.cited}`, work: wid, url: p.url, at: when,
          text: `“${p.title.slice(0, 90)}” was cited ${gained} more time${gained > 1 ? 's' : ''}` });
      }
    }
  }
  return out;
}

async function openalex(path: string): Promise<any> {
  const r = await wiseFetch(`https://api.openalex.org${path}`, { page: 'grow:wins' });
  if (!r.ok) throw new Error(`OpenAlex ${r.status}`);
  return r.json();
}

/** `who`: your ORCID iD, or the OpenAlex author id you confirmed ("Is this you?", whois.ts). */
async function readPapers(who: string): Promise<Record<string, Paper>> {
  const path = /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(who) ? `orcid:${who}` : /^A\d{2,12}$/.test(who) ? who : '';
  if (!path) return {};
  const author = await openalex(`/authors/${path}?select=id`);
  const aid = String(author?.id ?? '').split('/').pop() ?? '';
  if (!/^A\d+$/.test(aid)) return {};
  const data = await openalex(`/works?filter=author.id:${aid}&per-page=200&select=id,title,cited_by_count,doi`);
  const out: Record<string, Paper> = {};
  for (const w of data?.results ?? []) {
    const wid = String(w.id ?? '').split('/').pop() ?? '';
    if (/^W\d+$/.test(wid) && w.title) {
      out[wid] = { title: String(w.title).split(/\s+/).join(' ').slice(0, 200), cited: Number(w.cited_by_count) || 0,
        url: String(w.doi ?? `https://openalex.org/${wid}`) };
    }
  }
  return out;
}

async function newestCiting(wid: string): Promise<Win['citing']> {
  const d = await openalex(`/works?filter=cites:${wid}&sort=publication_date:desc&per-page=1&select=id,title,doi,authorships`);
  const w = d?.results?.[0];
  if (!w) return null;
  const names = (w.authorships ?? []).map((a: any) => String(a?.author?.display_name ?? '')).filter(Boolean);
  return { title: String(w.title ?? '').slice(0, 200), by: names.length ? names[0] + (names.length > 1 ? ' et al.' : '') : '',
    url: String(w.doi ?? '') || `https://openalex.org/${String(w.id ?? '').split('/').pop()}` };
}

export const winsDue = (s: WinsState) => !s.updatedAt || Date.now() - Date.parse(s.updatedAt) > REFRESH_HOURS * 3600000;

/** Read the counts (when due, or forced) and keep what changed. */
export async function refreshWins(user: string, orcid: string, token: string | null, force = false): Promise<WinsState> {
  const state = await loadWins();
  if (!force && !winsDue(state)) return state;
  const when = new Date().toISOString();
  let repos: MyRepo[] | null = null;
  if (user) {
    try {
      const raw = await gh<any[]>(`/users/${encodeURIComponent(user)}/repos?per_page=100&type=owner&sort=pushed`, token);
      repos = raw.filter((r) => !r.fork && r.full_name).map((r) => ({
        name: String(r.full_name), url: `https://github.com/${r.full_name}`, description: String(r.description ?? '').slice(0, 300),
        topics: (r.topics ?? []).slice(0, 20), language: String(r.language ?? ''), stars: Number(r.stargazers_count) || 0,
        forks: Number(r.forks_count) || 0 }));
    } catch {
      repos = null;
    }
  }
  let papers: Record<string, Paper> | null = null;
  try {
    papers = await readPapers(orcid);
  } catch {
    papers = null;
  }
  const fresh = diff(state, repos ?? [], papers ?? {}, when);
  for (const w of fresh) {
    if (w.kind === 'citations' && w.work) w.citing = await newestCiting(w.work).catch(() => null);
  }
  const cutoff = Date.now() - KEEP_DAYS * 86400000;
  const kept = state.wins.filter((w) => Date.parse(w.at) >= cutoff);
  const seen = new Set(kept.map((w) => w.id));
  const next: WinsState = {
    updatedAt: when,
    repos: repos ? Object.fromEntries(repos.map((r) => [r.name, { stars: r.stars, forks: r.forks }])) : state.repos,
    papers: papers && Object.keys(papers).length ? Object.fromEntries(Object.entries(papers).map(([k, v]) => [k, { cited: v.cited }]))
      : state.papers,
    wins: [...fresh.filter((w) => !seen.has(w.id)), ...kept].slice(0, 200),
    myRepos: repos ?? state.myRepos,
    myPapers: papers ? Object.values(papers).map((p) => p.title).slice(0, 200) : state.myPapers,
  };
  await AsyncStorage.setItem(KEY, JSON.stringify(next));
  return next;
}

export function recent(s: WinsState, days = 30): Win[] {
  const cutoff = Date.now() - days * 86400000;
  return s.wins.filter((w) => Date.parse(w.at) >= cutoff).sort((a, b) => b.at.localeCompare(a.at));
}
