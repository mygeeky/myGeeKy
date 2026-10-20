// Rising Skills and Learning paths -- a port of the desktop's skills.py. The phone
// counts how often each skill in a small dictionary (data/skills.json, the same file
// the desktop uses) shows up in what it already read about your field (rising papers,
// field repos, models, headlines), compares it with what you show (your keywords, your
// repos, your papers), and suggests what's rising there but missing from you. 👍/👎
// tilt it; 👎 hides a skill (protocols.ts turns one into stages). Growth is measured only where no one picked for
// you -- the explore picks and the shared world file (data/skill_trends.json, skilltrends.py) -- see corrected();
// shapes() makes the four views. tests/test_growth.py checks both apps agree. Nothing here sends anything.
import AsyncStorage from '@react-native-async-storage/async-storage';
import vocab from '../data/skills.json';
import bundledTrends from '../data/skill_trends.json';
import { match, Weights } from './interests';
import { fetchT } from './net';
import { isStale, readCache, writeCache } from './storage';
import * as taste from './taste';
import { loadWins, WinsState } from './wins';

const HISTORY_KEY = 'mygeeky.skills.history';
const RECENT_DAYS = 45;
const MIN_DOCS = 2;
const SURE_Z = 1.28;              // "sure it's rising": the lower edge of an 80% interval on its growth ...
const SURE_ABOVE = 1.1;           // ... is above 1.1x
const MIN_EVIDENCE = 3;           // world mentions needed before its growth counts at all
const LENS_LOW = 0.7, LENS_HIGH = 2.0;
export const TRENDS_URL = 'https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/skill_trends.json';

export const SOURCES: Record<string, [string, string, number]> = {
  paper: ['rising paper', 'rising papers', 1.0],
  tool: ['tool with a paper', 'tools with papers', 1.0],
  repo: ['field repo', 'field repos', 0.8],
  model: ['trending model', 'trending models', 0.6],
  news: ['headline', 'headlines', 0.5],
  users: ['myGeeKy user near you', 'myGeeKy users near you', 0.5],
};
const said = (src: string, n: number) => `in ${n} ${n === 1 ? SOURCES[src][0] : SOURCES[src][1]}`;

export type Skill = { name: string; kind: string; aliases: string[]; re: RegExp };
let VOCAB: Skill[] | null = null;
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function vocabulary(): Skill[] {
  if (!VOCAB) {
    VOCAB = ((vocab as any).skills ?? []).flatMap((s: any) => {
      const aliases = [...new Set<string>((s.aliases ?? []).map((a: string) => a.toLowerCase()).filter((a: string) => a.length >= 3))]
        .sort((a, b) => b.length - a.length);
      if (!s.name || !aliases.length) return [];
      const alt = aliases.map((a) => esc(a).replace(/ /g, '[\\s_-]+').replace(/-/g, '[\\s_-]?')).join('|');
      return [{ name: s.name, kind: s.kind ?? '', aliases, re: new RegExp(`(^|[^a-z0-9])(?:${alt})s?(?![a-z0-9])`, 'i') }];
    });
  }
  return VOCAB as Skill[];
}

export const find = (name: string) => {
  const n = name.trim().toLowerCase();
  return vocabulary().find((s) => s.name.toLowerCase() === n || s.aliases.includes(n)) ?? null;
};

export function skillsIn(text: string): Set<string> {
  const out = new Set<string>();
  if (text) for (const s of vocabulary()) if (s.re.test(text)) out.add(s.name);
  return out;
}

export type Doc = { text: string; when: number | null; source: string; url: string; title: string; pick?: 'mine' | 'wide' };

