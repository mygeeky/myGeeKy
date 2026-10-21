// 🏠 Home: one scrolling feed of everything myGeeKy already found for you (the desktop's feed.py: the same rules,
// checked by tests/test_feed.py). Built only from what the other pages already keep, so scrolling never asks the
// internet. Order: fit (your Model's terms), freshness per kind, what you've seen, a UCB1 bandit over card kinds
// (learned from taps, time on screen and quick skips), variety (at most 2 of a kind in any 4, sources spread) and one card
// in five of new territory 🔭. Deterministic, so both apps agree.
import AsyncStorage from '@react-native-async-storage/async-storage';

export type Card = { id: string; kind: string; title: string; sub?: string; url?: string; at?: string; terms?: string[]; source?: string; page?: string };
export type Seen = Record<string, { n?: number; opened?: boolean; at?: string }>;
export type Stats = Record<string, { s: number; f: number }>;
export type Ctx = { today: string; weights?: Record<string, number>; seen?: Seen; stats?: Stats };
export type Item = { card: Card; score: number; fit: number; fresh: number; explore: boolean; seen: boolean; why: string };

export const KINDS: Record<string, [string, string, number]> = {
  work: ['New work from your circle', '📄', 21], paper: ['Rising in your field', '🔬', 14], news: ['Papers & discussions', '💬', 4],
  headline: ['Headline', '🗞', 2], job: ['Job', '💼', 21], funding: ['Funding', '💶', 30], conference: ['Conference', '🎤', 30],
  dataset: ['Dataset', '🗂', 30], repo: ['Repo to help', '📦', 14], rising: ['Rising repo', '📈', 7], person: ['Someone to meet', '👥', 14],
  model: ['AI model', '🤗', 7], highlight: ['Highlight', '✨', 30], skill: ['Rising skill', '🧠', 30], quiz: ['Quiz', '🏆', 3650],
};
const EXPLORE_EVERY = 5, SAME_KIND_RUN = 2, SOURCE_WINDOW = 10, SOURCE_MAX = 3, STATS_HALF_LIFE = 30, READ_SECONDS = 4, SKIP_SECONDS = 1, SEEN_KEEP = 2000;
const KEY = 'mygeeky.feed';

export const r4 = (x: number) => Math.floor(x * 10000 + 0.5) / 10000;
const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9+#]+/g, ' ');
const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
const text = (c: Card) => ` ${norm([c.title ?? '', c.sub ?? '', ...(c.terms ?? []).map(String)].join(' '))} `;

export function fit(c: Card, weights: Record<string, number>): [number, string[]] {
  const t = text(c);
  const hits: [number, string][] = [];
  for (const [term, w] of Object.entries(weights)) {
    const key = ` ${norm(term).trim()} `;
    if (key.length > 3 && t.includes(key)) hits.push([Number(w), term]);
  }
  hits.sort((a, b) => b[0] - a[0] || cmp(a[1], b[1]));
  let score = 0;
  [1, 0.3, 0.15].forEach((f, i) => { if (hits[i]) score += hits[i][0] * f; });
  return [r4(Math.min(1, score)), hits.slice(0, 3).map((h) => h[1])];
}

