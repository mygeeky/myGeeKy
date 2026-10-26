// Your saved data, on the phone: the same storage and files as the desktop (src/mygeeky/storesync.py, sync.py) --
// Google Drive's hidden app folder or a private GitHub repo, the same plain files in either. The phone reads your
// computers' files and adds what you do here to the logs (*.jsonl); your computers merge them line by line.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { driveToken } from './google-drive-auth';
import { fetchT } from './net';
import { b64, fromUtf8, unb64, utf8 } from './signal-crypto';

const WHERE_KEY = 'mygeeky.saving.where';                // 'drive' | 'github' | absent
const FORMAT = 'mygeeky.json';                           // {"format": 3}, plus "moved_to" once a device switched away
const ME = { name: 'myGeeKy', email: 'housekeeping@mygeeky.invalid' };

export class Moved extends Error {}
class Conflict extends Error {}

export type Where = 'drive' | 'github';
export async function savedWhere(): Promise<Where | null> {
  const w = await AsyncStorage.getItem(WHERE_KEY);
  return w === 'drive' || w === 'github' ? w : null;
}
export async function setWhere(w: Where | null): Promise<void> {
  if (w) await AsyncStorage.setItem(WHERE_KEY, w);
  else await AsyncStorage.removeItem(WHERE_KEY);
}

// ---- the stores: list (name -> revision), read, write
export type Store = {
  label: string;
  list(): Promise<Record<string, string>>;
  read(name: string): Promise<string | null>;
  write(name: string, text: string): Promise<void>;
};

export function githubStore(repo: string, token: string): Store {
  const headers = { Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}`, 'X-GitHub-Api-Version': '2022-11-28' };
  let shas: Record<string, string> = {};
  const fail = (status: number, what: string) => {
    if (status === 401 || status === 403) return new Error('The data repo token no longer works. Make a new one and connect again.');
    return new Error(`GitHub answered ${status} for ${what}.`);
  };
  return {
    label: repo,
    async list() {
      const r = await fetchT(`https://api.github.com/repos/${repo}/git/trees/HEAD`, { headers });
      if (r.status === 409 || r.status === 404) { shas = {}; return {}; }   // an empty repo
      if (!r.ok) throw fail(r.status, 'the file list');
      const j = await r.json();
      shas = {};
      for (const e of Array.isArray(j?.tree) ? j.tree : []) {
        if (e?.type === 'blob' && typeof e.path === 'string' && typeof e.sha === 'string') shas[e.path] = e.sha;
      }
      return { ...shas };
    },
    async read(name) {
      const sha = shas[name];
      if (!sha) return null;
      const r = await fetchT(`https://api.github.com/repos/${repo}/git/blobs/${sha}`, { headers }, 60000);
      if (!r.ok) throw fail(r.status, name);
      const j = await r.json();
      return fromUtf8(unb64(String(j?.content ?? '').replace(/\s/g, '')) ?? new Uint8Array(0));
    },
    async write(name, text) {
      const r = await fetchT(`https://api.github.com/repos/${repo}/contents/${name}`, {
        method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `myGeeKy phone: ${name}`, sha: shas[name], author: ME, committer: ME, content: b64(utf8(text)) }),
      }, 60000);
      if (r.status === 409 || r.status === 422) throw new Conflict('Another device was saving at the same moment. Try again in a minute.');
      if (!r.ok) throw fail(r.status, name);
      const j = await r.json();
      if (typeof j?.content?.sha === 'string') shas[name] = j.content.sha;
    },
  };
}