/** What the phone already read about your field (its cached feeds). */
export async function fieldDocs(): Promise<Doc[]> {
  const docs: Doc[] = [];
  const add = (text: string, when: string | undefined, source: string, url = '', title = '', wide = false) => {
    if (text?.trim()) docs.push({ text: text.slice(0, 3000), when: when ? Date.parse(when) || null : null, source, url, title: title.slice(0, 140),
      pick: wide ? 'wide' : 'mine' });
  };
  const research = await readCache<{ rising: any[]; tools: any[] }>('research');
  for (const [k, src] of [['rising', 'paper'], ['tools', 'tool']] as const) {
    for (const p of research?.data?.[k] ?? []) add(`${p.title} ; ${String(p.abstract ?? '').slice(0, 1500)}`, p.date, src, p.url, p.title);
  }
  const repos = await readCache<any[]>('market-repos');
  for (const r of repos?.data ?? []) {
    add(`${r.full_name} ; ${r.description ?? ''} ; ${(r.topics ?? []).join(' ')} ; ${r.language ?? ''}`, r.pushed_at, 'repo', r.html_url, r.full_name);
  }
  const models = await readCache<{ field: any[] }>('models');
  for (const m of models?.data?.field ?? []) add(`${m.id} ; ${(m.tags ?? []).join(' ')} ; ${m.pipeline}`, undefined, 'model', m.url, m.id);
  const heads = await readCache<{ items: any[] }>('headlines');
  for (const h of heads?.data?.items ?? []) {       // yours, or picked to widen it
    if (h.match?.length || h.explore === true) add(h.title, h.published, 'news', h.link, h.title, h.explore === true);
  }
  return docs;
}

export function ownText(keywords: string[], interests: string[], w: WinsState): string {
  return [keywords.join(' ; '), interests.join(' ; '), ...w.myRepos.map((r) => `${r.name} ; ${r.description} ; ${r.topics.join(' ')} ; ${r.language}`),
    ...w.myPapers].join('\n');
}

export type Rising = { name: string; kind: string; score: number; growth: number; mentions: number; reasons: string[];
  examples: { title: string; url: string }[]; vote: number; rising: boolean; lo: number | null; hi: number | null;
  world: number; mine: number; self_made: boolean; beyond: boolean };
export type Link = [string, string, number];

// --------------------------------------------------------------------------- the world file (skilltrends.py)
export type Trends = { version: string; docs: number[]; skills: Record<string, number[]>; pairs: Record<string, number> };   // [older, newer, a year ago]
const int = (x: unknown) => (typeof x === 'number' && Number.isFinite(x) && x >= 0 && x < 1e8 ? Math.trunc(x) : 0);

export function cleanTrends(data: any): Trends {
  data = data && typeof data === 'object' && !Array.isArray(data) ? data : {};
  const known = new Set(vocabulary().map((s) => s.name));
  const docs = Array.isArray(data.docs) && (data.docs.length === 2 || data.docs.length === 3) ? data.docs : [0, 0];
  const skills: Record<string, number[]> = {};
  const raw = data.skills && typeof data.skills === 'object' && !Array.isArray(data.skills) ? data.skills : {};
  for (const [name, pair] of Object.entries(raw)) {
    if (known.has(name) && Array.isArray(pair) && (pair.length === 2 || pair.length === 3)) {   // an older file has no year-ago count
      skills[name] = [int(pair[0]), int(pair[1]), pair.length === 3 && docs.length === 3 ? int(pair[2]) : 0];
    }
  }
  const pairs: Record<string, number> = {};
  const rawPairs = data.pairs && typeof data.pairs === 'object' && !Array.isArray(data.pairs) ? data.pairs : {};
  for (const [key, k] of Object.entries(rawPairs).slice(0, 20000)) {
    const at = key.indexOf('|'), a = at < 0 ? key : key.slice(0, at), b = at < 0 ? '' : key.slice(at + 1);
    if (known.has(a) && known.has(b) && a < b && int(k)) pairs[`${a}|${b}`] = int(k);
  }
  const version = String(data.version ?? '');
  return { version: version.length === 10 && version[4] === '-' ? version : '', docs: [int(docs[0]), int(docs[1]), docs.length === 3 ? int(docs[2]) : 0], skills, pairs };
}

/** The newest world file: the copy in the app, or a newer one fetched from GitHub (at most once a day). */
export async function loadTrends(): Promise<Trends> {
  const shipped = cleanTrends(bundledTrends);
  const cached = await readCache<Trends>('skill-trends');
  let best = cached?.data ? cleanTrends(cached.data) : shipped;
  if (!best.docs[1] || best.version < shipped.version) best = shipped;
  if (isStale(cached?.at, 24)) {
    try {
      const r = await fetchT(TRENDS_URL);
      if (r.ok) {
        const fresh = cleanTrends(await r.json());
        await writeCache('skill-trends', fresh);
        if (fresh.docs[1] && fresh.version >= best.version) best = fresh;
      }
    } catch { /* offline: what we have */ }
  }
  return best;
}

