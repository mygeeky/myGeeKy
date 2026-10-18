// The 💡: an idea, a problem or a question to myGeeKy's maker -- a port of the desktop's ideas.py, so both apps
// open the same GitHub issue and the same email (tests/test_phone_ideas_match_desktop.py runs this in Node).
// Nothing is sent from here: the browser or the mail app opens it ready, and the user sends it themselves.

export const IDEAS_REPO = 'mygeeky/myGeeKy-ideas';
export const SUPPORT_EMAIL = 'support@mygeeky.org';
const MAX_URL = 7000;          // browsers and GitHub cope with ~8k; stay well under
const MAX_MAILTO = 1800;       // some mail apps cut a mailto: link near 2000 characters
// ideas.KINDS, without report and protocol (those are sent from the listing or protocol itself)
export const KINDS: [string, string, string, string][] = [
  ['idea', '💡', 'Idea', 'idea'], ['problem', '🐞', 'Problem', 'problem'], ['question', '❓', 'Question', 'question'],
  ['keyword', '🔤', 'Keyword', 'keyword'], ['score', '🏆', 'Quiz score', 'leaderboard'],
];

function parts(kind: string, title: string, details: string) {
  const [, emoji, label, ghLabel] = KINDS.find((k) => k[0] === kind) ?? KINDS[0];
  const t = title.split(/\s+/).filter(Boolean).join(' ').slice(0, 120) || label;
  let body = details.trim();
  if (kind === 'problem' && !body) body = 'What happened, and what did you expect?\n';
  return { emoji, ghLabel, t, body };
}

/** ideas.issue_url: the prefilled new-issue page. `version` is the version line, or null to leave it out. */
export function issueUrl(kind: string, title: string, details: string, version: string | null): string {
  const { emoji, ghLabel, t, body: b0 } = parts(kind, title, details);
  let body = b0 + (version ? `\n\n---\n<sub>Sent from the 💡 in myGeeKy · ${version}</sub>` : '\n\n---\n<sub>Sent from the 💡 in myGeeKy</sub>');
  const make = (b: string) => `https://github.com/${IDEAS_REPO}/issues/new?${new URLSearchParams({ title: `${emoji} ${t}`, body: b, labels: ghLabel })}`;
  let url = make(body);
  while (url.length > MAX_URL && body.length > 200) {     // a very long text: trim, never drop the title
    body = `${body.slice(0, Math.floor(body.length * 0.8))}\n\n(trimmed: please add the rest after opening)`;
    url = make(body);
  }
  return url;
}

/** ideas.email_url: the same idea as a ready-made email to support, for people without GitHub. */
export function emailUrl(kind: string, title: string, details: string, version: string | null): string {
  const { emoji, t, body: b0 } = parts(kind, title, details);
  let body = b0 + (version ? `\n\n---\nSent from the 💡 in myGeeKy · ${version}` : '\n\n---\nSent from the 💡 in myGeeKy');
  const make = (b: string) => `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`${emoji} ${t}`)}&body=${encodeURIComponent(b)}`;
  let url = make(body);
  while (url.length > MAX_MAILTO && body.length > 200) {
    body = `${body.slice(0, Math.floor(body.length * 0.8))}\n\n(trimmed: please add the rest in the email)`;
    url = make(body);
  }
  return url;
}
