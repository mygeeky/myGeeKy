// 📈 Rising: the desktop's market board (src/mygeeky/market.py) -- a "stock race" of the popular, active repos
// in your field, ranked by momentum: stars gained, commits, PyPI downloads and how those are trending. Your
// computers collect it (daily snapshots, commit activity, PyPI downloads) into market.json, synced to your
// private data repo; the phone ranks it here exactly as compute_board does.
import { readRepoFile } from './model-repo';

export type BoardRow = {
  repo: string; url: string; avatar: string; description: string; language: string; stars: number;
  stars_week: number | null; commits_4w: number | null; pypi: string | null; downloads_week: number | null;
  downloads_change: number | null; spark: number[]; spark_kind: 'downloads' | 'commits'; trend: 'up' | 'down' | null;
  score: number; rank: number; movement: number | 'new' | null;
};

const WEIGHTS: Record<string, number> = { stars_week: 0.25, commits_4w: 0.25, downloads_week: 0.2, downloads_change: 0.15, stars: 0.15 };
const NAME = /^[A-Za-z0-9-]{1,39}\/[A-Za-z0-9._-]{1,100}$/;
const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
const pairs = (v: unknown): [string, number][] =>
  (Array.isArray(v) ? v : []).filter((p) => Array.isArray(p) && typeof p[0] === 'string' && typeof p[1] === 'number').map((p) => [p[0], p[1]]);
const sum = (a: number[]) => a.reduce((x, y) => x + y, 0);

function starsWeek(stars: [string, number][]): number | null {   // market._stars_week
  if (stars.length < 2) return null;
  const latest = Date.parse(`${stars[stars.length - 1][0]}T00:00:00Z`);
  let base = stars[0];
  for (const s of stars) if (Date.parse(`${s[0]}T00:00:00Z`) >= latest - 7 * 86400000) { base = s; break; }
  if (base[0] === stars[stars.length - 1][0]) base = stars[stars.length - 2];
  return stars[stars.length - 1][1] - base[1];
}

function percentiles(values: Map<string, number>): Map<string, number> {   // market._percentiles
  const ordered = [...values.values()].sort((a, b) => a - b);
  const n = ordered.length;
  const out = new Map<string, number>();
  for (const [k, v] of values) out.set(k, n === 1 ? 1 : ordered.filter((x) => x < v).length / (n - 1));
  return out;
}

const signal = (r: BoardRow, metric: string): number | null => {   // market._signal
  const v = (r as unknown as Record<string, number | null>)[metric];
  if (v === null || v === undefined) return null;
  return ['stars', 'downloads_week', 'commits_4w', 'stars_week'].includes(metric) ? Math.log1p(Math.max(v, 0)) : v;
};

/** market.compute_board: the ranked rows, best momentum first, with movement since the last day ranked. */
export function computeBoard(state: any): BoardRow[] {
  const rows: BoardRow[] = [];
  const pypi = state?.pypi && typeof state.pypi === 'object' ? state.pypi : {};
  const repos = state?.repos && typeof state.repos === 'object' ? state.repos : {};
  for (const full of Array.isArray(state?.watchlist) ? state.watchlist : []) {
    const e = typeof full === 'string' && NAME.test(full) ? repos[full] : null;
    const stars = pairs(e?.stars);
    if (!e || !stars.length) continue;
    const weeks: number[] = (Array.isArray(e.commit_weeks) ? e.commit_weeks : []).map(num);
    const downloads = pairs(e.downloads).map((d) => d[1]);
    const week = downloads.length >= 7 ? sum(downloads.slice(-7)) : null;
    const prevWeek = downloads.length >= 14 ? sum(downloads.slice(-14, -7)) : null;
    const change = week !== null && prevWeek ? (week - prevWeek) / prevWeek : null;
    const commitsPrev = weeks.length >= 8 ? sum(weeks.slice(-8, -4)) : null;
    let spark: number[]; let kind: BoardRow['spark_kind']; let trend: BoardRow['trend'];
    if (downloads.length) {
      const weekly: number[] = [];
      for (let i = downloads.length; i > 0; i -= 7) weekly.push(sum(downloads.slice(Math.max(0, i - 7), i)));
      spark = weekly.slice(0, 12).reverse(); kind = 'downloads';
      trend = change === null ? null : change >= 0 ? 'up' : 'down';
    } else {
      spark = weeks.slice(-12); kind = 'commits';
      const recent = weeks.length ? sum(weeks.slice(-4)) : null;
      trend = recent === null || commitsPrev === null || recent === commitsPrev ? null : recent > commitsPrev ? 'up' : 'down';
    }
    const str = (v: unknown, n: number) => (typeof v === 'string' ? v.slice(0, n) : '');
    rows.push({
      repo: full, url: /^https:\/\/github\.com\//.test(str(e.url, 300)) ? e.url : `https://github.com/${full}`,
      avatar: /^https:\/\/avatars\.githubusercontent\.com\//.test(str(e.avatar, 300)) ? e.avatar : '',
      description: str(e.description, 300), language: str(e.language, 30), stars: stars[stars.length - 1][1],
      stars_week: starsWeek(stars), commits_4w: weeks.length ? sum(weeks.slice(-4)) : null,
      pypi: typeof pypi[full] === 'string' ? pypi[full] : null, downloads_week: week, downloads_change: change,
      spark, spark_kind: kind, trend, score: 0, rank: 0, movement: null,
    });
  }
  const pct = Object.fromEntries(Object.keys(WEIGHTS).map((m) => {
    const vals = new Map<string, number>();
    for (const r of rows) { const s = signal(r, m); if (s !== null) vals.set(r.repo, s); }
    return [m, percentiles(vals)];
  }));
  for (const r of rows) {
    const have = Object.keys(WEIGHTS).filter((m) => pct[m].has(r.repo));
    const total = sum(have.map((m) => WEIGHTS[m])) || 1;
    r.score = Math.round((sum(have.map((m) => WEIGHTS[m] * pct[m].get(r.repo)!)) / total) * 10000) / 10000;
  }
  rows.sort((a, b) => b.score - a.score);    // stable, as Python's sort
  const history = state?.rank_history && typeof state.rank_history === 'object' ? state.rank_history : {};
  const today = typeof state?.snapshot_date === 'string' ? state.snapshot_date : new Date().toISOString().slice(0, 10);
  const earlier = Object.keys(history).filter((d) => d < today).sort();
  const previous: string[] | null = earlier.length && Array.isArray(history[earlier[earlier.length - 1]]) ? history[earlier[earlier.length - 1]] : null;
  rows.forEach((r, i) => {
    r.rank = i + 1;
    r.movement = previous === null ? null : previous.includes(r.repo) ? previous.indexOf(r.repo) + 1 - r.rank : 'new';
  });
  return rows;
}

/** The board from your data repo; null when not connected or nothing collected yet. */
export async function loadBoard(): Promise<{ rows: BoardRow[]; updatedAt: string } | null> {
  const text = await readRepoFile('market.json');
  if (!text) return null;
  try {
    const state = JSON.parse(text);
    return { rows: computeBoard(state), updatedAt: typeof state.updated_at === 'string' ? state.updated_at : '' };
  } catch {
    return null;
  }
}
