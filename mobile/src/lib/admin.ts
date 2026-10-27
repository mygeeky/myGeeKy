// The maker's admin part, on the phone (src/mygeeky/admin.py `summary`): an overview, nothing more. Downloads, stars,
// what's waiting and what TRACE noticed this week, as numbers (components/admin-part.tsx). Reviewing, publishing,
// support email, passwords and keys all stay on the computer's Admin console.
//
// What keeps it the maker's:
//   * it shows only when GitHub says the account this phone signed in with is in ADMINS -- a username typed into the
//     app proves nothing, and it works whether your data is saved in Google Drive or a repo;
//   * what it shows comes from admin_summary.json, which your computer writes into your own saved data with counts
//     only: no names, no email addresses, no messages;
//   * it writes nothing, anywhere.
import { getToken } from './storage';
import { fetchT } from './net';
import { readRepoFile } from './model-repo';

export const ADMINS = new Set(['alsammanalsamman']);
const FILE = 'admin_summary.json';

export type Summary = {
  updatedAt: string;
  adoption: Record<'pypi_week' | 'pypi_month' | 'installer_downloads' | 'stars' | 'forks' | 'signals_users', number | null>;
  waiting: Record<'listings' | 'news' | 'highlights' | 'quiz_batches' | 'support' | 'ideas' | 'keywords' | 'ready_to_publish', number>;
  invites: Record<'new' | 'invited' | 'joined' | 'declined', number>;
  trace: { triggersWeek: number; acceptedWeek: number; rising: string[]; spentToday: number; perDay: number };
  lastPublish: string;
};

let verified: string | null = null;            // a yes is kept for this app run; a no is asked again next time

/** The admin account this phone is signed in with (GitHub says who it is), or null. */
export async function adminLogin(): Promise<string | null> {
  if (!verified) {
    const token = await getToken();
    if (!token) return null;
    try {
      const r = await fetchT('https://api.github.com/user', { headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}` } });
      const login = r.ok ? String((await r.json())?.login ?? '') : '';
      verified = /^[A-Za-z0-9-]{1,39}$/.test(login) ? login : null;
    } catch {
      verified = null;
    }
  }
  return verified && ADMINS.has(verified.toLowerCase()) ? verified : null;
}

const str = (v: unknown, n = 60) => (typeof v === 'string' ? v.slice(0, n) : '');
const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? Math.round(v) : 0);
const numOrNull = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? Math.round(v) : null);

/** admin.summary, checked field by field (it arrives over the network). */
export function cleanSummary(d: any): Summary {
  const pick = <K extends string>(o: any, keys: readonly K[], f: (v: unknown) => any) =>
    Object.fromEntries(keys.map((k) => [k, f(o?.[k])])) as Record<K, any>;
  return {
    updatedAt: str(d?.updated_at, 40),
    adoption: pick(d?.adoption, ['pypi_week', 'pypi_month', 'installer_downloads', 'stars', 'forks', 'signals_users'] as const, numOrNull),
    waiting: pick(d?.waiting, ['listings', 'news', 'highlights', 'quiz_batches', 'support', 'ideas', 'keywords', 'ready_to_publish'] as const, num),
    invites: pick(d?.invites, ['new', 'invited', 'joined', 'declined'] as const, num),
    trace: { triggersWeek: num(d?.trace?.triggers_week), acceptedWeek: num(d?.trace?.accepted_week),
      rising: (Array.isArray(d?.trace?.rising) ? d.trace.rising : []).slice(0, 5).map((x: unknown) => str(x, 40)).filter(Boolean),
      spentToday: num(d?.trace?.spent_today), perDay: num(d?.trace?.per_day) },
    lastPublish: str(d?.last_publish, 40),
  };
}

export async function loadSummary(): Promise<Summary | null> {
  if (!(await adminLogin())) return null;
  const text = await readRepoFile(FILE);
  if (!text) return null;
  try { return cleanSummary(JSON.parse(text)); } catch { return null; }
}
