// GEMS (Games: Evidence, Mastery, Signals): a port of the desktop's gems.py, line for line, so a round picks,
// scores and teaches the same on both apps (docs/GEMS.md; tests/test_gems.py runs this file against the Python).
//
// The games, the content they play (data/games.json, identical to the desktop's), and the rules: `validate` (a pack
// must pass it), `pick` (~70% your field, ~20% new territory, ~10% due again, never above what your level unlocks,
// shuffled by a seeded generator), `record` (points, stars, levels, spaced repetition, per-topic right/wrong/time),
// `modelTerms` (what the Model learns: topics played, by right answers and playing time), `mastery` (what you know,
// what you're learning) and `badgeCounts` (Player, Sharp, Level up). Nothing here touches the network or a screen.

export type Item = Record<string, any> & { id: string; kind: string; level: number; terms: string[] };
export type Answer = { id: string; right: boolean; level: number; terms: string[] };
export type GameStats = { plays: number; xp: number; best: number; seconds: number; answered: number; right: number; last?: string };
export type Progress = {
  version: 1;
  games: Record<string, GameStats>;
  items: Record<string, { box: number; right: number; wrong: number; due?: string; seen?: string }>;
  topics: Record<string, { right: number; wrong: number; seconds: number }>;
  xp: number;
};

export const GAMES: { id: string; title: string; emoji: string; kinds: string[]; about: string }[] = [
  { id: 'hunter', title: 'Word Hunter', emoji: '☄️', kinds: ['wordset', 'question'],
    about: 'Shoot the words that belong to the set; let the wrong ones drift past.' },
  { id: 'rise', title: 'Rise', emoji: '\u{1f30a}', kinds: ['ladder'],
    about: 'Climb out of the sea on the right next step of a pipeline.' },
  { id: 'maze', title: 'GeeKOc goes home', emoji: '\u{1f3e0}', kinds: ['question'],
    about: 'Find the way home; doors ask questions from your protocols.' },
  { id: 'run', title: 'GeeKOc run', emoji: '\u{1f3c3}', kinds: ['gate'],
    about: 'Jump the bugs; at a gate, jump for the top answer or stay low for the bottom one.' },
  { id: 'flappy', title: 'Flappy GeeKOc', emoji: '\u{1f419}', kinds: ['gate'],
    about: 'Swim up through the gap of the right answer.' },
  { id: 'whack', title: 'Whack-a-bug', emoji: '\u{1f528}', kinds: ['critter'],
    about: 'Whack the bugs, spare the friends.' },
  { id: 'realfake', title: 'Real tool or made up?', emoji: '\u{1f575}️', kinds: ['realfake'],
    about: 'Which tools really exist?' },
  { id: 'genemon', title: 'Gene or Pokémon?', emoji: '\u{1f9ec}', kinds: ['genemon'],
    about: 'Sonic hedgehog or Psyduck: gene or Pokémon?' },
  { id: 'reviewer', title: 'Reviewer 2 attacks', emoji: '\u{1f421}', kinds: ['review'],
    about: 'Answer the grumpy reviewer well and get your paper accepted.' },
  { id: 'reef', title: 'Debug reef', emoji: '\u{1fab8}', kinds: ['snippet'],
    about: 'Tap the line with the bug before the bubble rises.' },
  { id: 'catch', title: 'Sort the catch', emoji: '\u{1f3a3}', kinds: ['sort'],
    about: 'Steer each name into the right net.' },
  { id: 'figure', title: 'Fix the figure', emoji: '\u{1f4ca}', kinds: ['figure'],
    about: "Spot what's wrong with the plot." },
  { id: 'first', title: 'Which came first?', emoji: '⚖️', kinds: ['year'],
    about: 'Two tools, one question: which is older?' },
  { id: 'terminal', title: 'Terminal typing', emoji: '⌨️', kinds: ['command'],
    about: "Two commands do the task, one doesn't: pick a right one (and type it, on the computer)." },
];
export const GAME_IDS = GAMES.map((g) => g.id);

export const KINDS = ['wordset', 'ladder', 'gate', 'critter', 'realfake', 'genemon', 'review', 'snippet', 'sort', 'figure', 'year', 'command'];
export const FIGURE_KINDS = ['truncated', 'rainbow', 'noerror', 'dualaxis', 'pie3d', 'overplot', 'spaghetti', 'nolabels'];
export const SHARES = { field: 0.7, explore: 0.2, review: 0.1 };
export const INTERVALS = [1, 2, 4, 8, 16, 32];
export const GAME_MAX_LEVEL = 10;
const TERMS_PER_ROUND = 12;

