// The four signs on the right of the top strip -- a port of the desktop's signs.py: is GitHub linked, is ORCID,
// is myGeeKy saving to your data repo, is your Signals beacon on. Each is on (lit), off (faint: never set up) or bad
// (red: its access stopped working, or is about to); a bad one reminds you, at most once a day, to renew it. Only what
// the app knows already (the daily token check): no request. tests/test_signs.py checks both apps agree.
export type SignState = 'on' | 'off' | 'bad';
export type Sign = { key: 'github' | 'orcid' | 'data' | 'beacon'; label: string; state: SignState; tip: string };

export const ORDER = ['github', 'orcid', 'data', 'beacon'] as const;
export const LABELS: Record<Sign['key'], string> = { github: 'GitHub', orcid: 'ORCID', data: 'Saving', beacon: 'Beacon' };
export const TIPS: Record<Sign['key'], Partial<Record<SignState, string>>> = {
  github: { on: 'Signed in with GitHub.',
    off: "GitHub isn't linked. Link it in More → Settings for people, your repos and Signals.",
    bad: 'Your GitHub sign-in stopped working. Sign in again in More → Settings.' },
  orcid: { on: 'ORCID is linked: your papers shape what you see.',
    off: "ORCID isn't linked. Add it in More → Settings for your papers and who cites you." },
  data: { on: 'Saving to your private data repo: your computers and phone share what myGeeKy learns.',
    off: 'Not saving to a data repo: what myGeeKy learns stays on this device only.',
    bad: "myGeeKy can't save to your data repo any more: its access expired or stopped working. Renew it." },
  beacon: { on: 'Your Signals beacon is on.', off: 'Signals is off.',
    bad: 'Your Signals token expired or stopped working: renew it to keep Signals on.' },
};
export const REMIND_HOURS = 24;

/** signs.state: 'off' never set up, 'bad' set up but its access stopped (or is about to), else 'on'. */
export const state = (present: boolean, broken = false): SignState => (!present ? 'off' : broken ? 'bad' : 'on');

export function signs(github: SignState, orcid: SignState, data: SignState, beacon: SignState): Sign[] {
  const given: Record<Sign['key'], SignState> = { github, orcid: orcid !== 'off' ? 'on' : 'off', data, beacon };
  return ORDER.map((key) => {
    const st: SignState = ['on', 'off', 'bad'].includes(given[key]) ? given[key] : 'off';
    return { key, label: LABELS[key], state: st, tip: TIPS[key][st] ?? '' };
  });
}

/** signs.reminder: the message about a sign gone red, or '' (none, or one shown within REMIND_HOURS). */
export function reminder(items: Sign[], last: string, now: Date): string {
  const bad = items.filter((s) => s.state === 'bad');
  if (!bad.length) return '';
  const t = last ? Date.parse(last) : NaN;
  if (!Number.isNaN(t) && now.getTime() - t < REMIND_HOURS * 3600000) return '';
  return bad.map((s) => s.tip).join(' ');
}
