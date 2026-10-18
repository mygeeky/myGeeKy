// Suggestions while you type your field's keywords: the desktop's keyword dictionary (data/field-words.json,
// written by src/mygeeky/keywords.py) plus the skill names. Words starting with what you type come first,
// then words containing it. With nothing typed, the closest words to the ones you already picked.
import fieldWords from '../data/field-words.json';
import vocab from '../data/skills.json';

const RELATED: Record<string, string[]> = (fieldWords as any).related ?? {};
let WORDS: string[] | null = null;
const norm = (w: string) => w.toLowerCase().replace(/[\s_-]+/g, ' ').trim();

function words(): string[] {
  if (!WORDS) {
    const all = new Map<string, string>();
    for (const w of [...((fieldWords as any).words ?? []), ...((vocab as any).skills ?? []).map((s: any) => s.name)]) {
      if (typeof w === 'string' && w.trim() && !all.has(norm(w))) all.set(norm(w), w);   // "single cell rna seq" = "Single-cell RNA-seq"
    }
    WORDS = [...all.values()];
  }
  return WORDS;
}

/** The keywords typed so far, and the one being typed (after the last comma). */
export function splitTyping(text: string): { done: string[]; typing: string } {
  const parts = text.split(',');
  const typing = parts.pop()!.trim();
  return { done: parts.map((p) => p.trim()).filter(Boolean), typing };
}

export function suggest(text: string, max = 6): string[] {
  const { done, typing } = splitTyping(text);
  const taken = new Set(done.map(norm));
  const q = typing.toLowerCase();
  if (!q) {
    const near = done.flatMap((d) => RELATED[norm(d)] ?? []);
    return [...new Set(near)].filter((w) => !taken.has(norm(w))).slice(0, max);
  }
  if (q.length < 2) return [];
  const starts: string[] = [];
  const within: string[] = [];
  for (const w of words()) {
    const l = w.toLowerCase();
    if (taken.has(norm(w)) || norm(w) === norm(q)) continue;
    if (l.startsWith(q) || l.split(/[\s-]/).some((part) => part.startsWith(q))) starts.push(w);
    else if (q.length >= 3 && l.includes(q)) within.push(w);
  }
  // shorter first, then plain character order (not localeCompare), exactly as keywords.suggest on the desktop
  const byLength = (a: string, b: string) => a.length - b.length || (a < b ? -1 : a > b ? 1 : 0);
  return [...starts.sort(byLength), ...within.sort(byLength)].slice(0, max);
}

/** The text with the word being typed replaced by `word`, ready for the next one. */
export function pick(text: string, word: string): string {
  const { done } = splitTyping(text);
  return [...done, word].join(', ') + ', ';
}
