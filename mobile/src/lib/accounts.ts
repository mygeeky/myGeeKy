// Settings → Accounts: the cards, in order, with what each says -- a port of the desktop's accounts.py
// (tests/test_accounts.py checks both agree). GitHub and ORCID first, then saving your data and Signals, then your
// other device. On: folded and green; off: optional ones say why you might want them; bad: its access stopped working.
// Only saving your data counts as something to do (not set up, or any card gone bad); the optional ones never nag.
export type AccountKey = 'github' | 'orcid' | 'data' | 'beacon' | 'device';
export type AccountState = 'on' | 'off' | 'bad';
export type AccountCard = { key: AccountKey; state: AccountState; title: string; pill: string; why: string; heading: string;
  optional: boolean; folded: boolean };

export const ORDER: AccountKey[] = ['github', 'orcid', 'data', 'beacon', 'device'];
export const OPTIONAL: AccountKey[] = ['github', 'orcid', 'beacon', 'device'];
const HEADINGS: Partial<Record<AccountKey, string>> = { github: 'SIGN IN', data: 'SAVING AND SIGNALS', device: 'YOUR OTHER DEVICES' };
const TITLES: Partial<Record<AccountKey, string>> = { github: 'GitHub', orcid: 'ORCID', data: 'Saving your data', beacon: 'Signals (beacon)' };
const PILLS = { on: 'Connected', bad: 'Needs renewing', optional: 'Optional', off: 'Not set up' };

function why(key: AccountKey, state: AccountState, platform: string, d: Record<string, string>): string {
  const here = platform === 'phone' ? 'this phone' : 'this computer';
  if (key === 'github') {
    if (state === 'on') return `Signed in as ${d.user || 'you'}. Read-only: myGeeKy never follows, stars or posts for you.`;
    if (state === 'bad') return 'Your GitHub sign-in stopped working. Sign in again.';
    return 'Why link it: people worth following, your own repos, and My month from your GitHub activity. Read-only: myGeeKy never posts for you.';
  }
  if (key === 'orcid') {
    return state === 'on' ? `Linked: ${d.orcid}. Your papers shape your feeds.`
      : 'Why link it: myGeeKy finds your papers, shows who cites you, and fits jobs to your field. No papers yet? Your keywords are enough.';
  }
  if (key === 'data') {
    const repo = d.repo || 'your data repo';
    const place = d.where === 'drive' ? 'Google Drive' : repo;
    if (state === 'on') return `Saving to ${place}. Your computers and phone share your settings and progress.`;
    if (state === 'bad') {
      if (d.where === 'drive') return `Google Drive stopped accepting ${here}'s sign-in, so nothing has been saved since. Sign in with Google again.`;
      return `Access to ${repo} stopped working, so nothing has been saved since. ${platform === 'phone'
        ? 'On GitHub, open the token, click Regenerate token, and paste the new one here.' : 'Open the setup window to connect it again.'} (Google Drive never needs renewing.)`;
    }
    return `Right now, your settings and progress are only on ${here}. Save them in Google Drive (recommended) or a private GitHub repo: choose one. Either works the same, and you can switch later.`;
  }
  if (key === 'beacon') {
    if (state === 'on') return `Signals is on: private thank-yous and collab invites, with a key kept only on ${here}.`;
    if (state === 'bad') return 'Your Signals token stopped working: renew it to keep Signals on.';
    return 'Why turn it on: private thank-yous and collab invites between myGeeKy users, through your public repo mygeeky-beacon.';
  }
  if (platform === 'phone') {
    return state === 'on' ? "Your computer's profile, interests and badges came over by scan."
      : 'Have myGeeKy on a computer? One scan brings over your profile, interests and badges.';
  }
  return 'Have the phone app? Show a QR code: one scan sets it up with your profile and badges.';
}

/** accounts.cards: the five cards for these states (a missing key is off). */
export function cards(states: Partial<Record<AccountKey, string>>, platform = 'desktop', details: Record<string, string> = {}): AccountCard[] {
  return ORDER.map((key) => {
    let st = (states[key] ?? 'off') as string;
    if (!['on', 'off', 'bad'].includes(st) || (key === 'orcid' && st === 'bad')) st = st === 'bad' ? 'on' : 'off';
    if (key === 'device' && platform !== 'phone') st = 'off';
    const state = st as AccountState;
    const optional = OPTIONAL.includes(key);
    return { key, state, title: TITLES[key] ?? (platform === 'phone' ? 'Your computer' : 'Your phone'),
      pill: state === 'off' && optional ? PILLS.optional : PILLS[state], why: why(key, state, platform, details),
      heading: HEADINGS[key] ?? '', optional, folded: state === 'on' };
  });
}

/** accounts.todo: a card gone bad, or saving your data not set up. */
export const todo = (items: AccountCard[]): number =>
  items.filter((c) => c.state === 'bad' || (c.key === 'data' && c.state === 'off')).length;

export const todoText = (n: number): string =>
  n <= 0 ? '' : n === 1 ? '1 thing would make myGeeKy work better for you' : `${n} things would make myGeeKy work better for you`;
