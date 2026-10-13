// Collaborator match -- a port of the desktop's collab.py. Fellow myGeeKy users on
// Signals whose skills complement yours: they bring what you don't show (the Rising
// Skills you lack first), you bring what they don't. Scored here, on the phone; asking
// uses the existing sealed 🤝, which they only ever see if they choose you too.
import type { Person } from './signals-core';
import { skillsIn } from './skills';
import * as taste from './taste';

export type Match = Person & { theyBring: string[]; youBring: string[]; score: number; vote: number; asked: boolean };

export async function matches(people: Person[], have: Set<string>, wanted: Set<string>, asked: Set<string>,
  strengths: string[] = [], top = 12): Promise<{ people: Match[]; hidden: number }> {
  const votes = await taste.load();
  const leanW = taste.weights(votes, ['collaborator']);
  const out: Match[] = [];
  let hidden = 0;
  for (const p of people) {
    const v = taste.voteOf(votes, 'collaborator', p.login);
    if (v < 0) {
      hidden++;
      continue;
    }
    const theirs = skillsIn(p.interests.join(' ; '));
    const theyBring = [...theirs].filter((s) => !have.has(s)).sort((a, b) => Number(!wanted.has(a)) - Number(!wanted.has(b)) || a.localeCompare(b));
    const rank = (s: string) => (strengths.includes(s) ? strengths.indexOf(s) : strengths.length);
    const youBring = [...have].filter((s) => !theirs.has(s)).sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
    if (!theyBring.length && !p.shared.length) continue;
    const bring = theyBring.length + theyBring.filter((s) => wanted.has(s)).length;
    let score = (0.25 + p.fit) * (0.5 + 0.5 * Math.min(1, bring / 3)) * (0.6 + 0.4 * Math.min(1, youBring.length / 3));
    score *= 1 + 0.4 * taste.lean(p.interests.join(' ; '), [], leanW);
    if (v > 0) score *= 1.3;
    out.push({ ...p, theyBring, youBring, score, vote: v, asked: asked.has(p.login.toLowerCase()) });
  }
  out.sort((a, b) => b.score - a.score);
  return { people: out.slice(0, top), hidden };
}