// --------------------------------------------------------------------------- is it really rising? (skills.corrected)
const round = (x: number, places = 4) => Math.round(x * 10 ** places) / 10 ** places;
export type Corrected = { growth: number | null; lo: number; hi: number; sure: boolean; mine: number; world: number; lens: number;
  self_made: boolean; beyond: boolean };

export function corrected(docs: { skills: Iterable<string>; pick: string; recent: boolean }[], trends: Trends,
  feedGrowth: Record<string, number>): Record<string, Corrected> {
  const n = { old: trends.docs[0], new: trends.docs[1], mine: 0 };
  const old: Record<string, number> = {}, nw: Record<string, number> = {}, mine: Record<string, number> = {};
  for (const [name, [o, r]] of Object.entries(trends.skills)) {
    old[name] = (old[name] ?? 0) + o;
    nw[name] = (nw[name] ?? 0) + r;
  }
  for (const d of docs) {
    if (d.pick === 'wide') {
      const side = d.recent ? nw : old;
      if (d.recent) n.new++; else n.old++;
      for (const s of d.skills) side[s] = (side[s] ?? 0) + 1;
    } else {
      n.mine++;
      for (const s of d.skills) mine[s] = (mine[s] ?? 0) + 1;
    }
  }
  const out: Record<string, Corrected> = {};
  const worldN = n.old + n.new;
  const names = [...new Set([...Object.keys(old), ...Object.keys(nw), ...Object.keys(mine)])].sort();
  for (const s of names) {
    const o = old[s] ?? 0, r = nw[s] ?? 0;
    const lg = Math.log(((r + 0.5) / (n.new + 1)) / ((o + 0.5) / (n.old + 1)));
    const se = Math.sqrt(1 / (r + 0.5) + 1 / (o + 0.5));
    const world = worldN ? (o + r) / worldN : 0;
    const yours = n.mine ? (mine[s] ?? 0) / n.mine : 0;
    const lens = n.mine ? yours / Math.max(world, 0.5 / (worldN + 1)) : 1;
    const evidence = o + r >= MIN_EVIDENCE;
    const sure = evidence && lg - SURE_Z * se > Math.log(SURE_ABOVE);
    out[s] = { growth: evidence ? round(Math.exp(lg), 2) : null, lo: round(Math.exp(lg - SURE_Z * se), 2), hi: round(Math.exp(lg + SURE_Z * se), 2),
      sure, mine: round(yours), world: round(world), lens: round(lens, 2),
      self_made: !sure && (feedGrowth[s] ?? 1) >= 1.3 && lens >= LENS_HIGH, beyond: sure && lens < LENS_LOW };
  }
  return out;
}

// --------------------------------------------------------------------------- directions (skills.directions)
const DIRECTIONS = 5;
const DIRECTION_BONUS = 1.3;
const GROWTH_CAP = 5;
export type Direction = { name: string; kind: string; growth: number; lo: number; hi: number; since: 'year' | 'weeks'; mentions: number; with: string[];
  together: number; via: string; score: number };

/** Where the field is going and how it touches you: skills rising for sure across new preprints that you don't have,
 *  tied to yours by preprints mentioning both, or through one skill that is. `skip`: already suggested or hidden. */
