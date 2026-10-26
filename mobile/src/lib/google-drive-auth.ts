// Sign in with Google for Google Drive, on Android: Google's own sign-in sheet (Google Identity Services'
// AuthorizationClient, in the small native module modules/google-drive-auth), asking for one thing only:
// drive.appdata, myGeeKy's own hidden folder in your Drive. It can't see or touch your other files. Google gives a
// 1-hour token; when it ends the phone asks again without showing anything (the desktop's side: google_login.py).
// Never ask for another scope: `drive` is restricted (a yearly paid security review), and the privacy policy
// promises this one only.
import { requireOptionalNativeModule } from 'expo';

type Native = {
  authorize(interactive: boolean): Promise<{ accessToken: string }>;
  clearToken(token: string): Promise<void>;
};
const native = requireOptionalNativeModule<Native>('GoogleDriveAuth');
let current: { token: string; until: number } | null = null;

export const driveAvailable = () => !!native;

/** Ask Google for Drive access, showing its sign-in sheet if needed (the first time, or after access was removed). */
export async function signInWithGoogle(): Promise<void> {
  if (!native) throw new Error('This version of the app can\'t sign in with Google yet. Update it from Google Play.');
  try {
    const r = await native.authorize(true);
    current = { token: r.accessToken, until: Date.now() + 50 * 60000 };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (/cancel/i.test(msg)) throw new Error('You cancelled the sign-in on Google.');
    throw new Error(`Google didn't sign you in: ${msg.slice(0, 160)}`);
  }
}

/** A working Drive token (asked again quietly when the last one ended; `fresh` when Drive refused it). */
export async function driveToken(fresh = false): Promise<string> {
  if (!native) throw new Error('This version of the app can\'t use Google Drive. Update it from Google Play.');
  if (current && !fresh && Date.now() < current.until) return current.token;
  if (current && fresh) await native.clearToken(current.token).catch(() => undefined);
  try {
    const r = await native.authorize(false);
    current = { token: r.accessToken, until: Date.now() + 50 * 60000 };
    return r.accessToken;
  } catch {
    current = null;
    throw new Error('Google Drive needs you to sign in with Google again (Settings → Accounts).');
  }
}

export async function forgetGoogle(): Promise<void> {
  if (current && native) await native.clearToken(current.token).catch(() => undefined);
  current = null;
}
