// 📰 News → Papers & discussions, as on the desktop (src/mygeeky/news.py): new preprints and discussions
// matching your interests, from free, open sources with no keys -- arXiv, bioRxiv and Hacker News (Algolia).
// Ranked by how well each matches you and how new it is; a share of the list is "new territory" (today's
// exploration terms and the Hacker News front page). Only your search terms are sent to these services.
// Everything that comes back is someone else's text: size-capped, shown as plain text, links rebuilt from ids.
import { XMLParser } from 'fast-xml-parser';
import { exploreTerms, match, mix, STOPWORDS, type Weights } from './interests';
import { fetchT } from './net';

export type NewsItem = {
  source: 'arxiv' | 'biorxiv' | 'hackernews'; id: string; title: string; summary: string; published: string;
  url: string; story_url?: string; category?: string; score: number; match: string[]; explore?: boolean;
};
export const NEWS_BADGES: Record<NewsItem['source'], [string, string]> = {
  arxiv: ['arXiv', '#b31b1b'], biorxiv: ['bioRxiv', '#bd2736'], hackernews: ['HN', '#ff6600'],
};

const DAYS = 7;                  // config.news_days
const SIZE = 25;                 // config.news_size
const ARXIV_ID = /^\d{4}\.\d{4,5}(v\d+)?$|^[a-z-]+(\.[A-Z]{2})?\/\d{7}(v\d+)?$/;
const DOI = /^10\.\d{4,9}\/[\w.-]+$/;
const clip = (v: unknown, n: number) => String(v ?? '').split(/\s+/).filter(Boolean).join(' ').slice(0, n);
const when = (v: unknown) => { const t = Date.parse(String(v ?? '')); return Number.isNaN(t) ? '' : new Date(t).toISOString(); };
const parser = new XMLParser({ ignoreAttributes: true, processEntities: true });

