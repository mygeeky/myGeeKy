// 🏠 Home's cards on the phone (the desktop's feed.candidates): everything the other pages already keep, read from
// the phone's own copies -- never fetched here, so scrolling costs nothing and works offline. Each source is read
// on its own, and one that can't be read is simply left out. The ranking is lib/feed.ts.
import { type Card, arrange, load as loadFeed } from './feed';
import { daysLeft } from './curated';
import { loadRadar } from './datasets';
import { feed as researchersFeed, load as loadResearchers } from './researchers';
import { bank } from './quiz';
import { readCache } from './storage';

const clip = (s: unknown, n = 200) => String(s ?? '').split(/\s+/).join(' ').trim().slice(0, n);
const today = () => new Date().toISOString().slice(0, 10);
const num = (x: unknown) => { const v = Number(x); return Number.isFinite(v) && v > 0 ? v : 0; };
/** feed._quiz_facts: a choice question can be answered right on its card. */
function quizFacts(q: any): Record<string, unknown> {
  const opts = q?.options, ans = q?.answer;
  if (!(Array.isArray(opts) && opts.length >= 2 && opts.length <= 6 && Number.isInteger(ans) && ans >= 0 && ans < opts.length && !q.code)) return {};
  return { options: opts.map((o: unknown) => clip(o, 160)), answer: ans, why: clip(q.why, 300) };
}

function from<T>(rows: T[] | null | undefined, limit: number, make: (r: T) => Card | null): Card[] {
  const out: Card[] = [];
  for (const r of (rows ?? []).slice(0, limit * 2)) {
    try {
      const c = r && typeof r === 'object' ? make(r) : null;
      if (c && c.id && c.title) out.push(c);
    } catch { /* one odd row: skipped */ }
    if (out.length >= limit) break;
  }
  return out;
}
async function cached<T>(key: string): Promise<T | null> {
  try { return (await readCache<T>(key))?.data ?? null; } catch { return null; }
}