export function directions(world: Record<string, Corrected>, trends: Trends, have: Set<string>, skip: Set<string>,
  kinds: Record<string, string>, top = DIRECTIONS): Direction[] {
  const near: Record<string, Record<string, number>> = {};
  for (const [key, k] of Object.entries(trends.pairs ?? {})) {
    const at = key.indexOf('|'), a = key.slice(0, at), b = key.slice(at + 1);
    (near[a] ??= {})[b] = k;
    (near[b] ??= {})[a] = k;
  }
  const yoursOf = (n: string) => Object.entries(near[n] ?? {}).filter(([h]) => have.has(h)).sort((x, y) => y[1] - x[1] || cmp(x[0], y[0]));
  const rows: Direction[] = [];
  for (const [s, c] of Object.entries(world)) {
    if (have.has(s) || skip.has(s)) continue;
    const o = trends.skills[s]?.[0] ?? 0, r = trends.skills[s]?.[1] ?? 0, y = trends.skills[s]?.[2] ?? 0, docs = trends.docs;
    const mentions = o + r;
    let year: [number, number, number] | null = null;
    if ((docs[2] ?? 0) && r + y >= MIN_EVIDENCE) {
      const lg = Math.log(((r + 0.5) / (docs[1] + 1)) / ((y + 0.5) / (docs[2] + 1)));
      const se = Math.sqrt(1 / (r + 0.5) + 1 / (y + 0.5));
      if (lg - SURE_Z * se > Math.log(SURE_ABOVE)) year = [round(Math.exp(lg), 2), round(Math.exp(lg - SURE_Z * se), 2), round(Math.exp(lg + SURE_Z * se), 2)];
    }
    if (!mentions || !(year || (c.sure && c.growth != null))) continue;
    const [growth, lo, hi] = year ?? [c.growth as number, c.lo, c.hi];
    let mine = yoursOf(s), via = '';
    let together = mine.reduce((a, [, k]) => a + k, 0), tie = together / mentions;
    if (!mine.length) {                               // one step further: a skill seen with it, and with yours
      let best: [number, string, [string, number][]] | null = null;
      for (const [n, k] of Object.entries(near[s] ?? {})) {
        const yours = yoursOf(n);
        if (have.has(n) || !yours.length) continue;
        const step = Math.min(k, yours.reduce((a, [, j]) => a + j, 0));
        if (!best || step > best[0] || (step === best[0] && n > best[1])) best = [step, n, yours];
      }
      if (!best) continue;
      [together, via, mine] = best;
      tie = (0.5 * together) / mentions;
    }
    const score = Math.log1p(mentions) * Math.min(growth, GROWTH_CAP) * (0.25 + 0.75 * Math.sqrt(Math.min(tie, 1)))
      * (kinds[s] === 'direction' ? DIRECTION_BONUS : 1);
    rows.push({ name: s, kind: kinds[s] ?? '', growth, lo, hi, since: year ? 'year' : 'weeks', mentions, with: mine.slice(0, 2).map(([h]) => h),
      together, via, score: round(score) });
  }
  return rows.sort((a, b) => b.score - a.score || cmp(a.name, b.name)).slice(0, top);
}

/** Why a direction is shown (skills.direction_line: the same words on the computer). */
export function directionLine(d: Direction): string {
  const w = d.with.join(' and ');
  const grew = `×${d.growth} in new preprints ${d.since === 'year' ? 'since a year ago' : 'over the last 45 days'}`;
  if (d.via) return `${grew}; close to ${d.via}, which appears with your ${w}`;
  return `${grew}; appears with your ${w} in ${d.together} of them`;
}

/** One line on whether a skill is really rising, under its card (skills.note: the same words on the computer). */
export function note(s: Rising): string {
  const g = s.growth;
  if (s.beyond) return `🌍 Rising beyond your usual: ×${g} in new preprints across the field, rare in your feed`;
  if (s.rising) return `📈 Sure it's rising: ×${g} in new preprints across the field (×${s.lo} to ×${s.hi})`;
  if (s.self_made) return '🪞 Busy in your feed only: it follows what you chose to read, not the field';
  return '';
}

export type LensRow = { name: string; mine: number; world: number; yours: boolean };
export type Shapes = {
  directions: (Direction & { line: string })[];
  next: { name: string; via: string; more: number; weight: number; sure: boolean; beyond: boolean }[];
  flow: { left: string[]; right: string[]; bands: Link[] };
  ladder: { left: string[]; right: string[]; links: Link[] };
  lens: { mine: LensRow[]; world: LensRow[] };
};
const ratio = (r: LensRow) => (r.mine + 0.002) / (r.world + 0.002);
const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

