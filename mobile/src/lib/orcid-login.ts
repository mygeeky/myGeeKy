// Sign in with ORCID: proves which ORCID iD is yours, with no myGeeKy server. ORCID's
// "implicit" sign-in needs no secret (the app is open source). ORCID only returns to a
// registered https page, https://mygeeky.org/orcid/, which hands the answer to this app
// (mygeeky://orcid). The answer is a 10-minute token that can only say who you are: the
// app asks ORCID once whose it is, keeps the iD and name, and forgets the token.
import * as Crypto from 'expo-crypto';
import * as WebBrowser from 'expo-web-browser';
import { fetchT } from './net';

// The public ORCID API client registered for myGeeKy ('' hides the button).
export const ORCID_CLIENT_ID: string = 'APP-18BCI2EHRCBFQ3O7';
const RELAY = 'https://mygeeky.org/orcid/';
const BACK = 'mygeeky://orcid';

export const orcidSignInAvailable = () => ORCID_CLIENT_ID !== '';

/** ORCID's last character is a check digit (ISO 7064 11,2): catches most typos. */
export function orcidChecksumOk(id: string): boolean {
  if (!/^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(id)) return false;
  const digits = id.replace(/-/g, '');
  let total = 0;
  for (const ch of digits.slice(0, -1)) total = (total + Number(ch)) * 2;
  const check = (12 - (total % 11)) % 11;
  return digits.slice(-1) === (check === 10 ? 'X' : String(check));
}

export function authorizeUrl(state: string, nonce: string): string {
  const q = new URLSearchParams({
    client_id: ORCID_CLIENT_ID, response_type: 'token', scope: 'openid', redirect_uri: RELAY, state, nonce,
  });
  return `https://orcid.org/oauth/authorize?${q}`;
}

/** What came back to mygeeky://orcid?..., as a plain object. */
export function answerOf(url: string): Record<string, string> {
  const query = url.includes('?') ? url.slice(url.indexOf('?') + 1).split('#')[0] : '';
  return Object.fromEntries(new URLSearchParams(query).entries());
}

export type OrcidMe = { orcid: string; name: string };

export async function whoOnOrcid(token: string): Promise<OrcidMe> {
  const r = await fetchT('https://orcid.org/oauth/userinfo', {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
  });
  if (!r.ok) throw new Error("ORCID didn't confirm the sign-in. Try again.");
  const d = await r.json();
  const orcid = String(d.sub ?? '');
  if (!orcidChecksumOk(orcid)) throw new Error("ORCID answered with something that isn't an ORCID iD.");
  const name = String(d.name ?? [d.given_name, d.family_name].filter(Boolean).join(' '));
  return { orcid, name: name.trim() };
}

const randomText = () => Crypto.randomUUID().replace(/-/g, '');

/** Opens ORCID in an in-app browser and waits for it to come back. */
export async function signInWithOrcid(): Promise<OrcidMe> {
  if (!orcidSignInAvailable()) throw new Error("Sign in with ORCID isn't set up in this version. Type your iD instead.");
  const state = `p-${randomText()}`;
  const result = await WebBrowser.openAuthSessionAsync(authorizeUrl(state, randomText()), BACK);
  if (result.type !== 'success') throw new Error('The sign-in was closed before it finished.');
  const answer = answerOf(result.url);
  if (answer.state !== state) throw new Error("That answer wasn't for this sign-in. Try again.");
  if (!answer.access_token) {
    throw new Error(answer.error === 'access_denied' ? 'You cancelled the sign-in on ORCID.'
      : answer.error_description || "ORCID didn't sign you in. Try again.");
  }
  return whoOnOrcid(answer.access_token);
}
