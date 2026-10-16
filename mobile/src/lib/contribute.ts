// 📦 Repos, as on the desktop: repositories in your field you could fork, improve and get merged
// (src/mygeeky/contribute.py). Finding them is heavy -- a dozen GitHub searches, then each top repo's
// recent outside pull requests and open starter issues -- so the phone does not redo it: your computers
// save every run in contribute_history.jsonl, synced to your private data repo, and the phone shows that
// list the way the desktop's Repos tab does (storage.contribution_pool).
import { readRepoFile } from './model-repo';

export type Contribution = {
  full_name: string; repo_url: string; fork_url: string; owner: string; owner_avatar_url: string; description: string;
  language: string; topics: string[]; stars: number; pushed_at: string; score: number; reasons: string[]; explore: boolean;
  starter_issues: { title: string; url: string; comments: number }[]; timestamp: string;
};

const POOL_DAYS = 90;          // storage.POOL_DAYS: older suggestions are too stale to bring back
const NAME = /^[A-Za-z0-9-]{1,39}\/[A-Za-z0-9._-]{1,100}$/;
const gh = (v: unknown) => (typeof v === 'string' && /^https:\/\/(github\.com|avatars\.githubusercontent\.com)\//.test(v) ? v : '');
const str = (v: unknown, n: number) => (typeof v === 'string' ? v.slice(0, n) : '');

function clean(r: any): Contribution | null {
  if (!r || typeof r !== 'object' || !NAME.test(String(r.full_name ?? ''))) return null;
  const full = r.full_name as string;
  return {
    full_name: full, repo_url: gh(r.repo_url) || `https://github.com/${full}`, fork_url: `https://github.com/${full}/fork`,
    owner: str(r.owner, 39), owner_avatar_url: gh(r.owner_avatar_url), description: str(r.description, 300), language: str(r.language, 30),
    topics: (Array.isArray(r.topics) ? r.topics : []).filter((t: unknown) => typeof t === 'string').slice(0, 20),
    stars: typeof r.stars === 'number' ? r.stars : 0, pushed_at: str(r.pushed_at, 40), score: typeof r.score === 'number' ? r.score : 0,
    reasons: (Array.isArray(r.reasons) ? r.reasons : []).map((x: unknown) => str(x, 160)).filter(Boolean).slice(0, 6),
    explore: r.explore === true, timestamp: str(r.timestamp, 40),
    starter_issues: (Array.isArray(r.starter_issues) ? r.starter_issues : []).filter((i: any) => gh(i?.url))
      .map((i: any) => ({ title: str(i.title, 200), url: i.url, comments: typeof i.comments === 'number' ? i.comments : 0 })).slice(0, 3),
  };
}

/** storage._pool: each repo once (its newest record), from the last 90 days, newest run first; within a run,
 *  the order it was saved in (best first). Null when no data repo is connected or nothing is synced yet. */
export async function loadContributions(limit = 15): Promise<Contribution[] | null> {
  const text = await readRepoFile('contribute_history.jsonl');
  if (text === null) return null;
  const records: Contribution[] = [];
  for (const line of text.split('\n')) {
    try { const c = clean(JSON.parse(line)); if (c) records.push(c); } catch { /* a cut line */ }
  }
  const cutoff = new Date(Date.now() - POOL_DAYS * 86400000).toISOString();
  const seen = new Set<string>();
  const picked: [number, Contribution][] = [];
  for (let i = records.length - 1; i >= 0; i--) {
    const r = records[i];
    const key = r.full_name.toLowerCase();
    if (seen.has(key) || (r.timestamp && r.timestamp < cutoff)) continue;
    seen.add(key);
    picked.push([i, r]);
  }
  const runs = new Map<string, [number, Contribution][]>();
  for (const p of picked) runs.set(p[1].timestamp, [...(runs.get(p[1].timestamp) ?? []), p]);
  return [...runs.keys()].sort().reverse().flatMap((t) => runs.get(t)!.sort((a, b) => a[0] - b[0]).map(([, r]) => r)).slice(0, limit);
}