/** The four views (skills.shapes): next steps, flow, ladder and your lens. */
export function shapes(result: { skills: Rising[]; strengths: Rising[]; links: Link[]; directions?: Direction[] }): Shapes {
  const sug = result.skills, strong = result.strengths, links = result.links;
  const names = sug.map((s) => s.name);
  const next = sug.slice(0, 6).map((s) => {
    const ls = links.filter((l) => l[1] === s.name);
    return { name: s.name, via: ls[0]?.[0] ?? '', more: Math.max(0, ls.length - 1), weight: ls.reduce((a, l) => a + l[2], 0),
      sure: !!s.rising, beyond: !!s.beyond };
  });
  const total: Record<string, number> = {};
  for (const [h, s, k] of links) if (names.slice(0, 8).includes(s)) total[h] = (total[h] ?? 0) + k;
  const left = Object.entries(total).sort((a, b) => b[1] - a[1] || cmp(a[0], b[0])).slice(0, 6).map(([h]) => h);
  const right = names.filter((s) => links.some((l) => l[1] === s && left.includes(l[0]))).slice(0, 7);
  const lLeft = strong.slice(0, 7).map((s) => s.name), lRight = names.slice(0, 10);
  const rows: LensRow[] = [...strong, ...sug].map((s, i) => ({ name: s.name, mine: s.mine ?? 0, world: s.world ?? 0, yours: i < strong.length }))
    .filter((r) => r.mine + r.world > 0);
  return {
    directions: (result.directions ?? []).map((d) => ({ ...d, line: directionLine(d) })),
    next,
    flow: { left, right, bands: links.filter((l) => left.includes(l[0]) && right.includes(l[1])) },
    ladder: { left: lLeft, right: lRight, links: links.filter((l) => lLeft.includes(l[0]) && lRight.includes(l[1])) },
    lens: {
      mine: rows.filter((r) => r.mine > r.world).sort((a, b) => ratio(b) - ratio(a) || cmp(a.name, b.name)).slice(0, 5),
      world: rows.filter((r) => r.world > r.mine).sort((a, b) => ratio(a) - ratio(b) || cmp(a.name, b.name)).slice(0, 5),
    },
  };
}

async function history(): Promise<Record<string, Record<string, number>>> {
  try {
    return JSON.parse((await AsyncStorage.getItem(HISTORY_KEY)) ?? '{}') ?? {};
  } catch {
    return {};
  }
}

export type RisingResult = { skills: Rising[]; strengths: Rising[]; hidden: number; links: Link[]; directions: Direction[] };

