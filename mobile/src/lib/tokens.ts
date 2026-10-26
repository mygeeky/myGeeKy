// When do this phone's GitHub tokens expire? As the desktop does it (src/mygeeky/tokens.py): GitHub sends a
// token's expiry with every reply (github-authentication-token-expiration), so one call to /rate_limit --
// which doesn't count against the limit -- tells it. Checked at most once a day; only dates are kept, never
// the tokens. From WARN_DAYS before, the phone says so, before Signals or your model quietly stop working.
// (The GitHub sign-in renews itself, so it is not checked here.)
import AsyncStorage from '@react-native-async-storage/async-storage';
import { savedWhere } from './data-store';
import { modelLink } from './model-repo';
import { fetchT } from './net';
import { signalsToken } from './signals';

const KEY = 'mygeeky.tokencheck';
export const WARN_DAYS = 7;
export const SETTINGS_URL = 'https://github.com/settings/personal-access-tokens';

export type TokenState = { name: 'signals' | 'data'; label: string; state: 'ok' | 'expired' | 'unreachable';
  expiresAt: string | null; warn: boolean; message: string };

/** tokens.parse_expiry: '2026-10-18 04:23:30 UTC' or with a +hhmm offset. */
export function parseExpiry(v: string | null): Date | null {
  if (!v) return null;
  const m = v.trim().match(/^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) (UTC|[+-]\d{4})$/);
  if (!m) return null;
  const off = m[3] === 'UTC' ? 'Z' : `${m[3].slice(0, 3)}:${m[3].slice(3)}`;
  const d = new Date(`${m[1]}T${m[2]}${off}`);
  return Number.isNaN(d.getTime()) ? null : d;
}

async function probe(token: string): Promise<Pick<TokenState, 'state' | 'expiresAt'>> {
  try {
    const r = await fetchT('https://api.github.com/rate_limit', { headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' } });
    if (r.status === 401) return { state: 'expired', expiresAt: null };   // expired, revoked or mistyped
    return { state: 'ok', expiresAt: parseExpiry(r.headers.get('github-authentication-token-expiration'))?.toISOString() ?? null };
  } catch {
    return { state: 'unreachable', expiresAt: null };
  }
}

/** tokens.describe, with what to do on the phone. */
export function describe(name: TokenState['name'], p: Pick<TokenState, 'state' | 'expiresAt'>, now = Date.now()): TokenState {
  const label = name === 'signals' ? 'Your Signals token' : 'Your data repo token';
  const where = name === 'signals' ? 'Signals' : 'You → Model';
  const base = { name, label, ...p, warn: false };
  if (p.state === 'expired') return { ...base, warn: true, message: `${label} has expired or was revoked. Make a new one on GitHub and paste it in ${where}.` };
  if (p.state === 'unreachable') return { ...base, message: `${label}: couldn't reach GitHub to check it.` };
  if (!p.expiresAt) return { ...base, message: `${label} never expires.` };
  const days = (Date.parse(p.expiresAt) - now) / 86400000;
  const when = new Date(p.expiresAt).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' });
  if (days < 0) return { ...base, warn: true, message: `${label} expired on ${when}. Make a new one and paste it in ${where}.` };
  if (days <= WARN_DAYS) {
    const left = days < 1 ? 'today' : `in ${Math.trunc(days)} day${Math.trunc(days) === 1 ? '' : 's'}`;
    return { ...base, warn: true, message: `${label} expires ${left} (${when}). On GitHub, open it and click Regenerate token, then paste it in ${where}.` };
  }
  return { ...base, message: `${label} expires on ${when} (${Math.trunc(days)} days left).` };
}

/** Both tokens this phone has, checked at most once a day (`force` checks now). */
export async function checkTokens(force = false): Promise<TokenState[]> {
  try {
    const cached = JSON.parse((await AsyncStorage.getItem(KEY)) ?? 'null');
    if (!force && cached && Date.now() - Date.parse(cached.at) < 86400000 && Array.isArray(cached.found)) {
      return cached.found.map((f: any) => describe(f.name, f));      // the dates again, the days left fresh
    }
  } catch { /* check again */ }
  const [sig, link] = await Promise.all([signalsToken().catch(() => null),
    savedWhere().then((w) => (w === 'drive' ? null : modelLink())).catch(() => null)]);   // Google Drive has no token to renew
  const found: (Pick<TokenState, 'state' | 'expiresAt'> & { name: TokenState['name'] })[] = [];
  if (sig) found.push({ name: 'signals', ...(await probe(sig)) });
  if (link) found.push({ name: 'data', ...(await probe(link.token)) });
  try { await AsyncStorage.setItem(KEY, JSON.stringify({ at: new Date().toISOString(), found })); } catch { /* fine */ }
  return found.map((f) => describe(f.name, f));
}