// ------------------------------------------------------------------------------------------------ the same dice
/** mulberry32, as gems.Dice: a seed picks alike on both apps. */
export class Dice {
  a: number;
  constructor(seed: number) { this.a = seed >>> 0; }
  next(): number {
    this.a = (this.a + 0x6d2b79f5) >>> 0;
    let t = this.a;
    t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
    t = (t ^ ((t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0)) >>> 0)) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  shuffle<T>(items: T[]): T[] {
    const out = items.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(this.next() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }
}

/** Halves go up, the same on both apps (Python's round() sends 2.5 to 2). */
export function halfUp(x: number, digits = 0): number {
  const k = 10 ** digits;
  return Math.floor(x * k + 0.5) / k;
}

/** FNV-1a over code points, as gems.seed_of. */
export function seedOf(text: string): number {
  let h = 2166136261;
  for (const ch of text) h = Math.imul(h ^ (ch.codePointAt(0) ?? 0), 16777619) >>> 0;
  return h >>> 0;
}

// ------------------------------------------------------------------------------------------------ the pack
const https = (u: unknown) => typeof u === 'string' && u.startsWith('https://') && u.length < 300 && !u.includes(' ');
const pyLen = (s: string) => [...s].length;          // Python counts code points, JS UTF-16 units
const textP = (v: unknown, most = 400) => typeof v === 'string' && v.trim().length > 0 && pyLen(v) <= most;

/** Everything wrong with a pack, as gems.validate (same sentences). */
export function validate(pack: any): string[] {
  const problems: string[] = [];
  const seen = new Set<string>();
  const items = pack && typeof pack === 'object' ? pack.items : null;
  if (!Array.isArray(items) || !items.length) return ['the pack has no items'];
  items.forEach((it: any, n: number) => {
    let where = `item ${n + 1}`;
    if (!it || typeof it !== 'object' || Array.isArray(it)) { problems.push(`${where} is not an object`); return; }
    const iid = it.id, kind = it.kind;
    where = `${iid || where}`;
    if (typeof iid !== 'string' || !iid || pyLen(iid) > 60) problems.push(`${where}: no id`);
    else if (seen.has(iid)) problems.push(`${where}: id used twice`);
    seen.add(String(iid));
    if (!KINDS.includes(kind)) { problems.push(`${where}: unknown kind ${JSON.stringify(kind)}`); return; }
    if (![1, 2, 3].includes(it.level)) problems.push(`${where}: level must be 1, 2 or 3`);
    const terms = it.terms;
    if (!Array.isArray(terms) || !terms.every((t: unknown) => typeof t === 'string' && t === t.toLowerCase() && t.trim()))
      problems.push(`${where}: terms must be a list of lower-case words`);
    const src = it.source;
    if (!(src && typeof src === 'object' && textP(src.title, 160) && https(src.url)))
      problems.push(`${where}: needs a source with a title and an https link`);
    for (const p of shape(kind, it)) problems.push(`${where}: ${p}`);
  });
  return problems;
}

function shape(kind: string, it: any): string[] {
  const p: string[] = [];
  const T = textP;
  if (kind === 'wordset') {
    if (!T(it.name, 80) || !T(it.what, 80)) p.push('a word set needs a name and what one of its words is');
    if (!Array.isArray(it.words) || it.words.length < 6 || !it.words.every((w: unknown) => T(w, 40))) p.push('a word set needs at least 6 words');
  } else if (kind === 'ladder') {
    const rows = it.rows;
    if (!T(it.name, 80) || !Array.isArray(rows) || rows.length < 4) p.push('a ladder needs a name and at least 4 rows');
    else if (!rows.every((r: any) => r && T(r.right, 120) && Array.isArray(r.wrong) && r.wrong.length
        && r.wrong.every((w: any) => w && T(w.text, 120) && T(w.why, 200))))
      p.push('each ladder row needs the right step and wrong ones that say why');
  } else if (kind === 'gate') {
    if (!(T(it.q, 70) && T(it.right, 18) && T(it.wrong, 18))) p.push('a gate needs a short question and two short answers');
    else if (it.right === it.wrong) p.push("a gate's two answers must differ");
  } else if (kind === 'critter') {
    if (!(T(it.label, 24) && (it.bug === true || it.bug === false) && T(it.why, 160))) p.push("a critter needs a short label, whether it's a bug, and why");
  } else if (kind === 'realfake' || kind === 'genemon') {
    const ok = kind === 'realfake' ? (it.real === true || it.real === false) : ['gene', 'pokemon'].includes(it.answer);
    if (!(T(it.name, 40) && ok && T(it.fact, 200))) p.push(`a ${kind} card needs a name, its answer and a fact`);
  } else if (kind === 'review') {
    if (!(T(it.comment, 120) && T(it.right, 120) && Array.isArray(it.wrong) && it.wrong.length >= 2 && it.wrong.every((w: unknown) => T(w, 120))))
      p.push('a review needs a comment, the right reply and two wrong ones');
  } else if (kind === 'snippet') {
    const lines = it.lines, bug = it.bug;
    if (!(['Python', 'R', 'Shell', 'SQL'].includes(it.lang) && Array.isArray(lines) && lines.length >= 2 && lines.length <= 10
        && lines.every((x: unknown) => typeof x === 'string' && pyLen(x) <= 80) && Number.isInteger(bug)
        && bug >= 0 && bug < lines.length && T(it.why, 200)))
      p.push('a snippet needs a language, 2-10 short lines, the buggy line and why');
  } else if (kind === 'sort') {
    const bins = it.bins, things = it.things;
    if (!(T(it.name, 80) && Array.isArray(bins) && bins.length >= 2 && bins.length <= 3 && bins.every((b: unknown) => T(b, 20))
        && Array.isArray(things) && things.length >= 6
        && things.every((t: any) => Array.isArray(t) && t.length === 2 && T(t[0], 30) && Number.isInteger(t[1]) && t[1] >= 0 && t[1] < bins.length)))
      p.push('a sort needs 2-3 bins and at least 6 names, each with its bin');
  } else if (kind === 'figure') {
    if (!(FIGURE_KINDS.includes(it.draw) && T(it.right, 140) && Array.isArray(it.wrong) && it.wrong.length >= 3 && it.wrong.every((w: unknown) => T(w, 140))))
      p.push('a figure needs a known drawing, the right flaw and three wrong ones');
  } else if (kind === 'year') {
    const y = it.year;
    if (!(T(it.name, 40) && Number.isInteger(y) && y >= 1900 && y <= 2100 && T(it.event, 80)))
      p.push('a year card needs a name, a year and what happened that year');
  } else if (kind === 'command') {
    const right = it.right, wrong = it.wrong;
    if (!(T(it.task, 120) && Array.isArray(right) && right.length === 2 && right.every((c: unknown) => T(c, 70)) && right[0] !== right[1]
        && wrong && typeof wrong === 'object' && T(wrong.cmd, 70) && T(wrong.why, 200) && !right.includes(wrong.cmd)))
      p.push('a command needs a task, two right commands and one wrong one that says why');
  }
  return p;
}

export function itemsOf(pack: any, kind: string): Item[] {
  return (pack?.items ?? []).filter((it: any) => it && typeof it === 'object' && it.kind === kind);
}

// ------------------------------------------------------------------------------------------------ picking
export function relevance(item: Item, weights: Record<string, number>): number {
  return (item.terms ?? []).reduce((s, t) => s + Number(weights[t] ?? 0), 0);
}

export const maxItemLevel = (gameLevel: number) => (gameLevel < 3 ? 1 : gameLevel < 6 ? 2 : 3);

const isDue = (entry: { due?: string } | undefined, today: string) => !!entry && String(entry.due ?? '') <= today;
const cmpStr = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

/** The round's items, as gems.pick. */
export function pick(items: Item[], n: number, progress: Partial<Progress> | null, weights: Record<string, number>,
                     today: string, seed: number, gameLevel = 1): Item[] {
  const top = maxItemLevel(gameLevel);
  let pool = items.filter((it) => Number(it.level ?? 1) <= top);
  if (!pool.length) pool = items.slice();
  const seen = (progress && typeof progress === 'object' ? progress.items : undefined) ?? {};
  const dice = new Dice(seed);
  const order: Record<string, number> = {};
  dice.shuffle(pool).forEach((it, i) => { order[it.id] = i; });
  const rel = (it: Item) => relevance(it, weights);
  const review = pool.filter((it) => isDue(seen[it.id], today));
  const fresh = pool.filter((it) => !(it.id in seen));
  const field = fresh.filter((it) => rel(it) > 0).sort((a, b) => rel(b) - rel(a) || order[a.id] - order[b.id]);
  const explore = fresh.filter((it) => rel(it) <= 0).sort((a, b) => order[a.id] - order[b.id]);
  review.sort((a, b) => cmpStr(String(seen[a.id].due ?? ''), String(seen[b.id].due ?? '')) || order[a.id] - order[b.id]);
  const resting = pool.filter((it) => it.id in seen && !isDue(seen[it.id], today))
    .sort((a, b) => cmpStr(String(seen[a.id].seen ?? ''), String(seen[b.id].seen ?? '')) || order[a.id] - order[b.id]);
  const want = { review: halfUp(n * SHARES.review), explore: halfUp(n * SHARES.explore), field: 0 };
  want.field = n - want.review - want.explore;
  const out: Item[] = [];
  const taken = new Set<string>();
  const take = (src: Item[], k: number) => {
    for (const it of src) {
      if (out.length >= n || k <= 0) return;
      if (!taken.has(it.id)) { out.push(it); taken.add(it.id); k--; }
    }
  };
  take(review, want.review);
  take(explore, want.explore);
  take(field, want.field);
  for (const src of [field, explore, review, resting]) take(src, n - out.length);
  return dice.shuffle(out);
}

// ------------------------------------------------------------------------------------------------ scoring
export const xpForLevel = (level: number) => 75 * level * (level - 1);

export function levelOf(xp: number, cap = GAME_MAX_LEVEL): number {
  let lv = 1;
  while (lv < cap && xp >= xpForLevel(lv + 1)) lv++;
  return lv;
}

export function playerLevel(xp: number): number {
  let lv = 1;
  while (xp >= 150 * (lv + 1) * lv) lv++;
  return lv;
}

export const stars = (accuracy: number) => (accuracy >= 0.95 ? 3 : accuracy >= 0.8 ? 2 : accuracy >= 0.6 ? 1 : 0);

export function points(answers: Answer[], bonus = 0): number {
  return answers.reduce((s, a) => s + (a.right ? 10 * Number(a.level ?? 1) : 0), 0) + Math.max(0, Math.trunc(bonus));
}

export const emptyProgress = (): Progress => ({ version: 1, games: {}, items: {}, topics: {}, xp: 0 });

function addDays(day: string, n: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** A finished round into your progress, as gems.record. Returns [progress, summary]. */
export function record(progress: Progress | null | undefined, game: string, answers: Answer[], seconds: number, today: string,
                       bonus = 0): [Progress, Record<string, any>] {
  const prog: Progress = progress && progress.version === 1 ? progress : emptyProgress();
  prog.games ??= {}; prog.items ??= {}; prog.topics ??= {};
  const g = prog.games[game] ?? (prog.games[game] = { plays: 0, xp: 0, best: 0, seconds: 0, answered: 0, right: 0 });
  const right = answers.filter((a) => a.right).length;
  const acc = answers.length ? right / answers.length : 0;
  const pts = points(answers, bonus);
  const before = levelOf(g.xp), playerBefore = playerLevel(prog.xp ?? 0);
  const newBest = pts > (g.best ?? 0);
  const secs = Math.max(0, halfUp(seconds));
  Object.assign(g, { plays: g.plays + 1, xp: g.xp + pts, best: Math.max(g.best ?? 0, pts), seconds: g.seconds + secs,
                     answered: g.answered + answers.length, right: g.right + right, last: today });
  prog.xp = (prog.xp ?? 0) + pts;
  const share = secs / Math.max(1, answers.length);
  for (const a of answers) {
    const e = prog.items[String(a.id)] ?? (prog.items[String(a.id)] = { box: 0, right: 0, wrong: 0 });
    if (a.right) { e.box = Math.min((e.box ?? 0) + 1, INTERVALS.length - 1); e.right = (e.right ?? 0) + 1; }
    else { e.box = 0; e.wrong = (e.wrong ?? 0) + 1; }
    e.due = addDays(today, INTERVALS[e.box]);
    e.seen = today;
    for (const t of a.terms ?? []) {
      const tp = prog.topics[t] ?? (prog.topics[t] = { right: 0, wrong: 0, seconds: 0 });
      if (a.right) tp.right += 1; else tp.wrong += 1;
      tp.seconds = tp.seconds + halfUp(share);
    }
  }
  const after = levelOf(g.xp);
  return [prog, { game, points: pts, right, answered: answers.length, accuracy: halfUp(acc, 3), stars: stars(acc),
                  best: g.best, new_best: newBest, level: after, level_up: after > before,
                  player_level: playerLevel(prog.xp), player_level_up: playerLevel(prog.xp) > playerBefore,
                  next_level_xp: after < GAME_MAX_LEVEL ? xpForLevel(after + 1) : null, xp: g.xp }];
}

// ------------------------------------------------------------------------------------------------ what it teaches
/** What the Model learns from a round, as gems.model_terms. */
export function modelTerms(answers: Answer[], seconds: number): Record<string, number> {
  const raw: Record<string, number> = {};
  for (const a of answers) {
    const terms = a.terms ?? [];
    for (const t of terms) raw[t] = (raw[t] ?? 0) + (a.right ? 1.0 : 0.6) / Math.max(1, terms.length);
  }
  const keys = Object.keys(raw);
  if (!keys.length) return {};
  const minutes = Math.max(0, seconds) / 60;
  const strength = Math.min(1.5, 0.3 + 0.12 * minutes);
  const total = keys.reduce((s, k) => s + raw[k], 0);
  const ranked = keys.map((k) => [k, raw[k]] as [string, number]).sort((x, y) => y[1] - x[1] || cmpStr(x[0], y[0])).slice(0, TERMS_PER_ROUND);
  const out: Record<string, number> = {};
  for (const [t, w] of ranked) out[t] = halfUp((w / total) * strength, 4);
  return out;
}

/** Topics you know and ones you're learning, as gems.mastery. */
export function mastery(progress: Partial<Progress> | null, least = 3): { knows: string[]; learning: string[] } {
  const knows: [number, string][] = [], learning: [number, string][] = [];
  for (const [t, tp] of Object.entries(progress?.topics ?? {})) {
    const r = Number(tp.right ?? 0), w = Number(tp.wrong ?? 0), n = r + w;
    if (n >= least && r / n >= 0.8) knows.push([n, t]);
    else if (w >= 2 && r / n < 0.6) learning.push([n, t]);
  }
  const order = (xs: [number, string][]) => xs.sort((a, b) => b[0] - a[0] || cmpStr(a[1], b[1])).map((x) => x[1]);
  return { knows: order(knows), learning: order(learning) };
}

export function badgeCounts(progress: Partial<Progress> | null | undefined): Record<string, number> {
  const games = Object.values(progress?.games ?? {});
  return { player: games.reduce((s, g) => s + Number(g.plays ?? 0), 0),
           sharp: games.reduce((s, g) => s + Number(g.right ?? 0), 0),
           levelup: games.reduce((s, g) => s + levelOf(Number(g.xp ?? 0)) - 1, 0) };
}

/** Each game's level, best, plays and time, and your player level, as gems.summary_of. */
export function summaryOf(progress: Partial<Progress> | null | undefined) {
  const games = progress?.games ?? {};
  const out = GAMES.map((g) => {
    const s = games[g.id] ?? ({} as Partial<GameStats>);
    const xp = Number(s.xp ?? 0), lv = levelOf(xp);
    const nxt = lv < GAME_MAX_LEVEL ? xpForLevel(lv + 1) : null, low = xpForLevel(lv);
    return { id: g.id, title: g.title, level: lv, xp, best: Number(s.best ?? 0), plays: Number(s.plays ?? 0),
             seconds: Number(s.seconds ?? 0), progress: nxt === null ? 1.0 : halfUp((xp - low) / Math.max(1, nxt - low), 3) };
  });
  const xp = Number(progress?.xp ?? 0);
  return { games: out, xp, player_level: playerLevel(xp),
           minutes: Math.floor(Object.values(games).reduce((s, g) => s + Number(g.seconds ?? 0), 0) / 60) };
}

export function roundTerms(items: Item[]): string[] {
  const out: string[] = [];
  for (const it of items) for (const t of it.terms ?? []) if (!out.includes(t)) out.push(t);
  return out;
}
