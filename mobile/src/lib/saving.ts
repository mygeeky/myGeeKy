// Where your data is saved, and switching it, on the phone (the desktop's saving.py): Google Drive (recommended: one
// sign-in, nothing to renew) or a private GitHub repo -- one or the other, never both, encrypted either way
// (lib/data-store.ts). Switching copies the encrypted files over (nothing is opened) and leaves a "moved" mark where
// they were, so your other devices know to follow.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as L from './data-lock';
import { driveStore, getKey, githubStore, Moved, NeedsKey, openLocked, savedWhere, setKey, setWhere, moveStore } from './data-store';
import { signInWithGoogle } from './google-drive-auth';
import { connectModel, flushInterests, modelLink } from './model-repo';

export { Moved, NeedsKey };

/** "Continue with Google": Google's sign-in, then your data is saved in Drive (moved there from your repo if it was). */
export async function saveInDrive(): Promise<string> {
  await signInWithGoogle();
  const before = await savedWhere();
  const link = await modelLink();
  const drive = driveStore();
  const locked = await openLocked(drive, await getKey(), true);       // a new Drive becomes yours; NeedsKey if not
  await setKey(locked.key);
  let note = '';
  if (before === 'github' && link) {
    await moveStore(githubStore(link.repo, link.token), drive, locked.key, 'drive');
    note = 'Moved from GitHub. ';
  } else if (link) {
    note = 'Your computer still saves to your repo: switch it too, in Settings → Accounts there. ';
  }
  await setWhere('drive');
  await flushInterests().catch(() => undefined);
  return `${note}Your data is saved in Google Drive, encrypted.`;
}

/** A private GitHub repo and its token: encrypted (an older plain repo with data stays as it is until your computer
 *  encrypts it). Moves your data from Drive if it was there. */
export async function saveInGithub(repo: string, token: string): Promise<string> {
  const before = await savedWhere();
  await connectModel(repo, token);                                   // checks the token can read and write that repo
  repo = repo.trim();
  token = token.trim();
  const gh = githubStore(repo, token);
  const names = await gh.list();
  const plain = !(L.FORMAT_FILE in names) && Object.keys(names).some((n) => n.endsWith('.json') || n.endsWith('.jsonl'));
  if (plain) {
    await setWhere(null);
    return `Saving to ${repo}. It isn't encrypted yet: encrypt it from your computer (Settings → Accounts).`;
  }
  const locked = await openLocked(gh, await getKey(), true);
  await setKey(locked.key);
  let note = '';
  if (before === 'drive') {
    await moveStore(driveStore(), gh, locked.key, `github:${repo}`);
    note = 'Moved from Google Drive. ';
  }
  await setWhere('github');
  await flushInterests().catch(() => undefined);
  return `${note}Your data is saved in ${repo}, encrypted.`;
}

export async function recoveryCode(): Promise<string | null> {
  const key = await getKey();
  return key ? L.recoveryCode(key) : null;
}

/** The recovery code typed on this phone: its key is kept only if it opens your saved data (or nothing is saved yet). */
export async function enterCode(code: string): Promise<void> {
  const key = L.keyFromCode(code);
  if (!key) throw new Error('That code isn\'t right: check each group of four (the last letters catch typos).');
  const previous = await getKey();
  await setKey(key);
  const where = await savedWhere();
  const link = await modelLink();
  try {
    if (where === 'drive') await openLocked(driveStore(), key);
    else if (where === 'github' && link) await openLocked(githubStore(link.repo, link.token), key);
  } catch (e) {
    await setKey(previous);
    if (e instanceof NeedsKey) throw new Error('That\'s a real recovery code, but not the one your saved data is encrypted with.');
    throw e;
  }
}

/** From the pairing QR code: where your computer saves, and the key. Drive still needs this phone's own Google sign-in;
 *  a repo still needs its own token. */
export async function fromPairing(where: string | null, key: Uint8Array | null): Promise<void> {
  if (!key || !where) return;
  await setKey(key);
  if (where === 'drive') await setWhere('drive');
  else if (where.startsWith('github:')) {
    await AsyncStorage.setItem('mygeeky.model.repo', where.slice('github:'.length));
    await setWhere('github');
  }
}

/** What's wrong with saving right now, if anything (one quick look at the storage): '' when all is well or offline. */
export async function savingProblem(): Promise<'' | 'key' | 'google' | 'moved'> {
  const where = await savedWhere();
  const link = await modelLink();
  try {
    if (where === 'drive') await openLocked(driveStore(), await getKey());
    else if (where === 'github' && link) await openLocked(githubStore(link.repo, link.token), await getKey());
    return '';
  } catch (e) {
    if (e instanceof NeedsKey) return 'key';
    if (e instanceof Moved) return 'moved';
    return e instanceof Error && /sign in with Google/i.test(e.message) ? 'google' : '';
  }
}