async function json(url: string): Promise<any> {
  const r = await fetchT(url);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

export async function fetchArxiv(terms: string[], max = 40): Promise<Omit<NewsItem, 'score' | 'match'>[]> {
  if (!terms.length) return [];
  const query = terms.slice(0, 6).map((t) => (t.includes(' ') ? `all:"${t}"` : `all:${t}`)).join(' OR ');
  const r = await fetchT(`https://export.arxiv.org/api/query?${new URLSearchParams({ search_query: query, sortBy: 'submittedDate',
    sortOrder: 'descending', max_results: String(max) })}`);
  if (!r.ok) throw new Error(String(r.status));
  const feed = parser.parse(await r.text())?.feed;
  const entries = Array.isArray(feed?.entry) ? feed.entry : feed?.entry ? [feed.entry] : [];
  return entries.flatMap((e: any) => {
    const id = String(e?.id ?? '').split('/abs/').pop() ?? '';
    return ARXIV_ID.test(id) ? [{ source: 'arxiv' as const, id: `arxiv:${id}`, title: clip(e.title, 220), summary: clip(e.summary, 400),
      published: when(e.published), url: `https://arxiv.org/abs/${id}` }] : [];
  });
}

export async function fetchBiorxiv(days = DAYS, pages = 3): Promise<Omit<NewsItem, 'score' | 'match'>[]> {
  const end = new Date();
  const start = new Date(end.getTime() - Math.min(days, 3) * 86400000);   // hundreds a day: the last few are plenty
  const day = (d: Date) => d.toISOString().slice(0, 10);
  const out: Omit<NewsItem, 'score' | 'match'>[] = [];
  for (let cursor = 0; cursor < pages * 100; cursor += 100) {
    const items = (await json(`https://api.biorxiv.org/details/biorxiv/${day(start)}/${day(end)}/${cursor}/json`))?.collection ?? [];
    for (const it of Array.isArray(items) ? items : []) {
      const doi = String(it?.doi ?? '');
      if (!DOI.test(doi)) continue;
      const v = /^\d+$/.test(String(it.version ?? '')) ? String(it.version) : '1';
      out.push({ source: 'biorxiv', id: `biorxiv:${doi}`, title: clip(it.title, 220), summary: clip(it.abstract, 400),
        published: when(it.date), url: `https://www.biorxiv.org/content/${doi}v${v}`, category: clip(it.category, 60) });
    }
    if (!Array.isArray(items) || items.length < 100) break;
  }
  return out;
}

const hnItems = (hits: any[]): Omit<NewsItem, 'score' | 'match'>[] => (Array.isArray(hits) ? hits : []).flatMap((h) => {
  const oid = String(h?.objectID ?? '');
  if (!/^\d+$/.test(oid) || !h.title) return [];
  return [{ source: 'hackernews' as const, id: `hn:${oid}`, title: clip(h.title, 220),
    summary: `${Math.trunc(Number(h.points) || 0)} points · ${Math.trunc(Number(h.num_comments) || 0)} comments`,
    published: when(h.created_at), url: `https://news.ycombinator.com/item?id=${oid}`,
    story_url: String(h.url ?? '').startsWith('https://') ? clip(h.url, 300) : '' }];
});

export async function fetchHackernews(terms: string[], days = DAYS): Promise<Omit<NewsItem, 'score' | 'match'>[]> {
  const since = Math.floor((Date.now() - days * 86400000) / 1000);
  const out: Omit<NewsItem, 'score' | 'match'>[] = [];
  for (const term of terms.slice(0, 3)) {
    out.push(...hnItems((await json(`https://hn.algolia.com/api/v1/search_by_date?${new URLSearchParams({ query: term, tags: 'story',
      numericFilters: `points>10,created_at_i>${since}` })}`))?.hits));
  }
  return out;
}

const fetchHnFront = async () => hnItems((await json('https://hn.algolia.com/api/v1/search?tags=front_page'))?.hits);

/** news.rank: relevance to your interests, faded by age (half a point every ~4 days). */
export function rank(items: Omit<NewsItem, 'score' | 'match'>[], weights: Weights, now = Date.now()): NewsItem[] {
  const seen = new Set<string>();
  const out: NewsItem[] = [];
  for (const it of items) {
    if (seen.has(it.id)) continue;
    seen.add(it.id);
    let [relevance, matched] = match(`${it.title} ${it.summary}`, weights);
    if (matched.length < 2 && !matched.some((m) => m.includes(' '))) relevance *= 0.2;   // one generic word isn't evidence
    const t = Date.parse(it.published);
    const age = Number.isNaN(t) ? 7 : Math.max((now - t) / 86400000, 0);
    out.push({ ...it, score: Math.round(relevance * Math.exp(-age / 6) * 10000) / 10000, match: matched });
  }
  return out.sort((a, b) => b.score - a.score);
}

/** news.search_terms: your strongest, most specific interests -- phrases first, then a couple of words. */
export function searchTerms(weights: Weights, n = 6): string[] {
  const ok = Object.keys(weights).filter((t) => t.length >= 4 && !STOPWORDS.has(t));
  const by = (a: string, b: string) => weights[b] - weights[a];
  return [...ok.filter((t) => t.includes(' ')).sort(by).slice(0, n - 2), ...ok.filter((t) => !t.includes(' ')).sort(by)].slice(0, n);
}

/** news.refresh: one source down never empties the feed. */
export async function fetchNews(weights: Weights, share = 0.2): Promise<{ items: NewsItem[]; errors: string[] }> {
  const terms = searchTerms(weights);
  const explore = exploreTerms(weights, 2);
  const errors: string[] = [];
  const attempt = async <T,>(name: string, fn: () => Promise<T[]>): Promise<T[]> => {
    try { return await fn(); } catch { errors.push(name); return []; }
  };
  const [arxiv, arxivExplore, biorxiv, hn, front] = await Promise.all([
    attempt('arXiv', () => fetchArxiv(terms)), attempt('arXiv', () => fetchArxiv(explore, 10)), attempt('bioRxiv', () => fetchBiorxiv()),
    attempt('Hacker News', () => fetchHackernews(terms)), attempt('Hacker News', fetchHnFront),
  ]);
  const ranked = rank([...arxiv, ...biorxiv, ...hn], weights).filter((x) => x.score > 0);
  const have = new Set(ranked.map((r) => r.id));
  const pool = rank([...arxivExplore, ...front], Object.fromEntries(explore.map((t) => [t, 1]))).filter((x) => !have.has(x.id));
  return { items: mix(ranked, SIZE, share, pool), errors: [...new Set(errors)] };
}
