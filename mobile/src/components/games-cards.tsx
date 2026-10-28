// The card games of Play with GeeKOc: the desktop's gui/games_cards.py on the same GEMS rules. One engine (a round
// of questions; an answer always says why) and six faces: Real tool or made up?, Gene or Pokémon?, Which came first?,
// Reviewer 2 attacks (the grumpy anglerfish and the paper's chance of acceptance), Debug reef (tap the buggy line
// before the bubble rises) and Fix the figure (a flawed chart, drawn here in SVG, the same eight kinds as the desktop).
// Everything shown comes from the pack: plain text only.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Ellipse, G as SvgG, Line, Path, Polyline, Rect, Text as SvgText } from 'react-native-svg';
import { useApp } from '../lib/app-state';
import * as G from '../lib/gems';
import { finish, roundItems } from '../lib/games-store';
import { C, tint } from '../lib/theme';

type Result = Awaited<ReturnType<typeof finish>>;
type Q = G.Item & { a?: G.Item; b?: G.Item };
const shuffle = <T,>(xs: T[]): T[] => { const a = xs.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const secondsSince = (t0: number) => (Date.now() - t0) / 1000;
/** A seeded generator, so a figure draws the same points every time. */
const seeded = (s: number) => { let x = s; return () => (x = (x * 16807) % 2147483647) / 2147483647; };

type Face = {
  game: string; kind: string; round: number; hint: string; timed?: number;
  load?: (items: G.Item[]) => Q[];
  prompt: (q: Q, state: { chance: number; mood: number; left: number }) => ReactNode;
  choices: (q: Q) => { options: string[]; right: number; big?: boolean; lines?: boolean };
  why: (q: Q, right: boolean) => string;
  answered?: (q: Q, right: boolean) => G.Answer[];
};

function NameCard({ text }: { text: string }) {
  return <View style={st.nameCard}><Text style={st.name}>{text}</Text></View>;
}

function Angler({ comment, chance, mood }: { comment: string; chance: number; mood: number }) {
  const lantern = mood > 0 ? '#34d399' : mood < 0 ? '#f87171' : '#ffc457';
  return (
    <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
      <Svg width={110} height={100} viewBox="0 0 110 100">
        <Ellipse cx={46} cy={58} rx={36} ry={28} fill="#4b5a7a" />
        <Path d="M80 58 L104 40 L104 76 Z" fill="#4b5a7a" />
        <Line x1={34} y1={34} x2={18} y2={14} stroke="#4b5a7a" strokeWidth={3} />
        <Circle cx={16} cy={12} r={6} fill={lantern} />
        <Circle cx={30} cy={50} r={7} fill="#fff" />
        <Circle cx={28} cy={51} r={3} fill="#111" />
        <Line x1={20} y1={38} x2={38} y2={mood > 0 ? 34 : 43} stroke="#111" strokeWidth={3} />
        <Line x1={14} y1={70} x2={38} y2={mood > 0 ? 66 : 74} stroke="#1a1428" strokeWidth={2.5} />
      </Svg>
      <View style={{ flex: 1, gap: 6 }}>
        <View style={st.bubble}><Text style={st.bubbleText}>“{comment}”</Text></View>
        <View style={st.bar}><View style={[st.barFill, { width: `${chance}%`, backgroundColor: chance >= 50 ? C.green : C.red }]} /></View>
        <Text style={st.small}>Chance of acceptance: {chance}%</Text>
      </View>
    </View>
  );
}

function Figure({ kind }: { kind: string }) {
  const W = 320, H = 190, L = 34, T = 24, R = W - 10, B = H - 26;
  const soft = '#9a9ab0', cols = ['#7fd8ff', '#ffc457', '#34d399', '#ff6fd8', '#a873f5', '#f87171'];
  const title: Record<string, string> = { truncated: 'Survival (%) by treatment', rainbow: 'Expression of 8 genes in 12 samples',
    noerror: 'Mean cell count (n = 3 per group)', dualaxis: 'Sales and temperature', pie3d: 'Share of reads by species',
    overplot: 'Gene length vs expression (50,000 genes)', spaghetti: 'Growth of 12 strains', nolabels: '' };
  const axes = <SvgG><Line x1={L} y1={T} x2={L} y2={B} stroke={soft} /><Line x1={L} y1={B} x2={R} y2={B} stroke={soft} /></SvgG>;
  const bars = (vals: number[], lo: number, hi: number, names: string[], c0: number) => vals.map((v, i) => {
    const bw = (R - L) / 5, x = L + bw * (0.6 + i * 1.4), y = B - ((v - lo) / (hi - lo)) * (B - T);
    return <SvgG key={i}><Rect x={x} y={y} width={bw} height={B - y} fill={cols[c0 + i]} />
      <SvgText x={x + bw / 2} y={B + 14} fill={soft} fontSize={10} textAnchor="middle">{names[i]}</SvgText></SvgG>;
  });
  let body: ReactNode = null;
  if (kind === 'truncated') {
    body = <SvgG>{axes}{[95, 96, 97, 98, 99, 100].map((v) => <SvgText key={v} x={L - 4} y={B - ((v - 95) / 5) * (B - T) + 3} fill={soft} fontSize={9} textAnchor="end">{v}</SvgText>)}
      {bars([96, 97.5, 99], 95, 100, ['Control', 'Drug A', 'Drug B'], 0)}</SvgG>;
  } else if (kind === 'rainbow') {
    const cw = (R - L) / 12, ch = (B - T) / 8;
    body = <SvgG>{Array.from({ length: 96 }, (_, k) => { const r = Math.floor(k / 12), c = k % 12, v = (Math.sin(r * 0.7 + c * 0.45) + 1) / 2;
      return <Rect key={k} x={L + c * cw} y={T + r * ch} width={cw - 1} height={ch - 1} fill={`hsl(${Math.round((1 - v) * 240)},100%,50%)`} />; })}</SvgG>;
  } else if (kind === 'noerror') {
    body = <SvgG>{axes}{bars([42, 55, 61], 0, 70, ['WT', 'KO-1', 'KO-2'], 3)}</SvgG>;
  } else if (kind === 'dualaxis') {
    const line = (vals: number[]) => vals.map((v, i) => `${L + ((R - L) * i) / (vals.length - 1)},${B - v * (B - T)}`).join(' ');
    body = <SvgG>{axes}<Line x1={R} y1={T} x2={R} y2={B} stroke={soft} />
      <Polyline points={line([0.2, 0.3, 0.35, 0.5, 0.62, 0.7, 0.8])} stroke={cols[0]} strokeWidth={2.4} fill="none" />
      <Polyline points={line([0.9, 0.75, 0.66, 0.5, 0.4, 0.3, 0.15])} stroke={cols[1]} strokeWidth={2.4} fill="none" />
      <SvgText x={L - 6} y={T + 8} fill={cols[0]} fontSize={10} textAnchor="end">€</SvgText>
      <SvgText x={R + 2} y={T + 8} fill={cols[1]} fontSize={10}>°C</SvgText></SvgG>;
  } else if (kind === 'pie3d') {
    const cx = W / 2, cy = H / 2 + 6, rx = 110, ry = 46, shares = [0.4, 0.25, 0.2, 0.15];
    const slice = (a0: number, a1: number, dy: number, fill: string, key: string) => {
      const p = (a: number) => `${cx + rx * Math.cos(a)},${cy + dy + ry * Math.sin(a)}`;
      return <Path key={key} d={`M${cx},${cy + dy} L${p(a0)} A${rx},${ry} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${p(a1)} Z`} fill={fill} />;
    };
    const parts: ReactNode[] = [];
    for (let d = 14; d > 0; d -= 2) { let a = 0.5; shares.forEach((s, i) => { parts.push(slice(a, a + s * 2 * Math.PI, d, '#333', `d${d}${i}`)); a += s * 2 * Math.PI; }); }
    let a = 0.5; shares.forEach((s, i) => { parts.push(slice(a, a + s * 2 * Math.PI, 0, cols[i], `t${i}`)); a += s * 2 * Math.PI; });
    body = <SvgG>{parts}</SvgG>;
  } else if (kind === 'overplot') {
    const rnd = seeded(3);
    const g = () => (rnd() + rnd() + rnd() - 1.5) / 1.5;
    body = <SvgG>{axes}{Array.from({ length: 900 }, (_, k) => { const x = 0.5 + g() * 0.35, y = 0.5 + (x - 0.5) * 0.6 + g() * 0.2;
      return x > 0 && x < 1 && y > 0 && y < 1 ? <Circle key={k} cx={L + x * (R - L)} cy={B - y * (B - T)} r={2.4} fill="#7fd8ff" /> : null; })}</SvgG>;
  } else if (kind === 'spaghetti') {
    const rnd = seeded(5);
    body = <SvgG>{axes}{Array.from({ length: 12 }, (_, s) => { let y = 0.1 + rnd() * 0.1; const pts = [`${L},${B - y * (B - T)}`];
      for (let i = 1; i < 12; i++) { y = Math.min(0.95, y + rnd() * 0.12); pts.push(`${L + ((R - L) * i) / 11},${B - y * (B - T)}`); }
      return <Polyline key={s} points={pts.join(' ')} stroke={`hsl(${205 + s * 3},70%,70%)`} strokeWidth={1.6} fill="none" />; })}</SvgG>;
  } else {
    const rnd = seeded(9);
    body = <SvgG>{axes}{Array.from({ length: 14 }, (_, i) => { const x = i / 13;
      return <Circle key={i} cx={L + x * (R - L)} cy={B - (0.15 + 0.7 * x + (rnd() - 0.5) * 0.16) * (B - T)} r={4} fill="#34d399" />; })}</SvgG>;
  }
  return (
    <View style={st.figure}>
      <Svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`}>
        <Rect x={0} y={0} width={W} height={H} fill="#11111c" />
        <SvgText x={L} y={14} fill="#e8e8f0" fontSize={11}>{title[kind] ?? ''}</SvgText>
        {body}
      </Svg>
    </View>
  );
}

const FACES: Record<string, Face> = {
  realfake: { game: 'realfake', kind: 'realfake', round: 10, hint: 'Real tool, or made up?',
    prompt: (q) => <NameCard text={q.name} />, choices: (q) => ({ options: ['Real tool', 'Made up'], right: q.real ? 0 : 1, big: true }),
    why: (q) => q.fact },
  genemon: { game: 'genemon', kind: 'genemon', round: 10, hint: 'Gene, or Pokémon?',
    prompt: (q) => <NameCard text={q.name} />, choices: (q) => ({ options: ['Gene', 'Pokémon'], right: q.answer === 'gene' ? 0 : 1, big: true }),
    why: (q) => q.fact },
  first: { game: 'first', kind: 'year', round: 12, hint: 'Which came first?',
    load: (items) => {
      const rest = items.slice(), pairs: Q[] = [];
      while (rest.length >= 2 && pairs.length < 6) {
        const a = rest.shift()!, bi = rest.findIndex((x) => x.year !== a.year);
        if (bi < 0) break;
        const b = rest.splice(bi, 1)[0];
        pairs.push({ id: `${a.id}+${b.id}`, kind: 'pair', level: Math.max(a.level, b.level), terms: [...new Set([...a.terms, ...b.terms])].sort(), a, b });
      }
      return pairs;
    },
    prompt: (q) => <Text style={st.task}>{q.a!.name}   or   {q.b!.name}?</Text>,
    choices: (q) => ({ options: [q.a!.name, q.b!.name], right: q.a!.year < q.b!.year ? 0 : 1, big: true }),
    why: (q) => `${q.a!.name}: ${q.a!.year} (${q.a!.event}). ${q.b!.name}: ${q.b!.year} (${q.b!.event}).`,
    answered: (q, right) => [q.a!, q.b!].map((x) => ({ id: x.id, right, level: x.level, terms: x.terms })) },
  reviewer: { game: 'reviewer', kind: 'review', round: 5, hint: 'Reviewer 2 has read your paper. Reply well.',
    prompt: (q, s) => <Angler comment={q.comment} chance={s.chance} mood={s.mood} />,
    choices: (q) => { const options = shuffle([q.right, ...q.wrong]); return { options, right: options.indexOf(q.right) }; },
    why: (q, right) => (right ? 'Reviewer 2 grumbles, but nods.' : `Reviewer 2's lantern flickers. Better: ${q.right[0].toLowerCase()}${q.right.slice(1)}.`) },
  reef: { game: 'reef', kind: 'snippet', round: 5, hint: 'Tap the line with the bug before the bubble reaches the top.', timed: 20,
    prompt: (q) => <Text style={[st.small, { color: C.violet, fontWeight: '800' }]}>{q.lang}</Text>,
    choices: (q) => ({ options: q.lines as string[], right: q.bug, lines: true }), why: (q) => q.why },
  figure: { game: 'figure', kind: 'figure', round: 4, hint: "What's wrong with this figure?",
    prompt: (q) => <Figure kind={q.draw} />,
    choices: (q) => { const options = shuffle([q.right, ...(q.wrong as string[]).slice(0, 3)]); return { options, right: options.indexOf(q.right) }; },
    why: (q) => `${q.right}.` },
};
export const CARD_GAMES = Object.keys(FACES);

export function CardGame({ id, onAgain, onHub, Result }: {
  id: string; onAgain: () => void; onHub: () => void; Result: (p: { r: Result; onAgain: () => void; onHub: () => void }) => ReactNode;
}) {
  const face = FACES[id];
  const { profile } = useApp();
  const [items, setItems] = useState<Q[]>([]);
  const [i, setI] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [chance, setChance] = useState(50);
  const [mood, setMood] = useState(0);
  const [left, setLeft] = useState(face.timed ?? 0);
  const answers = useRef<G.Answer[]>([]);
  const t0 = useRef(0);
  const bonus = useRef(0);
  useEffect(() => {
    roundItems(face.game, face.kind, face.round, profile?.weights ?? {})
      .then((xs) => { t0.current = Date.now(); setItems(face.load ? face.load(xs) : xs); }).catch(() => setItems([]));
  }, [face, profile]);
  const q = items[i];
  const ch = useMemo(() => (q ? face.choices(q) : null), [q, face]);
  const pick = (k: number) => {
    if (picked !== null || !q || !ch) return;
    setPicked(k);
    const right = k === ch.right;
    answers.current.push(...(face.answered ? face.answered(q, right) : [{ id: q.id, right, level: q.level, terms: q.terms }]));
    if (id === 'reviewer') { setChance((c) => Math.max(0, Math.min(100, c + (right ? 12 : -15)))); setMood(right ? 1 : -1); }
    if (id === 'reef' && right && left > (face.timed ?? 0) / 2) bonus.current += 5 * q.level;
  };
  useEffect(() => {                                  // the bubble rises; at the top, time's up
    if (!face.timed || picked !== null || !q) return;
    const timed = face.timed;
    let ticks = 0;
    const t = setInterval(() => {
      ticks += 1;
      const l = timed - ticks / 10;
      setLeft(l);
      if (l <= 0) {
        clearInterval(t);
        setPicked(-1);
        answers.current.push({ id: q.id, right: false, level: q.level, terms: q.terms });
      }
    }, 100);
    return () => clearInterval(t);
  }, [face.timed, picked, q]);
  const next = async () => {
    if (i + 1 < items.length) { setI(i + 1); setPicked(null); setMood(0); setLeft(face.timed ?? 0); return; }
    if (id === 'reviewer') bonus.current += Math.max(0, chance - 50);
    setResult(await finish(face.game, answers.current, secondsSince(t0.current), bonus.current));
  };
  if (result) return <Result r={result} onAgain={onAgain} onHub={onHub} />;
  if (!q || !ch) return <Text style={st.small}>Getting the questions ready…</Text>;
  const mark = (k: number) => (picked === null ? '' : k === ch.right ? 'right' : k === picked ? 'wrong' : '');
  const right = picked === ch.right;
  return (
    <View style={{ gap: 10 }}>
      <Text style={st.small}>{i + 1} of {items.length} · {face.hint}</Text>
      {face.prompt(q, { chance, mood, left })}
      {ch.lines ? (
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <View style={st.code}>
            {ch.options.map((line, k) => (
              <Pressable key={k} onPress={() => pick(k)} accessibilityRole="button" accessibilityLabel={`Line ${k + 1}`}
                         style={[st.codeRow, mark(k) === 'right' && { backgroundColor: 'rgba(52,211,153,0.22)' }, mark(k) === 'wrong' && { backgroundColor: 'rgba(248,113,113,0.22)' }]}>
                <Text style={st.codeText}>{String(k + 1).padStart(2)}  {line}</Text>
              </Pressable>
            ))}
          </View>
          <View style={st.tube}><View style={[st.bub, { bottom: `${Math.max(0, Math.min(1, 1 - left / (face.timed ?? 1))) * 88}%` }]} /></View>
        </View>
      ) : (
        <View style={ch.big ? { flexDirection: 'row', gap: 10 } : { gap: 8 }}>
          {ch.options.map((o, k) => (
            <Pressable key={k} onPress={() => pick(k)} accessibilityRole="button"
                       style={[ch.big ? st.bigOpt : st.opt, mark(k) === 'right' && { borderColor: C.green }, mark(k) === 'wrong' && { borderColor: C.red }]}>
              <Text style={ch.big ? st.bigOptText : st.body}>{o}</Text>
            </Pressable>
          ))}
        </View>
      )}
      {picked !== null ? <>
        <Text style={st.body}>{right ? '✅ Right. ' : picked < 0 ? '⏱ Time\'s up. ' : '❌ Not quite. '}{face.why(q, right)}</Text>
        <Pressable onPress={next} style={st.primary} accessibilityRole="button">
          <Text style={st.primaryText}>{i + 1 < items.length ? 'Next ›' : 'See how you did'}</Text>
        </Pressable>
      </> : null}
    </View>
  );
}

const st = StyleSheet.create({
  small: { color: C.muted, fontSize: 12.5, lineHeight: 18 },
  body: { color: C.text, fontSize: 14, lineHeight: 20 },
  task: { color: C.text, fontSize: 18, fontWeight: '800' },
  nameCard: { minHeight: 140, borderRadius: 20, borderWidth: 2, borderColor: C.violet, backgroundColor: C.card, alignItems: 'center', justifyContent: 'center', padding: 16 },
  name: { color: C.text, fontSize: 26, fontWeight: '800', textAlign: 'center' },
  bigOpt: { flex: 1, borderWidth: 2, borderColor: tint(0.12), backgroundColor: C.cardHi, borderRadius: 14, paddingVertical: 16, alignItems: 'center' },
  bigOptText: { color: C.text, fontSize: 16, fontWeight: '800' },
  opt: { borderWidth: 2, borderColor: tint(0.12), backgroundColor: C.cardHi, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12 },
  primary: { alignSelf: 'flex-start', backgroundColor: C.violet, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 16 },
  primaryText: { color: '#fff', fontWeight: '800', fontSize: 14 },
  bubble: { backgroundColor: C.sheet, borderWidth: 1, borderColor: C.violet, borderRadius: 12, padding: 10 },
  bubbleText: { color: C.text, fontWeight: '800', fontSize: 14 },
  bar: { height: 8, borderRadius: 4, backgroundColor: tint(0.12), overflow: 'hidden' },
  barFill: { height: 8 },
  code: { flex: 1, backgroundColor: C.dark ? '#0d0d18' : '#ffffff', borderRadius: 12, paddingVertical: 6 },
  codeRow: { paddingVertical: 6, paddingHorizontal: 8, borderRadius: 6 },
  codeText: { color: C.dark ? '#f0f0f5' : '#241f1a', fontFamily: 'monospace', fontSize: 12.5 },
  tube: { width: 22, borderRadius: 11, borderWidth: 1.5, borderColor: 'rgba(127,216,255,0.5)', position: 'relative' },
  bub: { position: 'absolute', left: 3, width: 13, height: 13, borderRadius: 7, borderWidth: 2, borderColor: '#7fd8ff', backgroundColor: 'rgba(127,216,255,0.25)' },
  figure: { borderRadius: 12, overflow: 'hidden' },
});
