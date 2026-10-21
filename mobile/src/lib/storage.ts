// Settings and cached lists live in AsyncStorage; tokens only in the phone's
// secure store (Android Keystore / iOS Keychain). The web preview has no secure
// store, so there (and only there) tokens fall back to the browser's storage.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { type Grant, renewGrant } from './github-login';

export type Settings = {
  username: string;
  orcid: string;
  openalex?: string;          // "Is this you?" (whois.ts): your OpenAlex author id (A...), used without an ORCID
  keywords: string[];
  coauthors?: string[];       // people you've written with, found in a CV you dropped in (doc-read.ts)
  topics: string[];
  exploreShare: number;
  // what your computer learned about you (from "Connect your phone")
  interests: Record<string, number>;
  field: string[];
  desktopBadges: string[];
};

export const DEFAULT_SETTINGS: Settings = {
  username: '', orcid: '', keywords: [], topics: [], exploreShare: 0.2, interests: {}, field: [], desktopBadges: [],
};
const SETTINGS_KEY = 'mygeeky.settings';
const TOKEN_KEY = 'mygeeky_read_token';
const SIGNIN_KEY = 'mygeeky_signin_refresh';      // the refresh token of a "Sign in with GitHub" (secure store)
const RENEW_BEFORE_MS = 10 * 60 * 1000;

export async function loadSettings(): Promise<Settings | null> {
  const raw = await AsyncStorage.getItem(SETTINGS_KEY);
  if (!raw) return null;
  try {
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return null;
  }
}

export async function saveSettings(s: Settings): Promise<void> {
  await AsyncStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
}

export async function getToken(): Promise<string | null> {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(TOKEN_KEY) ?? null;
  try {
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    // after a reinstall or a phone-backup restore the stored token can't be decrypted:
    // forget it and treat the app as signed out, instead of failing on start
    await SecureStore.deleteItemAsync(TOKEN_KEY).catch(() => undefined);
    return null;
  }
}

export async function setToken(token: string | null): Promise<void> {
  if (Platform.OS === 'web') {
    if (token) globalThis.localStorage?.setItem(TOKEN_KEY, token);
    else globalThis.localStorage?.removeItem(TOKEN_KEY);
  } else if (token) await SecureStore.setItemAsync(TOKEN_KEY, token);
  else await SecureStore.deleteItemAsync(TOKEN_KEY);
  if (!token) await saveSignin(null);              // signing out forgets the refresh token too
}

// ---- a free OpenAlex key (WISEP, lib/wisep.ts): the person's own budget instead of the one their network shares
const OPENALEX_KEY = 'mygeeky.openalex.key';
export const getOpenAlexKey = () => readSecure(OPENALEX_KEY);
export const setOpenAlexKey = (key: string | null) => writeSecure(OPENALEX_KEY, key);

// ---- 8-hour sign-in tokens that renew themselves
type SigninRecord = { refresh: string; expiresAt: number; refreshExpiresAt: number };

async function readSecure(key: string): Promise<string | null> {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(key) ?? null;
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    await SecureStore.deleteItemAsync(key).catch(() => undefined);
    return null;
  }
}

async function writeSecure(key: string, value: string | null): Promise<void> {
  if (Platform.OS === 'web') {
    if (value) globalThis.localStorage?.setItem(key, value);
    else globalThis.localStorage?.removeItem(key);
  } else if (value) await SecureStore.setItemAsync(key, value);
  else await SecureStore.deleteItemAsync(key).catch(() => undefined);
}

/** Keep the refresh token of a fresh sign-in (none: a token that doesn't expire). */
export async function saveSignin(grant: Grant | null): Promise<void> {
  if (!grant?.refresh) return writeSecure(SIGNIN_KEY, null);
  const now = Date.now();
  const record: SigninRecord = {
    refresh: grant.refresh, expiresAt: now + (grant.expiresIn ?? 8 * 3600) * 1000,
    refreshExpiresAt: now + (grant.refreshExpiresIn ?? 182 * 86400) * 1000,
  };
  await writeSecure(SIGNIN_KEY, JSON.stringify(record));
}

let renewing: Promise<string | null> | null = null;   // one renewal at a time, however many screens load

// ---- a token GitHub refused (401: expired, revoked, or a sign-in that couldn't renew)
const rejected = new Set<string>();
const listeners = new Set<() => void>();
/** Called when the token was refused and forgotten: the app shows "Sign in with GitHub" again. */
export function onTokenRejected(cb: () => void): () => void { listeners.add(cb); return () => { listeners.delete(cb); }; }
export const isRejected = (token: string | null) => !!token && rejected.has(token);
/** GitHub answered 401 with this token: forget it everywhere (it can never work again) and say so once. */
export async function rejectToken(token: string): Promise<void> {
  if (rejected.has(token)) return;
  rejected.add(token);
  if ((await getToken()) === token) await setToken(null);
  listeners.forEach((cb) => { try { cb(); } catch { /* a closed screen */ } });
}

/** The token to call GitHub with: renewed first when an 8-hour sign-in is about to end. */
export async function freshToken(fallback: string | null): Promise<string | null> {
  const raw = await readSecure(SIGNIN_KEY);
  if (!raw) return fallback;
  let record: SigninRecord;
  try {
    record = JSON.parse(raw);
  } catch {
    return fallback;
  }
  if (record.expiresAt - Date.now() > RENEW_BEFORE_MS) return (await getToken()) ?? fallback;
  if (!renewing) {
    renewing = (async () => {
      const got = await renewGrant(record.refresh);
      if (got === 'refused') {
        const old = await getToken();                  // the sign-in ended: its token is expired too
        await writeSecure(SIGNIN_KEY, null);
        if (old) await rejectToken(old);               // You -> Sign in with GitHub shows again
        return null;
      }
      if (!got) return null;                           // offline: try again next time
      await setToken(got.token);
      await saveSignin(got);
      return got.token;
    })().finally(() => {
      renewing = null;
    });
  }
  const got = (await renewing) ?? (await getToken()) ?? fallback;
  return isRejected(got) ? null : got;
}

// ---- cached results: { at: ISO time, data }
export async function readCache<T>(key: string): Promise<{ at: string; data: T } | null> {
  const raw = await AsyncStorage.getItem(`mygeeky.cache.${key}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export async function writeCache<T>(key: string, data: T): Promise<void> {
  await AsyncStorage.setItem(`mygeeky.cache.${key}`, JSON.stringify({ at: new Date().toISOString(), data }));
}

export function isStale(at: string | undefined, hours: number): boolean {
  if (!at) return true;
  return Date.now() - new Date(at).getTime() > hours * 3600 * 1000;
}

export async function clearAll(): Promise<void> {
  const keys = (await AsyncStorage.getAllKeys()).filter((k) => k.startsWith('mygeeky.'));
  await AsyncStorage.multiRemove(keys);
  await setToken(null);
}