export function driveStore(token: (fresh: boolean) => Promise<string> = driveToken): Store {
  const API = 'https://www.googleapis.com/drive/v3/files';
  const UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files';
  let ids: Record<string, string> = {};
  const call = async (url: string, init: RequestInit = {}, ms = 30000): Promise<Response> => {
    for (const fresh of [false, true]) {
      const r = await fetchT(url, { ...init, headers: { ...(init.headers as Record<string, string> ?? {}), Authorization: `Bearer ${await token(fresh)}` } }, ms);
      if (r.status === 401 && !fresh) continue;
      if (r.status === 401) throw new Error('Google Drive needs you to sign in with Google again (Settings → Accounts).');
      if (r.status === 403 && (await r.clone().text()).includes('storageQuota')) throw new Error('Your Google Drive is full, so your data can\'t be saved there.');
      if (!r.ok) throw new Error(`Google Drive answered ${r.status}.`);
      return r;
    }
    throw new Error('unreachable');
  };
  return {
    label: 'Google Drive',
    async list() {
      const out: Record<string, string> = {};
      const when: Record<string, string> = {};
      ids = {};
      let page = '';
      do {
        const q = new URLSearchParams({ spaces: 'appDataFolder', pageSize: '1000', fields: 'nextPageToken,files(id,name,md5Checksum,modifiedTime)' });
        if (page) q.set('pageToken', page);
        const j = await (await call(`${API}?${q}`)).json();
        for (const f of Array.isArray(j?.files) ? j.files : []) {
          const name = String(f?.name ?? ''), id = String(f?.id ?? ''), t = String(f?.modifiedTime ?? '');
          if (name && id && (!(name in when) || t > when[name])) {          // two copies: the newest
            when[name] = t;
            ids[name] = id;
            out[name] = String(f?.md5Checksum ?? '') || t;
          }
        }
        page = typeof j?.nextPageToken === 'string' ? j.nextPageToken : '';
      } while (page);
      return out;
    },
    async read(name) {
      const id = ids[name];
      if (!id) return null;
      return (await call(`${API}/${id}?alt=media`, {}, 60000)).text();
    },
    async write(name, text) {
      let id = ids[name];
      if (!id) {
        const made = await (await call(`${API}?fields=id`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, parents: ['appDataFolder'] }) })).json();
        id = String(made?.id ?? '');
        if (!id) throw new Error('Google Drive didn\'t make the file.');
        ids[name] = id;
      }
      await call(`${UPLOAD}/${id}?uploadType=media&fields=id`, { method: 'PATCH',
        headers: { 'Content-Type': 'text/plain; charset=utf-8' }, body: text }, 60000);
    },
  };
}

// ---- reading and adding to your saved data
export type Opened = {
  store: Store;
  read(file: string): Promise<string | null>;
  append(file: string, lines: string[]): Promise<void>;
};

function movedTo(text: string | null): string | null {
  try {
    const m = JSON.parse(text ?? 'null')?.moved_to;
    return typeof m === 'string' && /^(drive|github:[A-Za-z0-9-]{1,39}\/[A-Za-z0-9._-]{1,100})$/.test(m) ? m : null;
  } catch {
    return null;
  }
}

/** A storage's mygeeky.json that says another device moved the data away: throws Moved, saying where. */
export function throwIfMoved(format: string | null): void {
  const moved = movedTo(format);
  if (moved) throw new Moved(`Your data moved to ${moved === 'drive' ? 'Google Drive' : moved.replace(/^github:/, '')} on another device. Switch this phone too, in Settings → Accounts.`);
}

/** Open a store: one another device moved away from throws Moved, unless it's being chosen again (`claim`), when it
 *  becomes the place again. */
export async function openStore(store: Store, claim = false): Promise<Opened> {
  const names = await store.list();
  const format = FORMAT in names ? await store.read(FORMAT) : null;
  if (claim && movedTo(format)) await store.write(FORMAT, JSON.stringify({ format: 3 }, null, 1));
  else throwIfMoved(format);
  return { store, read: (file) => store.read(file), append: (file, lines) => appendTo(store, file, lines) };
}

/** Add lines to a log: the newest copy, plus them; once more if a computer saved it at that very moment. */
export async function appendTo(store: Store, file: string, lines: string[]): Promise<void> {
  for (let attempt = 0; ; attempt++) {
    await store.list();
    const have = (await store.read(file)) ?? '';
    try {
      await store.write(file, `${have}${have && !have.endsWith('\n') ? '\n' : ''}${lines.join('\n')}\n`);
      return;
    } catch (e) {
      if (attempt || !(e instanceof Conflict)) throw e;
    }
  }
}

/** Copy every file from one store to another as it is, then mark the old one moved. How many files went. */
export async function moveStore(from: Store, to: Store, toLabel: 'drive' | `github:${string}`): Promise<number> {
  const src = await from.list();
  await to.list();
  let n = 0;
  for (const name of Object.keys(src)) {
    if (name === FORMAT || name.endsWith('.mgk') || name.startsWith('.')) continue;
    const text = await from.read(name);
    if (text !== null) { await to.write(name, text); n++; }
  }
  await to.write(FORMAT, JSON.stringify({ format: 3 }, null, 1));
  await from.write(FORMAT, JSON.stringify({ format: 3, moved_to: toLabel }, null, 1));
  return n;
}