export async function rising(opts: { docs: Doc[]; mine: string; weights: Weights; github: boolean; top?: number; save?: boolean;
  trends?: Trends }): Promise<RisingResult> {
  const { docs, mine, weights } = opts;
  const now = Date.now();
  const have = skillsIn(mine);
  if (opts.github) have.add('Git');
  const votes = await taste.load();
  const leanW = taste.weights(votes, ['skill', 'resource']);
  const recent: Record<string, number> = {};
  const older: Record<string, number> = {};
  const close: Record<string, number> = {};
  const hits: Record<string, number> = {};
  const bySrc: Record<string, Record<string, number>> = {};
  const examples: Record<string, { title: string; url: string }[]> = {};
  const seen: { skills: Set<string>; pick: string; recent: boolean }[] = [];
  const pairs = new Map<string, number>();
  for (const d of docs) {
    const found = skillsIn(d.text);
    const age = d.when ? (now - d.when) / 86400000 : null;
    seen.push({ skills: found, pick: d.pick ?? 'mine', recent: age === null || age <= RECENT_DAYS });
    if (!found.size) continue;
    for (const h of found) {
      if (!have.has(h)) continue;
      for (const s of found) if (!have.has(s)) pairs.set(`${h}\n${s}`, (pairs.get(`${h}\n${s}`) ?? 0) + 1);
    }
    const w = SOURCES[d.source]?.[2] ?? 0.5;
    const fit = Object.keys(weights).length ? match(d.text, weights)[0] : 0.5;
    for (const s of found) {
      hits[s] = (hits[s] ?? 0) + 1;
      bySrc[s] = bySrc[s] ?? {};
      bySrc[s][d.source] = (bySrc[s][d.source] ?? 0) + 1;
      close[s] = (close[s] ?? 0) + fit;
      if (age === null || age <= RECENT_DAYS) recent[s] = (recent[s] ?? 0) + w;
      else older[s] = (older[s] ?? 0) + w * Math.min(1, RECENT_DAYS / Math.max(age, 1));
      examples[s] = examples[s] ?? [];
      if (d.url && examples[s].length < 2 && ['paper', 'tool', 'repo'].includes(d.source) && !examples[s].some((e) => e.url === d.url)) {
        examples[s].push({ title: d.title, url: d.url });
      }
    }
  }
  const hist = await history();
  const today = new Date().toISOString().slice(0, 10);
  if (opts.save !== false && docs.length) {
    hist[today] = Object.fromEntries(Object.entries(recent).map(([k, v]) => [k, Math.round(v * 1000) / 1000]));
    const cutoff = new Date(now - 120 * 86400000).toISOString().slice(0, 10);
    for (const d of Object.keys(hist)) if (d < cutoff) delete hist[d];
    await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(hist)).catch(() => undefined);
  }
  const lo = new Date(now - 56 * 86400000).toISOString().slice(0, 10);
  const hi = new Date(now - 21 * 86400000).toISOString().slice(0, 10);
  const feedGrowth = (name: string) => {
    const r = recent[name] ?? 0, o = older[name] ?? 0;
    let growth = (r + 1) / (o + 1);
    const past = Object.entries(hist).filter(([d]) => d >= lo && d <= hi).map(([, v]) => v[name] ?? 0);
    const before = past.length >= 3 ? past.reduce((a, b) => a + b, 0) / past.length : null;
    if (before !== null) growth = 0.5 * growth + 0.5 * (r + 1) / (before + 1);
    return Math.max(0.5, Math.min(growth, 3));
  };
  const feed = Object.fromEntries(vocabulary().filter((s) => hits[s.name]).map((s) => [s.name, feedGrowth(s.name)]));
  const trends = opts.trends ?? await loadTrends();
  const world = corrected(seen, trends, feed);
  const out: Rising[] = [];
  const strengths: Rising[] = [];
  let hidden = 0;
  for (const s of vocabulary()) {
    const n = hits[s.name] ?? 0;
    if (n < MIN_DOCS) continue;
    const r = recent[s.name] ?? 0;
    const o = older[s.name] ?? 0;
    const c = world[s.name];
    // the world's growth replaces your feed's in the score; a rise only in your own feed counts less
    const growth = c?.growth != null ? Math.max(0.5, Math.min(c.growth, 3)) : feed[s.name];
    const v = taste.voteOf(votes, 'skill', s.name);
    const tilt = taste.lean(s.name, s.aliases.slice(0, 3), leanW);
    const score = Math.log1p(r + 0.5 * o) * growth * (0.4 + 0.6 * (close[s.name] ?? 0) / n) * (1 + 0.5 * tilt) * (v > 0 ? 1.3 : 1)
      * (c?.self_made ? 0.6 : 1);
    const row: Rising = {
      name: s.name, kind: s.kind, score, growth: c?.growth ?? Math.round(feed[s.name] * 100) / 100, mentions: n, vote: v,
      examples: examples[s.name] ?? [], rising: !!c?.sure, lo: c?.lo ?? null, hi: c?.hi ?? null, world: c?.world ?? 0,
      mine: c?.mine ?? 0, self_made: !!c?.self_made, beyond: !!c?.beyond,
      reasons: Object.entries(bySrc[s.name] ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([src, k]) => said(src, k)),
    };
    if (have.has(s.name)) strengths.push(row);
    else if (v < 0) hidden++;
    else out.push(row);
  }
  out.sort((a, b) => b.score - a.score);
  strengths.sort((a, b) => b.score - a.score);
  const top = out.slice(0, opts.top ?? 12), shown = new Set(top.map((x) => x.name));
  const links = [...pairs].map(([k, c]) => [...k.split('\n'), c] as Link).filter((l) => shown.has(l[1]))
    .sort((a, b) => b[2] - a[2] || cmp(a[0], b[0]) || cmp(a[1], b[1])).slice(0, 80);
  const hiddenNames = vocabulary().filter((s) => taste.voteOf(votes, 'skill', s.name) < 0).map((s) => s.name);
  const ahead = directions(world, trends, have, new Set([...out.slice(0, 6).map((x) => x.name), ...hiddenNames]),
    Object.fromEntries(vocabulary().map((s) => [s.name, s.kind])));
  return { skills: top, strengths: strengths.slice(0, 8), hidden, links, directions: ahead };
}

export { loadWins };