export function ageDays(c: Card, today: string): number {
  const a = Date.parse(`${String(c.at ?? '').slice(0, 10)}T00:00:00Z`), b = Date.parse(`${today.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(a) || Number.isNaN(b)) return 30;
  return Math.max(0, Math.round((b - a) / 86400000));
}
export const freshness = (c: Card, today: string) => r4(0.5 ** (ageDays(c, today) / (KINDS[c.kind]?.[2] ?? 14)));
export function seenFactor(seen: Seen, id: string): number {
  const s = seen[id] ?? {};
  return s.opened ? 0.15 : r4(0.6 ** Math.trunc(Number(s.n ?? 0)));
}
export function kindPref(stats: Stats, kind: string): number {
  let total = 0;
  for (const v of Object.values(stats)) total += Number(v.s ?? 0) + Number(v.f ?? 0);
  const k = stats[kind] ?? { s: 0, f: 0 }, s = Number(k.s ?? 0), f = Number(k.f ?? 0);
  const mean = (s + 1) / (s + f + 2), bonus = 0.25 * Math.sqrt((2 * Math.log(total + 2)) / (s + f + 1));
  return r4(Math.min(1.25, mean + bonus));
}
function why(c: Card, terms: string[], age: number, explore: boolean, pref: number): string {
  const bits: string[] = [];
  if (explore) bits.push('new territory 🔭'); else if (terms.length) bits.push(`matches ${terms.slice(0, 2).join(', ')}`);
  bits.push(age === 0 ? 'new today' : age === 1 ? 'yesterday' : age < 30 ? `${age} days ago` : 'older');
  if (pref >= 0.85 && !explore) bits.push(`you often open ${(KINDS[c.kind]?.[0] ?? 'these').toLowerCase()}`);
  return bits.join(' · ');
}

export function scoreAll(cards: Card[], ctx: Ctx): Item[] {
  const weights = ctx.weights ?? {}, seen = ctx.seen ?? {}, stats = ctx.stats ?? {};
  return cards.map((c) => {
    const [f, terms] = fit(c, weights), fr = freshness(c, ctx.today), pref = kindPref(stats, c.kind), sf = seenFactor(seen, c.id);
    const explore = f === 0;
    const score = explore ? r4(fr * sf * 0.6) : r4((0.6 * f + 0.4 * fr) * (0.5 + pref) * sf);
    const s = seen[c.id] ?? {};
    return { card: c, score, fit: f, fresh: fr, explore, seen: !!(s.n || s.opened), why: why(c, terms, ageDays(c, ctx.today), explore, pref) };
  });
}

/** The feed (feed.arrange): unseen first with variety and new territory, then what you've already seen. */
export function arrange(cards: Card[], ctx: Ctx, n = 60): Item[] {
  const byScore = (a: Item, b: Item) => b.score - a.score || cmp(a.card.id, b.card.id);
  const titles = new Set<string>(), scored: Item[] = [];
  for (const x of scoreAll(cards, ctx).sort(byScore)) {           // the same story from two places shows once (the better)
    const t = String(x.card.title ?? '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 80);
    if (t && titles.has(t)) continue;
    titles.add(t);
    scored.push(x);
  }
  const main = scored.filter((x) => !x.seen && !x.explore).sort(byScore);
  const explore = scored.filter((x) => !x.seen && x.explore).sort(byScore);
  const older = scored.filter((x) => x.seen).sort(byScore);
  const picked: Item[] = [];
  while (picked.length < n && (main.length || explore.length)) {
    if ((explore.length && (picked.length + 1) % EXPLORE_EVERY === 0) || !main.length) { picked.push(explore.shift()!); continue; }
    const kinds = picked.slice(-(SAME_KIND_RUN + 1)).map((x) => x.card.kind);
    const window = picked.slice(-(SOURCE_WINDOW - 1)).map((x) => x.card.source ?? '');
    let choice = 0;
    for (let i = 0; i < main.length; i++) {
      const x = main[i];
      const run = kinds.filter((k) => k === x.card.kind).length >= SAME_KIND_RUN;
      const crowded = window.filter((s) => s === (x.card.source ?? '')).length >= SOURCE_MAX;
      if (!run && !crowded) { choice = i; break; }
    }
    picked.push(main.splice(choice, 1)[0]);
  }
  return [...picked, ...older.slice(0, Math.max(0, n - picked.length))];
}

export function learn(stats: Stats, kind: string, what: 'open' | 'up' | 'down' | 'view', dwell = 0, daysSince = 0): Stats {
  const decay = 0.5 ** (Math.max(0, daysSince) / STATS_HALF_LIFE);
  const out: Stats = {};
  for (const [k, v] of Object.entries(stats)) out[k] = { s: r4(Number(v.s ?? 0) * decay), f: r4(Number(v.f ?? 0) * decay) };
  const k = (out[kind] ??= { s: 0, f: 0 });
  if (what === 'open' || what === 'up') k.s = r4(k.s + 1);
  else if (what === 'down') k.f = r4(k.f + 1);
  else if (what === 'view') { if (dwell >= READ_SECONDS) k.s = r4(k.s + 0.5); else if (dwell < SKIP_SECONDS) k.f = r4(k.f + 0.25); }
  return out;
}

export function markSeen(seen: Seen, id: string, opened: boolean, today: string): Seen {
  const out: Seen = { ...seen };
  const s = { ...(out[id] ?? {}) };
  s.n = Math.trunc(Number(s.n ?? 0)) + (opened ? 0 : 1);
  s.opened = !!(s.opened || opened);
  s.at = today.slice(0, 10);
  out[id] = s;
  const keys = Object.keys(out);
  if (keys.length > SEEN_KEEP) {
    for (const old of keys.sort((a, b) => cmp(out[a].at ?? '', out[b].at ?? '') || cmp(a, b)).slice(0, keys.length - SEEN_KEEP)) delete out[old];
  }
  return out;
}

// ---- the store
export type FeedState = { stats: Stats; seen: Seen; learned_at: string; dwell: boolean };
export async function load(): Promise<FeedState> {
  try {
    const d = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '{}');
    return { stats: d.stats && typeof d.stats === 'object' ? d.stats : {}, seen: d.seen && typeof d.seen === 'object' ? d.seen : {},
      learned_at: String(d.learned_at ?? ''), dwell: d.dwell !== false };
  } catch {
    return { stats: {}, seen: {}, learned_at: '', dwell: true };
  }
}
const save = (s: FeedState) => AsyncStorage.setItem(KEY, JSON.stringify(s)).catch(() => undefined);

/** A tap, a vote, or a card leaving the screen after `dwell` seconds (feed.record). */
export async function record(kind: string, id: string, what: 'open' | 'up' | 'down' | 'view', dwell = 0, today = new Date().toISOString().slice(0, 10)): Promise<FeedState> {
  const s = await load();
  if (what === 'view' && !s.dwell) return s;
  const since = s.learned_at ? Math.max(0, Math.round((Date.parse(`${today}T00:00:00Z`) - Date.parse(`${s.learned_at}T00:00:00Z`)) / 86400000)) : 0;
  s.stats = learn(s.stats, kind, what, dwell, Number.isNaN(since) ? 0 : since);
  s.learned_at = today;
  if (what === 'open' || what === 'view') s.seen = markSeen(s.seen, id, what === 'open', today);
  await save(s);
  return s;
}
export async function setDwell(on: boolean): Promise<void> { const s = await load(); s.dwell = on; await save(s); }
