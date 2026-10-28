// Learning from what you open: interests.py (extract_terms, learned_terms, blend_learned), ported. Pure, so a test
// runs it in Node against the desktop (tests/test_learn_locally.py); model-repo.ts keeps and syncs the events.

export const KIND_WEIGHTS: Record<string, number> = { fork: 2.5, join: 2.5, follow: 2.0, star: 1.5, like: 1.5, repo: 1.0, news: 0.8, person: 0.7, play: 0.8 };
export const MIN_LEARNED_WEIGHT = 1.0;
export const TERMS_PER_EVENT = 12;
const WORD = /[a-z][a-z0-9+#.-]{2,}/g;
export const STOPWORDS = new Set(('a about above across after again all also am among an analyses analysis and any app approach approaches apps are as associated association at awesome based be because been before being below between both build builds built but by can code could data did different do does doing down during each easy fast few first followers following follows for found framework from further github had has have having he helper helpers her here hers high him his how however i if implementation in include includes including into is it its itself just large library like list lists low made make makes method methods model models module modules more most my new no nor not now of off official on once one only open or other our out over own package packages paper papers plugin plugins project projects provide provided provides python release released repo repos repository results same several she should show shown shows simple small so software some source studies study such support supported supports system systems than that the their them then there therefore these they this those three through to too tool toolbox toolkit toolkits tools two type under until up use used user users using utilities utility various version very via was way we well were what when where which while who whom why will with within work works would wrapper wrappers you your yours').split(' '));

export type Event = { at: string; kind: string; terms: Record<string, number>; source?: string };
export type LearnConfig = { interest_learning: boolean; interest_half_life_days: number };

export function extractTerms(text = '', topics: string[] = []): Record<string, number> {
  const counts = new Map<string, number>();
  const add = (t: string, n: number) => counts.set(t, (counts.get(t) ?? 0) + n);
  for (const raw of topics) {
    const t = String(raw).trim().toLowerCase().replace(/-/g, ' ');
    if (t.length > 2 && t.length <= 40) add(t, 3);
  }
  for (const m of text.toLowerCase().matchAll(WORD)) {
    const w = m[0].replace(/^[.-]+|[.-]+$/g, '').replace(/-/g, ' ');
    if (w.length > 2 && !STOPWORDS.has(w) && !/^\d+$/.test(w)) add(w, 1);
  }
  // Counter.most_common: by count, ties in the order first seen
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, TERMS_PER_EVENT);
  const total = top.reduce((sum, [, n]) => sum + n, 0) || 1;
  return Object.fromEntries(top.map(([t, n]) => [t, Math.round((n / total) * 10000) / 10000]));
}

const ONCE_KINDS = ['follow', 'star', 'fork'];
const onceKey = (ev: Event) => (ONCE_KINDS.includes(ev.kind) && ev.source ? `${ev.kind}\n${ev.source.toLowerCase()}` : '');
const followedLogin = (ev: Event) => (ev.kind === 'follow' && ev.source?.startsWith('followed ') ? ev.source.slice(9).trim().toLowerCase() : '');

/** interests.once_each: a follow, star or fork counts once, at its latest (a list GitHub sent short once made the
 * same follow look new again and again). */
export function onceEach(events: Event[]): Event[] {
  const last = new Map<string, number>();
  events.forEach((ev, i) => { const k = onceKey(ev); if (k) last.set(k, i); });
  return events.filter((ev, i) => { const k = onceKey(ev); return !k || last.get(k) === i; });
}

export function learnedTerms(events: Event[], cfg: LearnConfig, n: number, now = Date.now()): [string, number][] {
  if (!cfg.interest_learning) return [];
  const weights: Record<string, number> = {};
  for (const ev of onceEach(events)) {
    const at = Date.parse(ev.at);
    if (Number.isNaN(at)) continue;
    const ageDays = (now - at) / 86400000;
    const fade = 0.5 ** (Math.max(ageDays, 0) / Math.max(cfg.interest_half_life_days, 1));
    const login = followedLogin(ev);
    for (const [term, share] of Object.entries(ev.terms)) {
      if (login && login.includes(term.replace(/ /g, ''))) continue;   // "jake", "wharton" from JakeWharton: a name, not a topic
      weights[term] = (weights[term] ?? 0) + (KIND_WEIGHTS[ev.kind] ?? 0.5) * share * fade;
    }
  }
  return Object.entries(weights).sort((a, b) => b[1] - a[1])
    .map(([t, w]) => [t, Math.round(w * 100) / 100] as [string, number])
    .filter(([, w]) => w >= MIN_LEARNED_WEIGHT).slice(0, n);
}

/** interests.blend_learned: the strongest learned terms join your weights, the top one at 1.0. */
export function blendLearned(weights: Record<string, number>, learned: [string, number][]): Record<string, number> {
  const out = { ...weights };
  if (!learned.length) return out;
  const top = learned[0][1];
  for (const [term, w] of learned) out[term] = Math.max(out[term] ?? 0, 0.3 + (0.7 * w) / top);
  return out;
}
