// Cards that ask again, gently, for what setup skipped: saving your data (Google Drive recommended, or a GitHub repo),
// your ORCID, GitHub -- the desktop's nudges.py, line for line (tests/test_nudges.py holds both to the same answers).
// Each shows on the pages it would improve, never in the first week, and fades out: first after a week of use (7 days
// you opened myGeeKy); "Not now" -> back after 2 more days of use, once a week of use after the third; it stops two
// months after it first appeared, or at once with "Don't ask again"; at most one kind a day; linked -> never. What it
// remembers stays on this phone (AsyncStorage).
import AsyncStorage from '@react-native-async-storage/async-storage';

export type NudgeKey = 'data' | 'orcid' | 'github';
type Card = { first: string; skips: number; next: number; never: boolean };
export type NudgeState = { days: number; last: string; cards: Partial<Record<NudgeKey, Card>>; today: { date: string; key: string } };

export const KEYS: NudgeKey[] = ['data', 'orcid', 'github'];
export const START = 7, AGAIN = 2, WEEKLY_AFTER = 3, WEEK = 7, GIVE_UP = 60;

export const PLACES: Record<NudgeKey, string[]> = {
  data: ['month', 'model'],
  orcid: ['cited', 'researchers', 'highlights', 'jobs'],
  github: ['repos', 'rising', 'month'],
};
export const PAGE_PLACE: Record<string, string> = {
  'model:month': 'month', 'you:month': 'month', 'model:model': 'model', 'you:model': 'model',
  'model:cited': 'cited', 'you:cited': 'cited', 'grow:highlights': 'highlights', 'chances:jobs': 'jobs',
  repos: 'repos', 'repos:help': 'repos', 'market:repos': 'rising', 'repos:rising': 'rising',
};

export function placeOf(page: string): string {
  if (page === 'researchers' || page.startsWith('researchers:')) return 'researchers';
  return PAGE_PLACE[page] ?? '';
}

export function text(key: NudgeKey, device: string): { title: string; text: string; go: string } {
  if (key === 'data') {
    return { title: 'Keep your progress safe',
      text: `What myGeeKy has learned about you lives only on this ${device}. Save it in your own Google ` +
            'Drive (recommended) or a private GitHub repo: your other devices share it, and nothing is lost ' +
            `if this ${device} is.`,
      go: 'Choose where to save' };
  }
  if (key === 'orcid') {
    return { title: 'Add your ORCID',
      text: 'With your ORCID, myGeeKy finds your papers, shows who cites you, and fits researchers and jobs ' +
            'to your own work.',
      go: 'Add ORCID' };
  }
  return { title: 'Link GitHub',
    text: 'Read-only: myGeeKy sees your repos and activity to suggest projects to help and people to follow. ' +
          'It never posts for you.',
    go: 'Link GitHub' };
}

export const fresh = (): NudgeState => ({ days: 0, last: '', cards: {}, today: { date: '', key: '' } });

const card = (s: NudgeState, key: NudgeKey): Card => (s.cards[key] ??= { first: '', skips: 0, next: 0, never: false });
const between = (a: string, b: string): number => Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86400000);

/** You opened myGeeKy today: a day of use (once a day). */
export function used(s: NudgeState, today: string): void {
  if (s.last !== today) { s.last = today; s.days += 1; }
}

export function due(s: NudgeState, key: NudgeKey, today: string): boolean {
  const c = s.cards[key] ?? { first: '', skips: 0, next: 0, never: false };
  if (c.never || s.days < START || s.days < c.next) return false;
  if (c.first && between(c.first, today) >= GIVE_UP) return false;
  const t = s.today;
  return !(t.date === today && t.key !== '' && t.key !== key);
}

/** The card for this page today, if any (picking it counts as showing it). */
export function pick(s: NudgeState, page: string, today: string, missing: NudgeKey[]): NudgeKey | '' {
  used(s, today);
  const place = placeOf(page);
  for (const key of KEYS) {
    if (missing.includes(key) && PLACES[key].includes(place) && due(s, key, today)) {
      const c = card(s, key);
      c.first = c.first || today;
      s.today = { date: today, key };
      return key;
    }
  }
  return '';
}

/** Not now: back after 2 days of use, or a week of use after the third time. */
export function skip(s: NudgeState, key: NudgeKey): void {
  const c = card(s, key);
  c.skips += 1;
  c.next = s.days + (c.skips < WEEKLY_AFTER ? AGAIN : WEEK);
}

export function never(s: NudgeState, key: NudgeKey): void { card(s, key).never = true; }

// ---- where it's kept: this phone only
const STORE = 'mygeeky.nudges';
export async function load(): Promise<NudgeState> {
  try {
    const s = JSON.parse((await AsyncStorage.getItem(STORE)) ?? 'null');
    return s && typeof s === 'object' && s.cards ? s : fresh();
  } catch { return fresh(); }
}
export const save = (s: NudgeState): Promise<void> => AsyncStorage.setItem(STORE, JSON.stringify(s)).catch(() => undefined);
/** Today as the phone's own date, YYYY-MM-DD (the computer uses date.today()). */
export const today = (): string => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
