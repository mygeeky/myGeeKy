// Where your data is saved, and switching it, on the phone (the desktop's saving.py): Google Drive (recommended: one
// sign-in, nothing to renew) or a private GitHub repo -- one or the other, never both, the same plain files in either
// (lib/data-store.ts). Switching copies the files over and leaves a "moved" mark where they were, so your other
// devices know to follow.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { driveStore, githubStore, Moved, moveStore, openStore, savedWhere, setWhere } from './data-store';
import { driveAvailable, signInWithGoogle } from './google-drive-auth';
import { connectModel, flushInterests, modelLink } from './model-repo';

export { Moved };

/** "Continue with Google": Google's sign-in, then your data is saved in Drive (moved there from your repo if it was). */
export async function saveInDrive(): Promise<string> {
  await signInWithGoogle();
  const before = await savedWhere();
  const link = await modelLink();
  const drive = driveStore();
  await openStore(drive, true);
  let note = '';
  if (before === 'github' && link) {
    await moveStore(githubStore(link.repo, link.token), drive, 'drive');
    note = 'Moved from GitHub. ';
  } else if (link) {
    note = 'Your computer still saves to your repo: switch it too, in Settings → Accounts there. ';
  }
  await setWhere('drive');
  await flushInterests().catch(() => undefined);
  return `${note}Your data is saved in Google Drive.`;
}

/** A private GitHub repo and its token. Moves your data from Drive if it was there. */
export async function saveInGithub(repo: string, token: string): Promise<string> {
  const before = await savedWhere();
  if (before === 'drive') await flushInterests().catch(() => undefined);   // what's queued goes to Drive, then moves
  await connectModel(repo, token, before !== 'drive');               // checks the token can read and write that repo
  repo = repo.trim();
  token = token.trim();
  const gh = githubStore(repo, token);
  await openStore(gh, true);
  let note = '';
  if (before === 'drive') {
    await moveStore(driveStore(), gh, `github:${repo}`);
    note = 'Moved from Google Drive. ';
  }
  await setWhere('github');
  await flushInterests().catch(() => undefined);
  return `${note}Your data is saved in ${repo}.`;
}

/** From the pairing QR code: where your computer saves. It never changes where this phone already saves; a repo's name
 *  is filled in for you (the phone still needs its own token), and Google Drive needs this phone's own sign-in
 *  (Continue with Google, the first choice). */
export async function fromPairing(where: string | null): Promise<void> {
  if (!where?.startsWith('github:') || await savedWhere() || await modelLink()) return;
  await AsyncStorage.setItem('mygeeky.model.repo', where.slice('github:'.length));
}

/** What's wrong with saving right now, if anything (one quick look at the storage): '' when all is well or offline. */
export async function savingProblem(): Promise<'' | 'google' | 'moved'> {
  const where = await savedWhere();
  const link = await modelLink();
  if (where === 'drive' && !driveAvailable()) return 'google';
  try {
    if (where === 'drive') await openStore(driveStore());
    else if (where === 'github' && link) await openStore(githubStore(link.repo, link.token));
    return '';
  } catch (e) {
    if (e instanceof Moved) return 'moved';
    return e instanceof Error && /sign in with Google/i.test(e.message) ? 'google' : '';
  }
}
