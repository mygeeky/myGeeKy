// Sign in with GitHub (the device flow) -- the same myGeeKy OAuth app as the
// desktop. No scopes: the token can only read public data. No secret is needed
// (or possible: the app is open source).
import { fetchT } from './net';

export const CLIENT_ID = 'Ov23liNyUzK9THj5uAyH';

export type Flow = { deviceCode: string; userCode: string; uri: string; interval: number; expiresIn: number };

const form = (data: Record<string, string>) =>
  Object.entries(data).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');

async function post(url: string, data: Record<string, string>) {
  const r = await fetchT(url, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form(data),
  });
  return r.json();
}

export async function startLogin(): Promise<Flow> {
  const d = await post('https://github.com/login/device/code', { client_id: CLIENT_ID, scope: '' });
  if (!d.device_code || !d.user_code) throw new Error(d.error_description || "GitHub didn't start the sign-in.");
  return {
    deviceCode: d.device_code, userCode: d.user_code, uri: d.verification_uri || 'https://github.com/login/device',
    interval: Number(d.interval) || 5, expiresIn: Number(d.expires_in) || 900,
  };
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** What GitHub hands back. Since 2026-08-14 a new OAuth app's tokens last 8 hours and come
 *  with a refresh token (6 months, renewed at every use) that keeps the sign-in working. */
export type Grant = { token: string; refresh?: string; expiresIn?: number; refreshExpiresIn?: number };

type TokenAnswer = {
  access_token?: string; refresh_token?: string; expires_in?: number; refresh_token_expires_in?: number;
  error?: string; interval?: number; error_description?: string;
};

const grantOf = (d: TokenAnswer): Grant => ({
  token: d.access_token as string, refresh: d.refresh_token,
  expiresIn: d.expires_in ? Number(d.expires_in) : undefined,
  refreshExpiresIn: d.refresh_token_expires_in ? Number(d.refresh_token_expires_in) : undefined,
});

/** The same, with the refresh token GitHub may send along. */
export async function waitForGrant(flow: Flow, cancelled: () => boolean): Promise<Grant> {
  const deadline = Date.now() + flow.expiresIn * 1000;
  let wait = Math.max(flow.interval, 1);
  while (Date.now() < deadline) {
    await sleep(wait * 1000);
    if (cancelled()) throw new Error('Sign-in cancelled.');
    let d: TokenAnswer;
    try {
      d = await post('https://github.com/login/oauth/access_token', {
        client_id: CLIENT_ID, device_code: flow.deviceCode, grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
      });
    } catch {
      continue;                                       // a network hiccup: try again
    }
    if (d.access_token) return grantOf(d);
    if (d.error === 'authorization_pending') continue;
    if (d.error === 'slow_down') {
      wait = Number(d.interval) || wait + 5;
      continue;
    }
    if (d.error === 'expired_token') throw new Error('The code expired. Tap Sign in again.');
    if (d.error === 'access_denied') throw new Error('You cancelled the sign-in on GitHub.');
    throw new Error(d.error_description || d.error || 'GitHub sign-in failed.');
  }
  throw new Error('The code expired. Tap Sign in again.');
}

/** A new token pair from a refresh token. A device-flow sign-in needs no app secret to do this.
 *  'refused': the refresh token is expired or was replaced (sign in again); null: offline. */
export async function renewGrant(refresh: string): Promise<Grant | 'refused' | null> {
  let d: TokenAnswer;
  try {
    d = await post('https://github.com/login/oauth/access_token', {
      client_id: CLIENT_ID, grant_type: 'refresh_token', refresh_token: refresh,
    });
  } catch {
    return null;
  }
  if (d.access_token) return grantOf(d);
  return d.error === 'bad_refresh_token' || d.error === 'invalid_grant' ? 'refused' : null;
}

export async function whoAmI(token: string): Promise<string> {
  const r = await fetchT('https://api.github.com/user', {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' },
  });
  if (!r.ok) throw new Error("GitHub didn't accept the sign-in. Please try again.");
  return (await r.json()).login;
}
