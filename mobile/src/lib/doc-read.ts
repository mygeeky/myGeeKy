// Drop a CV, thesis or abstract: find your field's keywords, your methods and tools, and your co-authors -- a port
// of the desktop's docread.py (tests/test_docread.py runs both on the same texts). It all happens on this phone:
// the document is never sent anywhere, and only the words you keep are saved. Keywords are the dictionary's topics
// found in the text; methods and tools come from data/docread.json (identical to the desktop's); co-authors are
// names that sit next to others in author lists, the most frequent one being you unless your name is given.
import fieldWords from '../data/field-words.json';
import docRules from '../data/docread.json';

type Method = { name: string; also?: string[]; exact?: boolean; needs?: string[] };
type Rules = { ignore: string[]; headings: string[]; methods: Method[] };
export type Found = { keywords: string[]; methods: string[]; coauthors: string[]; words: number };

const RULES = docRules as Rules;
const HEAD_WORDS = 250;
const SHORT_WORDS = 800;
const MAX_GRAM = 4;
const KEYWORDS = 15, METHODS = 12, COAUTHORS = 10;

const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

export function norm(s: string): string {
  return String(s ?? '').normalize('NFKD').replace(/[^\x00-\x7f]/g, '').toLowerCase().replace(/[^a-z0-9+#]+/g, ' ')
    .split(' ').filter(Boolean).join(' ');
}

function grams(tokens: string[]): Map<string, number> {
  const out = new Map<string, number>();
  for (let n = 1; n <= MAX_GRAM; n++) {
    for (let i = 0; i + n <= tokens.length; i++) {
      const g = tokens.slice(i, i + n).join(' ');
      out.set(g, (out.get(g) ?? 0) + 1);
    }
  }
  return out;
}

const forms = (m: Method) => [m.name, ...(m.also ?? [])];

/** The positions inside any of these phrases (two words or more), wherever they occur. */
function covered(tokens: string[], phrases: string[]): Set<number> {
  const out = new Set<number>();
  for (const ph of new Set(phrases.filter((p) => p.includes(' ')))) {
    const words = ph.split(' ');
    for (let i = 0; i + words.length <= tokens.length; i++) {
      if (words.every((w, j) => tokens[i + j] === w)) for (let j = 0; j < words.length; j++) out.add(i + j);
    }
  }
  return out;
}

/** `skip`: forms that are methods, not topics. `inside`: the forms of the methods found. A single word counts only
 * where it stands on its own: "rna" inside RNA-seq, or "genetics" inside "statistical genetics", doesn't. */
export function findKeywords(tokens: string[], vocabulary: string[], skip: Set<string>, inside: string[] = []): string[] {
  const ignore = new Set(RULES.ignore), headings = new Set(RULES.headings);
  const all = grams(tokens), head = grams(tokens.slice(0, HEAD_WORDS));
  const short = tokens.length < SHORT_WORDS;
  const labels = new Map<string, string>();
  const sorted = [...vocabulary].map((w) => [norm(w), w] as const).sort((a, b) => cmp(a[0], b[0]) || cmp(a[1], b[1]));
  for (const [t, label] of sorted) {
    if (t && t.length > 1 && !labels.has(t) && !ignore.has(t) && !skip.has(t) && t.split(' ').length - 1 < MAX_GRAM) {
      labels.set(t, label);
    }
  }
  const scored: [number, string][] = [];
  const phrases = [...labels.keys()].filter((t) => t.includes(' ') && all.get(t));
  for (const t of phrases) scored.push([-(all.get(t)! + 2 * (head.get(t) ?? 0)) * (1 + 0.5 * (t.split(' ').length - 1)), t]);
  const cov = covered(tokens, [...phrases, ...inside.map(norm)]);
  const alone = new Map<string, number>(), aloneHead = new Map<string, number>();
  tokens.forEach((w, i) => {
    if (cov.has(i)) return;
    alone.set(w, (alone.get(w) ?? 0) + 1);
    if (i < HEAD_WORDS) aloneHead.set(w, (aloneHead.get(w) ?? 0) + 1);
  });
  for (const t of labels.keys()) {
    if (t.includes(' ') || !alone.get(t)) continue;
    const need = headings.has(t) ? (short ? 2 : 4) : (short ? 1 : 2);
    if (alone.get(t)! >= need) scored.push([-(alone.get(t)! + 2 * (aloneHead.get(t) ?? 0)), t]);
  }
  scored.sort((a, b) => a[0] - b[0] || cmp(a[1], b[1]));
  return scored.slice(0, KEYWORDS).map(([, t]) => labels.get(t)!);
}

export function findMethods(text: string, tokens: string[]): string[] {
  const all = grams(tokens);
  const have = new Set(tokens);
  const raw = text.split(/[^A-Za-z0-9+#]+/);
  const found: [number, string][] = [];
  for (const m of RULES.methods) {
    if (m.needs?.length && !m.needs.some((w) => have.has(w))) continue;
    let c: number;
    if (m.exact) {
      c = raw.filter((w) => w === m.name).length;
      if (c < 2) continue;
    } else {
      c = forms(m).reduce((s, n) => s + (all.get(norm(n)) ?? 0), 0);
      if (c < 1) continue;
    }
    found.push([-c, m.name]);
  }
  found.sort((a, b) => a[0] - b[0] || cmp(a[1], b[1]));
  return found.slice(0, METHODS).map(([, n]) => n);
}

const SURNAME = '[A-Z][a-z]+(?:-[A-Z][a-z]+)?';
const NAME = new RegExp(
  `\\b(${SURNAME}),\\s?([A-Z])\\.(?:\\s?[A-Z]\\.)*`
  + `|\\b([A-Z])\\.(?:\\s?[A-Z]\\.)*\\s(${SURNAME})\\b`
  + `|\\b(${SURNAME})\\s([A-Z]{1,3})\\b(?=[,;.]|\\s(?:and|&)\\s|$)`, 'g');

const plain = (s: string) => s.normalize('NFKD').replace(/[̀-ͯ᪰-᫿᷀-᷿⃐-⃿︠-︯]/g, '')
  .replace(/[\t  -​  　]/g, ' ');     // a PDF's no-break spaces, as plain ones

function keyOfName(name: string): string | null {
  const w = norm(name).split(' ').filter(Boolean);
  return w.length >= 2 ? `${w[w.length - 1]}|${w[0][0].toUpperCase()}` : null;
}

export function findCoauthors(text: string, ownName = ''): string[] {
  const counts = new Map<string, number>();
  const shown = new Map<string, string>();
  // an author list wrapped onto the next line is one list: join after a comma, "&", "and" or a lone initial
  for (const line of plain(text).replace(/(,|&|\band|\b[A-Z]\.)[ ]*\r?\n/g, '$1 ').split('\n')) {
    const names: [string, string][] = [];
    for (const m of line.matchAll(NAME)) {
      names.push(m[1] ? [m[1], m[2]] : m[4] ? [m[4], m[3]] : [m[5], m[6][0]]);
    }
    if (names.length < 2) continue;
    for (const [surname, initial] of names) {
      const key = `${surname.toLowerCase()}|${initial}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
      if (!shown.has(key)) shown.set(key, `${initial}. ${surname}`);
    }
  }
  let me = ownName ? keyOfName(ownName) : null;
  if (me === null && counts.size) {                       // you: the name on most lists, if it clearly leads
    const top = [...counts].sort((a, b) => b[1] - a[1] || cmp(shown.get(a[0])!, shown.get(b[0])!));
    if (top[0][1] >= 3 && (top.length === 1 || top[0][1] > top[1][1])) me = top[0][0];
  }
  return [...counts].filter(([k]) => k !== me).map(([k, c]) => [-c, shown.get(k)!] as const)
    .sort((a, b) => a[0] - b[0] || cmp(a[1], b[1])).slice(0, COAUTHORS).map(([, n]) => n);
}

export function read(text: string, vocabulary: string[], ownName = ''): Found {
  text = String(text ?? '');
  const tokens = norm(text).split(' ').filter(Boolean);
  const methods = findMethods(text, tokens);
  const skip = new Set(RULES.methods.flatMap((m) => forms(m).map(norm)));
  const found = RULES.methods.filter((m) => methods.includes(m.name)).flatMap(forms);
  return { keywords: findKeywords(tokens, vocabulary, skip, found), methods, coauthors: findCoauthors(text, ownName),
    words: tokens.length };
}

/** The dictionary's topics, as you'd write them: the same list the desktop reads from its dictionary. */
export const vocabulary = (): string[] => Object.keys((fieldWords as { related: Record<string, string[]> }).related);

export const readDocument = (text: string, ownName = '') => read(text, vocabulary(), ownName);

/** What you have, then the new words you kept, without the same word twice ("Single-cell" = "single cell"). */
export function mergeWords(have: string[], add: string[]): string[] {
  const seen = new Set<string>();
  return [...have, ...add].filter((w) => {
    const k = norm(w);
    if (!k || seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}
