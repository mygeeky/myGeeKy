// Rising Skills and Learning paths -- a port of the desktop's skills.py. The phone
// counts how often each skill in a small dictionary (data/skills.json, the same file
// the desktop uses) shows up in what it already read about your field (rising papers,
// field repos, models, headlines), compares it with what you show (your keywords, your
// repos, your papers), and suggests what's rising there but missing from you. 👍/👎
// tilt it; 👎 hides a skill (protocols.ts turns one into stages). Nothing here sends anything.
import AsyncStorage from '@react-native-async-storage/async-storage';
import vocab from '../data/skills.json';
import { match, Weights } from './interests';
import { readCache } from './storage';
import * as taste from './taste';
import { loadWins, WinsState } from './wins';

const HISTORY_KEY = 'mygeeky.skills.history';
const RECENT_DAYS = 45;
const MIN_DOCS = 2;

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

export type Doc = { text: string; when: number | null; source: string; url: string; title: string };

/** What the phone already read about your field (its cached feeds). */
export async function fieldDocs(): Promise<Doc[]> {
  const docs: Doc[] = [];
  const add = (text: string, when: string | undefined, source: string, url = '', title = '') => {
    if (text?.trim()) docs.push({ text: text.slice(0, 3000), when: when ? Date.parse(when) || null : null, source, url, title: title.slice(0, 140) });
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
  for (const h of heads?.data?.items ?? []) if (h.match?.length) add(h.title, h.published, 'news', h.link, h.title);
  return docs;
}

export function ownText(keywords: string[], interests: string[], w: WinsState): string {
  return [keywords.join(' ; '), interests.join(' ; '), ...w.myRepos.map((r) => `${r.name} ; ${r.description} ; ${r.topics.join(' ')} ; ${r.language}`),
    ...w.myPapers].join('\n');
}

export type Rising = { name: string; kind: string; score: number; growth: number; mentions: number; reasons: string[];
  examples: { title: string; url: string }[]; vote: number; rising: boolean };

async function history(): Promise<Record<string, Record<string, number>>> {
  try {
    return JSON.parse((await AsyncStorage.getItem(HISTORY_KEY)) ?? '{}') ?? {};
  } catch {
    return {};
  }
}

export async function rising(opts: { docs: Doc[]; mine: string; weights: Weights; github: boolean; top?: number; save?: boolean }):
  Promise<{ skills: Rising[]; strengths: Rising[]; hidden: number }> {
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
  for (const d of docs) {
    const found = skillsIn(d.text);
    if (!found.size) continue;
    const w = SOURCES[d.source]?.[2] ?? 0.5;
    const age = d.when ? (now - d.when) / 86400000 : null;
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
  const out: Rising[] = [];
  const strengths: Rising[] = [];
  let hidden = 0;
  for (const s of vocabulary()) {
    const n = hits[s.name] ?? 0;
    if (n < MIN_DOCS) continue;
    const r = recent[s.name] ?? 0;
    const o = older[s.name] ?? 0;
    let growth = (r + 1) / (o + 1);
    const past = Object.entries(hist).filter(([d]) => d >= lo && d <= hi).map(([, v]) => v[s.name] ?? 0);
    const before = past.length >= 3 ? past.reduce((a, b) => a + b, 0) / past.length : null;
    if (before !== null) growth = 0.5 * growth + 0.5 * (r + 1) / (before + 1);
    growth = Math.max(0.5, Math.min(growth, 3));
    const v = taste.voteOf(votes, 'skill', s.name);
    const tilt = taste.lean(s.name, s.aliases.slice(0, 3), leanW);
    const score = Math.log1p(r + 0.5 * o) * growth * (0.4 + 0.6 * (close[s.name] ?? 0) / n) * (1 + 0.5 * tilt) * (v > 0 ? 1.3 : 1);
    const row: Rising = {
      name: s.name, kind: s.kind, score, growth, mentions: n, vote: v, examples: examples[s.name] ?? [],
      rising: growth >= 1.3 && (before !== null || o > 0),
      reasons: Object.entries(bySrc[s.name] ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([src, k]) => said(src, k)),
    };
    if (have.has(s.name)) strengths.push(row);
    else if (v < 0) hidden++;
    else out.push(row);
  }
  out.sort((a, b) => b.score - a.score);
  strengths.sort((a, b) => b.score - a.score);
  return { skills: out.slice(0, opts.top ?? 12), strengths: strengths.slice(0, 5), hidden };
}

export { loadWins };