export async function phoneCards(day = today()): Promise<Card[]> {
  const cards: Card[] = [];
  const add = async (fn: () => Promise<Card[]>) => { try { cards.push(...(await fn())); } catch { /* left out */ } };
  await Promise.all([
    add(async () => from(researchersFeed(await loadResearchers(), day), 15, (w: any) => ({
      id: `work:${w.id}`, kind: 'work', title: clip(w.title), url: w.url ?? '', sub: clip([w.venue, (w.names ?? []).slice(0, 2).join(', ')].filter(Boolean).join(' · ')),
      at: w.date ?? '', terms: [], source: 'researchers', page: 'researchers:new' }))),
    add(async () => from((await cached<any>('research'))?.rising, 15, (p: any) => ({
      id: `paper:${p.id}`, kind: 'paper', title: clip(p.title), url: p.url ?? '', sub: clip(p.venue), at: p.date ?? '',
      terms: p.match ?? [], source: 'openalex', page: 'papers', facts: { cited: num(p.cited) } }))),
    add(async () => from((await cached<any>('news-discuss'))?.items, 15, (n: any) => ({
      id: `news:${n.id}`, kind: 'news', title: clip(n.title), url: n.url ?? '', sub: clip(n.source), at: String(n.published ?? '').slice(0, 10),
      terms: n.match ?? [], source: String(n.source ?? 'news'), page: 'news:discuss' }))),
    add(async () => from((await cached<any>('headlines'))?.items, 20, (h: any) => ({
      id: `headline:${h.id}`, kind: 'headline', title: clip(h.title), url: h.link ?? '', sub: clip(h.source), at: String(h.published ?? '').slice(0, 10),
      terms: h.match ?? [], source: String(h.source ?? 'headlines'), page: 'news:headlines' }))),
    add(async () => {
      // the lists as last kept, else the ones shipped with the app (curated.loadLists would go online when stale)
      const lists: any = (await cached<any>('curated')) ?? require('../data/curated.json');
      const out: Card[] = [];
      for (const [list, kind, page] of [['jobs', 'job', 'chances:jobs'], ['funding', 'funding', 'chances:funding'], ['conferences', 'conference', 'chances:conferences']] as const) {
        const open = (lists?.[list] ?? []).filter((it: any) => { const d = daysLeft(it, day); return d === null || d >= 0; });
        out.push(...from(open, 12, (it: any) => {
          const left = daysLeft(it, day);
          return { id: `${kind}:${it.id}`, kind, title: clip(it.title), url: it.url ?? '', at: String(it.added ?? it.checked ?? ''),
            sub: clip([it.org, it.place].filter(Boolean).join(' · ')),   // the days left are on the card's ring
            terms: it.keywords ?? [], source: 'curated', page, facts: left === null ? {} : { days: left } };
        }));
      }
      out.push(...from(lists?.highlights, 6, (h: any) => ({
        id: `highlight:${h.id}`, kind: 'highlight', title: clip(h.title), url: h.url ?? '', sub: clip(h.hook, 160), at: String(h.added ?? ''),
        terms: [...(h.keywords ?? []), ...(h.skills ?? [])], source: 'highlights', page: 'grow:highlights' })));
      return out;
    }),
    add(async () => from((await loadRadar()).items, 12, (d: any) => ({
      id: `dataset:${d.id}`, kind: 'dataset', title: clip(d.title), url: d.url ?? '', sub: clip([d.source, d.term].filter(Boolean).join(' · ')),
      at: String(d.found ?? d.date ?? ''), terms: d.term ? [d.term] : [], source: String(d.source ?? 'datasets'), page: 'grow:data:new',
      facts: { size_mb: num(d.size_mb), license: clip(d.license, 20) } }))),
    add(async () => from((await cached<any>('repos-contribute'))?.contribute, 12, (r: any) => ({
      id: `repo:${r.full_name}`, kind: 'repo', title: clip(r.full_name), url: r.repo_url ?? '', sub: clip(r.description, 160),
      at: String(r.pushed_at ?? r.timestamp ?? '').slice(0, 10), terms: r.topics ?? [], source: 'github', page: 'repos:help',
      facts: { stars: num(r.stars), lang: clip(r.language, 20), starters: Array.isArray(r.starter_issues) ? r.starter_issues.length : 0 } }))),
    add(async () => from((await cached<any>('market-board'))?.rows, 10, (r: any) => ({
      id: `rising:${r.repo}`, kind: 'rising', title: clip(r.repo), url: r.url ?? '', sub: clip(r.description, 160),
      at: String(r.pushed_at ?? '').slice(0, 10), terms: r.language ? [r.language] : [], source: 'market', page: 'repos:rising',
      facts: { stars: num(r.stars), stars_week: num(r.stars_week), lang: clip(r.language, 20) } }))),
    add(async () => from((await cached<any>('people'))?.field, 10, (p: any) => ({
      id: `person:${p.login}`, kind: 'person', title: clip(p.login), url: `https://github.com/${encodeURIComponent(p.login)}`,
      sub: clip(p.why, 160), at: day, terms: [], source: 'people', page: 'people' }))),
    add(async () => from((await cached<any>('models'))?.field, 8, (m: any) => ({
      id: `model:${m.id}`, kind: 'model', title: clip(m.id), url: m.url ?? '', sub: clip(m.pipeline), at: String(m.created ?? ''),
      terms: (m.match?.length ? m.match : m.tags ?? []).slice(0, 8), source: 'huggingface', page: 'models',
      facts: { downloads: num(m.downloads), likes: num(m.likes) } }))),
    add(async () => {
      const qs = ((await bank()) as any)?.questions?.filter((q: any) => q && q.q) ?? [];
      if (!qs.length) return [];
      const dayN = Math.floor(Date.parse(`${day}T00:00:00Z`) / 86400000) + 719163;          // the same day number as Python's toordinal()
      return [0, 1].map((i) => {
        const q = qs[(dayN * 7 + i * 13) % qs.length];
        return { id: `quiz:${q.id ?? i}:${day}`, kind: 'quiz', title: clip(q.q, 220), sub: clip(q.protocol), url: '', at: day,
          terms: [String(q.protocol ?? '')], source: 'quiz', page: 'grow:quiz', facts: quizFacts(q) };
      });
    }),
  ]);
  const seen = new Set<string>();
  return cards.filter((c) => (seen.has(c.id) ? false : (seen.add(c.id), true)));
}

/** The Home feed, ready to show (feed.build): your weights, what it learned, what you've seen. */
export async function buildFeed(weights: Record<string, number>, n = 90) {
  const [cards, state] = await Promise.all([phoneCards(), loadFeed()]);
  return arrange(cards, { today: today(), weights, seen: state.seen, stats: state.stats }, n);
}
