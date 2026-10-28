// Badges, as on the desktop: myGeeKy's own (bronze/silver/gold, from what you
// do in the app -- only the KIND of thing you open is counted, never titles or
// links), plus your GitHub achievements read from your public profile.
import { fetchT } from './net';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { queueUsage } from './model-repo';
import { isStale, readCache, writeCache } from './storage';

const USAGE_KEY = 'mygeeky.usage';
export const TIERS = ['bronze', 'silver', 'gold'] as const;
export const TIER_COLORS: Record<string, string> = { bronze: '#cd7f32', silver: '#c0c7d4', gold: '#ffd24a' };

// id: [emoji, name, what it counts, thresholds]
const BADGES: Record<string, [string, string, string, number[]]> = {
  active: ['🔥', 'Regular', "days you've opened myGeeKy", [3, 14, 60]],
  clicker: ['🖱️', 'Clicker', "things you've opened from myGeeKy", [10, 50, 200]],
  reader: ['📰', 'News Reader', "headlines and news you've read", [10, 50, 200]],
  analyst: ['📊', 'Analyst', "papers you've opened", [5, 25, 100]],
  ai: ['🤖', 'AI Fan', "AI headlines and models you've opened", [5, 25, 100]],
  models: ['🤗', 'Model Hunter', "Hugging Face models you've opened", [3, 15, 50]],
  explorer: ['🔭', 'Explorer', 'things you opened from outside your usual interests', [3, 15, 50]],
  wordsmith: ['🔤', 'Wordsmith', "keywords you've set", [3, 8, 15]],
  early: ['🌱', 'Early Adopter', 'joined myGeeKy before 2027', [1]],
  // Play with GeeKOc (gems.badgeCounts): this phone's rounds, or your computers' and this phone's together
  player: ['🎮', 'Player', "game rounds you've played", [3, 25, 100]],
  sharp: ['🎯', 'Sharp', 'right answers in games', [25, 200, 800]],
  levelup: ['🆙', 'Level Up', "game levels you've gained", [3, 15, 40]],
  // earned on your computer (they come along with "Connect your phone")
  networker: ['🤝', 'Networker', "people you've followed", [1, 10, 30]],
  stargazer: ['⭐', 'Stargazer', "repos you've starred", [1, 10, 50]],
  builder: ['🛠️', 'Builder', "repos you've forked to contribute", [1, 5, 20]],
  grateful: ['🙏', 'Grateful', "signals you've sent", [1, 5, 20]],
  ideas: ['💡', 'Idea Giver', "ideas and problems you've sent", [1, 3, 10]],
  everywhere: ['☁️', 'Everywhere', 'computers in sync', [1]],
};

type Usage = { days: string[]; clicks: { kind: string; cat?: string; explore?: boolean }[]; first: string };

async function load(): Promise<Usage> {
  try {
    const raw = await AsyncStorage.getItem(USAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* fresh */
  }
  return { days: [], clicks: [], first: new Date().toISOString() };
}

let queue = Promise.resolve();
function update(fn: (u: Usage) => void) {
  queue = queue.then(async () => {
    const u = await load();
    fn(u);
    u.clicks = u.clicks.slice(-2000);
    await AsyncStorage.setItem(USAGE_KEY, JSON.stringify(u));
  }).catch(() => undefined);
}

export function logOpenToday() {
  const day = new Date().toISOString().slice(0, 10);
  update((u) => {
    if (!u.days.includes(day)) {
      u.days.push(day);
      queueUsage({ what: 'open' });       // your computers count it too, once your data repo is connected
    }
  });
}

/** kind: headline | news | paper | model | repo | person | launch */
export function logClick(kind: string, cat?: string, explore?: boolean) {
  update((u) => u.clicks.push({ kind, cat, explore }));
  queueUsage({ what: 'click', kind, cat, explore });
}

/** Something you did, for My month and your rank (month.ts): a usage line, never what it was. */
export function logDid(what: 'idea' | 'step' | 'build' | 'share' | 'quiz' | 'skill' | 'chance') {
  queueUsage({ what });
}

export type Earned = { id: string; emoji: string; name: string; what: string; count: number; tier: string; next: number | null };

/** Every badge, at the best tier earned here or on your computer. With your data repo connected,
 *  `fromRepo` holds the desktop's own counts (your computers and this phone together). */
export async function earned(keywords: number, desktop: string[] = [], fromRepo?: Record<string, number>,
                             games: Record<string, number> = {}): Promise<Earned[]> {
  const fromDesktop: Record<string, number> = {};
  for (const b of desktop) {
    const [id, tier] = b.split(':');
    fromDesktop[id] = Math.max(fromDesktop[id] ?? 0, TIERS.indexOf(tier as typeof TIERS[number]) + 1);
  }
  const u = await load();
  const k = (x: string) => u.clicks.filter((c) => c.kind === x).length;
  const counts: Record<string, number> = fromRepo ? { ...fromRepo } : {
    active: u.days.length, clicker: u.clicks.length, reader: k('headline') + k('news'), analyst: k('paper'),
    ai: u.clicks.filter((c) => c.cat === 'ai' || c.kind === 'model').length, models: k('model'),
    explorer: u.clicks.filter((c) => c.explore).length, wordsmith: keywords, early: u.first < '2027-01-01' ? 1 : 0,
  };
  for (const [id, n] of Object.entries(games)) counts[id] = Math.max(counts[id] ?? 0, n);   // games played here
  return Object.entries(BADGES).map(([id, [emoji, name, what, levels]]) => {
    const n = counts[id] ?? 0;
    const reached = Math.max(levels.filter((need) => n >= need).length, fromDesktop[id] ?? 0);
    return { id, emoji, name, what, count: n, tier: reached ? TIERS[reached - 1] : '', next: levels.find((need) => n < need) ?? null };
  });
}

export type Achievement = { name: string; image: string };

const ACH = /<img[^>]*alt="Achievement: ([^"]{1,60})"[^>]*src="(https:\/\/github\.githubassets\.com\/assets\/[a-z0-9-]{1,80}\.png)"/gi;
const ACH_REV = /<img[^>]*src="(https:\/\/github\.githubassets\.com\/assets\/[a-z0-9-]{1,80}\.png)"[^>]*alt="Achievement: ([^"]{1,60})"/gi;

export function parseAchievements(html: string): Achievement[] {
  const found = new Map<string, string>();
  for (const m of html.matchAll(ACH)) if (!found.has(m[1].trim())) found.set(m[1].trim(), m[2]);
  for (const m of html.matchAll(ACH_REV)) if (!found.has(m[2].trim())) found.set(m[2].trim(), m[1]);
  return [...found].map(([name, image]) => ({ name, image }));
}

/** Read from your public GitHub profile at most once a week (GitHub has no API for them). */
export async function githubAchievements(user: string): Promise<Achievement[]> {
  const cached = await readCache<{ user: string; items: Achievement[] }>('achievements');
  if (cached && cached.data.user === user && !isStale(cached.at, 24 * 7)) return cached.data.items;
  try {
    const r = await fetchT(`https://github.com/${user}?tab=achievements`);
    const items = r.ok ? parseAchievements(await r.text()) : cached?.data.items ?? [];
    await writeCache('achievements', { user, items });
    return items;
  } catch {
    return cached?.data.items ?? [];
  }
}
