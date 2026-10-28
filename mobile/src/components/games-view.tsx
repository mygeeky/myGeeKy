// 🎮 Games (Play with GeeKOc): the hub of every game and the games themselves, the desktop's gui/games_ui.py on the
// same GEMS rules (lib/gems.ts, lib/games-store.ts). The hub shows each game's icon, level, best and how far the next
// level is; a game opens in place with "‹ All games". On the phone Terminal typing is pick-only (no typing), and
// Word Hunter is drag-to-steer, tap-an-asteroid-to-fire. Everything shown comes from the pack: plain text only.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Image, PanResponder, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { useApp } from '../lib/app-state';
import * as G from '../lib/gems';
import { finish, questions, roundItems, summary, type Question } from '../lib/games-store';
import { C, tint } from '../lib/theme';
import { GeekMover } from './tour-overlay';
import { gameIcon } from './game-icons';
import { CARD_GAMES, CardGame } from './games-cards';
import { ARCADE_GAMES, ArcadeGame } from './games-arcade';
import { ADVENTURES, Adventure } from './games-adventure';


const BUILT = ['hunter', 'terminal', ...CARD_GAMES, ...ARCADE_GAMES, ...ADVENTURES];   // playable now; the rest show their card and "coming next"
type Summary = Awaited<ReturnType<typeof summary>>;
type Result = Awaited<ReturnType<typeof finish>>;
const secondsSince = (t0: number) => (Date.now() - t0) / 1000;
const shuffle = <T,>(xs: T[]): T[] => { const a = xs.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };

export function GamesView() {
  const [open, setOpen] = useState<string | null>(null);
  const [s, setS] = useState<Summary | null>(null);
  const [round, setRound] = useState(0);              // a new round of the open game
  const reload = useCallback(() => { summary().then(setS).catch(() => undefined); }, []);
  useEffect(reload, [reload, open]);
  if (open) {
    const g = G.GAMES.find((x) => x.id === open)!;
    return (
      <View style={st.wrap}>
        <View style={st.head}>
          <Pressable onPress={() => setOpen(null)} style={st.back} accessibilityRole="button" accessibilityLabel="All games">
            <Text style={st.backText}>‹  All games</Text>
          </Pressable>
          <Image source={gameIcon(g.id)} style={{ width: 28, height: 28 }} />
          <Text style={st.headTitle} numberOfLines={1}>{g.title}</Text>
        </View>
        {g.id === 'terminal' ? <TerminalPhone key={round} onAgain={() => setRound((r) => r + 1)} onHub={() => setOpen(null)} />
          : g.id === 'hunter' ? <WordHunterPhone key={round} onAgain={() => setRound((r) => r + 1)} onHub={() => setOpen(null)} />
          : CARD_GAMES.includes(g.id) ? <CardGame key={`${g.id}:${round}`} id={g.id} onAgain={() => setRound((r) => r + 1)} onHub={() => setOpen(null)} Result={ResultCard} />
          : ARCADE_GAMES.includes(g.id) ? <ArcadeGame key={`${g.id}:${round}`} id={g.id} onAgain={() => setRound((r) => r + 1)} onHub={() => setOpen(null)} Result={ResultCard} />
          : ADVENTURES.includes(g.id) ? <Adventure key={`${g.id}:${round}`} id={g.id} onAgain={() => setRound((r) => r + 1)} onHub={() => setOpen(null)} Result={ResultCard} />
          : <ComingNext id={g.id} about={g.about} />}
      </View>
    );
  }
  const stats = Object.fromEntries((s?.games ?? []).map((x) => [x.id, x]));
  const order = [...G.GAMES.filter((g) => BUILT.includes(g.id)), ...G.GAMES.filter((g) => !BUILT.includes(g.id))];
  return (
    <View style={st.wrap}>
      <View style={st.hero}>
        <Image source={gameIcon('hub')} style={{ width: 84, height: 84 }} />
        <View style={{ flex: 1 }}>
          <Text style={st.h1}>Play with GeeKOc</Text>
          <Text style={st.muted}>Player level {s?.player_level ?? 1} · {s?.minutes ?? 0} min played · {s?.xp ?? 0} XP</Text>
          <Text style={st.small}>Short games from your own field. A mistake always says why.</Text>
        </View>
      </View>
      <View style={st.grid}>
        {order.map((g) => {
          const x = stats[g.id];
          const built = BUILT.includes(g.id);
          return (
            <Pressable key={g.id} onPress={() => { setRound(0); setOpen(g.id); }} style={st.card} accessibilityRole="button" accessibilityLabel={g.title}>
              <Image source={gameIcon(g.id)} style={{ width: 52, height: 52 }} />
              <View style={{ flex: 1, gap: 3 }}>
                <Text style={st.cardTitle} numberOfLines={2}>{g.title}</Text>
                {built ? <>
                  <Text style={st.muted}>Level {x?.level ?? 1}{x?.best ? ` · best ${x.best}` : ' · new'}</Text>
                  <View style={st.bar}><View style={[st.barFill, { width: `${Math.round((x?.progress ?? 0) * 100)}%` }]} /></View>
                </> : <Text style={st.soon}>Coming next</Text>}
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function ComingNext({ id, about }: { id: string; about: string }) {
  return (
    <View style={{ alignItems: 'center', gap: 12, paddingVertical: 16 }}>
      <Image source={gameIcon(id)} style={{ width: 150, height: 150 }} />
      <Text style={[st.cardTitle, { textAlign: 'center' }]}>{about}</Text>
      <Text style={[st.muted, { textAlign: 'center' }]}>This game is coming next: its questions are ready, its screen is being built.</Text>
    </View>
  );
}

function ResultCard({ r, onAgain, onHub }: { r: Result; onAgain: () => void; onHub: () => void }) {
  return (
    <View style={st.result}>
      <Text style={st.stars}>{'★'.repeat(r.stars)}{'☆'.repeat(3 - r.stars)}   {r.points} points</Text>
      <Text style={st.body}>{r.right} of {r.answered} right{r.new_best ? ' · a new best!' : ` · best ${r.best}`}</Text>
      <Text style={[st.body, { fontWeight: '800' }]}>Level {r.level}{r.level_up ? '  ·  level up!' : ''}{r.next_level_xp ? `  ·  ${r.next_level_xp - r.xp} XP to the next` : ''}</Text>
      {r.player_level_up ? <Text style={[st.body, { color: C.green, fontWeight: '800' }]}>You reached player level {r.player_level}!</Text> : null}
      {r.knows?.length ? <Text style={[st.small, { color: C.green }]}>You know: {r.knows.slice(0, 4).join(', ')}</Text> : null}
      {r.learning?.length ? <Text style={st.small}>You&apos;re learning: {r.learning.slice(0, 4).join(', ')}</Text> : null}
      <View style={st.row}>
        <Pressable onPress={onAgain} style={st.primary} accessibilityRole="button"><Text style={st.primaryText}>Play again</Text></Pressable>
        <Pressable onPress={onHub} style={st.ghost} accessibilityRole="button"><Text style={st.ghostText}>All games</Text></Pressable>
      </View>
    </View>
  );
}

// ------------------------------------------------------------------------------------------------ Terminal typing
function TerminalPhone({ onAgain, onHub }: { onAgain: () => void; onHub: () => void }) {
  const { profile } = useApp();
  const [items, setItems] = useState<G.Item[]>([]);
  const [i, setI] = useState(0);
  const [chosen, setChosen] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const answers = useRef<G.Answer[]>([]);
  const t0 = useRef(0);
  useEffect(() => {
    roundItems('terminal', 'command', 5, profile?.weights ?? {}).then((xs) => { t0.current = Date.now(); setItems(xs); }).catch(() => setItems([]));
  }, [profile]);
  const it = items[i];
  const opts = useMemo(() => (it ? shuffle([...it.right, it.wrong.cmd]) : []), [it]);
  if (result) return <ResultCard r={result} onAgain={onAgain} onHub={onHub} />;
  if (!it) return <Text style={st.muted}>Getting the commands ready…</Text>;
  const pick = (cmd: string) => {
    if (chosen) return;
    setChosen(cmd);
    answers.current.push({ id: it.id, right: it.right.includes(cmd), level: it.level, terms: it.terms });
  };
  const next = async () => {
    if (i + 1 < items.length) { setI(i + 1); setChosen(''); return; }
    setResult(await finish('terminal', answers.current, secondsSince(t0.current)));
  };
  const right = chosen && it.right.includes(chosen);
  return (
    <View style={{ gap: 10 }}>
      <Text style={st.muted}>{i + 1} of {items.length}</Text>
      <Text style={st.task}>$ {it.task}</Text>
      <Text style={st.small}>Two of these do it. Tap one that does.</Text>
      {opts.map((cmd) => {
        const mark = !chosen ? '' : it.right.includes(cmd) ? 'right' : cmd === chosen ? 'wrong' : '';
        return (
          <Pressable key={cmd} onPress={() => pick(cmd)} accessibilityRole="button"
                     style={[st.cmd, mark === 'right' && { borderColor: C.green }, mark === 'wrong' && { borderColor: C.red }]}>
            <Text style={st.cmdText}>{cmd}</Text>
          </Pressable>
        );
      })}
      {chosen ? <>
        <Text style={st.body}>{right ? '✅ Right.' : `❌ ${it.wrong.why}`}</Text>
        <Pressable onPress={next} style={[st.primary, { alignSelf: 'flex-start' }]} accessibilityRole="button">
          <Text style={st.primaryText}>{i + 1 < items.length ? 'Next ›' : 'See how you did'}</Text>
        </Pressable>
      </> : null}
    </View>
  );
}

// ------------------------------------------------------------------------------------------------ Word Hunter
const QUIZ_OF: Record<string, string> = { gwas: 'gwas', 'single-cell': 'single-cell-rna-seq', python: 'python-data-analysis', r: 'r-data-analysis',
  'machine learning': 'ml-in-practice', git: 'git-github-teamwork', statistics: 'stats-for-experiments', visualization: 'figures-for-papers',
  workflow: 'nextflow', imaging: 'image-analysis-fiji' };
type Rock = { key: number; x: number; y: number; vx: number; vy: number; r: number; word: string; set: G.Item; good: boolean };
type World = {
  sets: G.Item[]; waves: G.Item[]; wave: number; shields: number; rocks: Rock[]; queue: [string, G.Item][];
  spawnIn: number; paused: boolean; msg: string; msgT: number; laser: null | { x: number; y: number; t: number };
  answers: G.Answer[]; t0: number; key: number; mood: string; ended: boolean; w: number; h: number;
};
type Snap = { rocks: Rock[]; laser: World['laser']; msg: string; shields: number; wave: number; waves: number;
              set: G.Item | null; mood: string };
const newWorld = (): World => ({ sets: [], waves: [], wave: 0, shields: 3, rocks: [], queue: [], spawnIn: 0, paused: true,
  msg: '', msgT: 0, laser: null, answers: [], t0: 0, key: 0, mood: 'cheer', ended: false, w: 0, h: 0 });
const snapOf = (w: World): Snap => ({ rocks: w.rocks.map((r) => ({ ...r })), laser: w.laser && { ...w.laser },
  msg: w.msgT > 0 ? w.msg : '', shields: w.shields, wave: w.wave, waves: w.waves.length, set: w.waves[w.wave] ?? null, mood: w.mood });

function buildWave(w: World) {
  const ws = w.waves[w.wave];
  if (!ws) return;
  const near = w.sets.filter((s) => s.id !== ws.id && s.terms.some((t) => ws.terms.includes(t)));
  const far = w.sets.filter((s) => s.id !== ws.id && !near.includes(s));
  const pool = w.wave === 0 ? far : w.wave === 1 ? [...far, ...near] : (near.length ? near : far);
  const decoys = shuffle(pool.flatMap((s) => (s.words as string[]).filter((x) => !ws.words.includes(x)).map((x) => [x, s] as [string, G.Item]))).slice(0, 4 + w.wave);
  const mine = shuffle(ws.words as string[]).slice(0, 6).map((x) => [x, ws] as [string, G.Item]);
  w.queue = shuffle([...mine, ...decoys]);
}
const answer = (w: World, word: string, s: G.Item, right: boolean) => { w.answers.push({ id: `${s.id}:${word}`, right, level: s.level, terms: s.terms }); };

function WordHunterPhone({ onAgain, onHub }: { onAgain: () => void; onHub: () => void }) {
  const { profile } = useApp();
  const world = useRef<World>(newWorld());           // touched only by the loop and by taps, never while drawing
  // the round's short waits (the next wave, the end): cleared if you leave, so a round you left is never saved
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const later = (fn: () => void, ms: number) => { timers.current.push(setTimeout(fn, ms)); };
  useEffect(() => { const list = timers.current; return () => list.forEach(clearTimeout); }, []);
  const [view, setView] = useState<Snap>(() => snapOf(newWorld()));
  const [card, setCard] = useState<'wave' | 'question' | null>('wave');
  const [result, setResult] = useState<Result | null>(null);
  const [q, setQ] = useState<Question | null>(null);
  const [qPick, setQPick] = useState('');

  const end = useCallback(async () => {
    const w = world.current;
    if (w.ended) return;
    w.ended = true;
    w.paused = true;
    setResult(await finish('hunter', w.answers, secondsSince(w.t0)));
  }, []);
  const nextWave = useCallback(() => {
    const w = world.current;
    w.wave += 1;
    if (w.wave >= w.waves.length || w.shields <= 0) { end(); return; }
    buildWave(w);
    setView(snapOf(w));
    setCard('wave');
  }, [end]);
  const between = useCallback(() => {
    const w = world.current;
    const topic = w.waves[w.wave]?.terms.map((t) => QUIZ_OF[t]).find(Boolean);
    const pool = topic ? questions().filter((x) => x.protocol === topic) : [];
    if (pool.length) { setQ(pool[Math.floor(Math.random() * pool.length)]); setQPick(''); setCard('question'); }
    else nextWave();
  }, [nextWave]);

  useEffect(() => {
    roundItems('hunter', 'wordset', 3, profile?.weights ?? {}).then((waves) => {
      const w = world.current;
      w.sets = G.itemsOf(require('../data/games.json'), 'wordset');
      w.waves = waves;
      w.t0 = Date.now();
      buildWave(w);
      setView(snapOf(w));
    }).catch(() => undefined);
  }, [profile]);

  const wake = useRef<() => void>(() => undefined);      // starts the frame loop again after it rested
  useEffect(() => {
    let raf = 0, last = Date.now(), wasStill = false, running = false;
    const loop = () => {
      const w = world.current;
      const now = Date.now(), dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (!w.paused && w.w) {
        w.spawnIn -= dt;
        if (w.queue.length && w.spawnIn <= 0) {
          const [word, s] = w.queue.pop()!;
          const r = Math.max(28, word.length * 4.6 + 14);
          const speed = (w.h / 13) + w.wave * 8;
          w.rocks.push({ key: w.key++, x: r + Math.random() * (w.w - 2 * r), y: -r, vx: (Math.random() - 0.5) * 30, vy: speed + Math.random() * 16,
                         r, word, set: s, good: s === w.waves[w.wave] });
          w.spawnIn = Math.max(0.8, 1.5 - w.wave * 0.25);
        }
        for (const k of w.rocks) {
          k.x += k.vx * dt; k.y += k.vy * dt;
          if (k.x < k.r || k.x > w.w - k.r) k.vx *= -1;
        }
        for (const k of w.rocks.filter((k) => k.y - k.r > w.h - 40)) {
          if (k.good) { answer(w, k.word, k.set, false); w.msg = `Missed: ${k.word} is one of the ${w.waves[w.wave].name}.`; w.msgT = 2.6; }
          else answer(w, k.word, k.set, true);                 // rightly let past
        }
        w.rocks = w.rocks.filter((k) => k.y - k.r <= w.h - 40);
        if (!w.queue.length && !w.rocks.length) { w.paused = true; later(between, 300); }
      }
      w.msgT -= dt;
      if (w.laser) { w.laser.t -= dt; if (w.laser.t <= 0) w.laser = null; }
      // a card is up or the round is over: nothing moves, so draw once instead of 60 times a second
      const still = w.paused && w.msgT <= 0 && !w.laser;
      if (still && wasStill) { running = false; return; }      // rests (no frames at all) until Go wakes it
      setView(snapOf(w));
      wasStill = still;
      raf = requestAnimationFrame(loop);
    };
    wake.current = () => { if (!running) { running = true; wasStill = false; last = Date.now(); raf = requestAnimationFrame(loop); } };
    wake.current();
    return () => { cancelAnimationFrame(raf); wake.current = () => undefined; };
  }, [between]);

  const hit = (key: number) => {
    const w = world.current;
    const k = w.rocks.find((x) => x.key === key);
    if (w.paused || !k) return;
    w.rocks = w.rocks.filter((x) => x !== k);
    w.laser = { x: k.x, y: k.y, t: 0.15 };
    if (k.good) { answer(w, k.word, k.set, true); w.mood = 'cheer'; }
    else {
      answer(w, k.word, k.set, false);
      w.shields -= 1; w.mood = 'think';
      w.msg = `${k.word} is ${k.set.what}, not one of the ${w.waves[w.wave].name}.`; w.msgT = 2.8;
      if (w.shields <= 0) later(end, 400);
    }
  };
  const [shipX, setShipX] = useState(0);              // where the drag put GeeKOc (only the drawing needs it)
  const [pan] = useState(() => PanResponder.create({
    onMoveShouldSetPanResponder: (_e, g) => Math.abs(g.dx) > 4,
    onPanResponderMove: (e) => setShipX(e.nativeEvent.locationX),
  }));
  const go = () => { const w = world.current; setCard(null); w.paused = false; w.spawnIn = 0.3; wake.current(); };
  const pickQ = (o: string) => {
    if (qPick || !q) return;
    setQPick(o);
    const w = world.current;
    w.answers.push({ id: q.id, right: o === q.options[0], level: 1, terms: w.waves[w.wave]?.terms ?? [] });
  };

  if (result) return <ResultCard r={result} onAgain={onAgain} onHub={onHub} />;
  return (
    <FieldView view={view} card={card} q={q} qPick={qPick} shipXRaw={shipX} pan={pan}
               onLayout={(w, h) => { world.current.w = w; world.current.h = h; }}
               onHit={hit} onGo={go} onPickQ={pickQ} onNextWave={() => { setCard(null); nextWave(); }} />
  );
}

function FieldView({ view, card, q, qPick, shipXRaw, pan, onLayout, onHit, onGo, onPickQ, onNextWave }: {
  view: Snap; card: 'wave' | 'question' | null; q: Question | null; qPick: string; shipXRaw: number;
  pan: ReturnType<typeof PanResponder.create>; onLayout: (w: number, h: number) => void; onHit: (key: number) => void;
  onGo: () => void; onPickQ: (o: string) => void; onNextWave: () => void;
}) {
  const [size, setSize] = useState({ w: 0, h: 0 });
  const { height: screenH } = useWindowDimensions();
  const fieldH = Math.max(380, Math.round(screenH * 0.66));   // most of the screen: room for the asteroids to fall
  const shipX = Math.max(40, Math.min(size.w - 40, shipXRaw || size.w / 2));
  const shipY = size.h - 34;
  const set = view.set;
  return (
    <View>
      <Text style={st.muted}>Wave {Math.min(view.wave + 1, Math.max(1, view.waves))} of {view.waves || 3} · {'♥'.repeat(Math.max(0, view.shields))}{'♡'.repeat(3 - Math.max(0, view.shields))}</Text>
      <View style={[st.field, { height: fieldH }]} {...pan.panHandlers}
            onLayout={(e) => { const { width, height } = e.nativeEvent.layout; setSize({ w: width, h: height }); onLayout(width, height); }}>
        {set ? <Text style={st.banner}>Shoot: {set.name}</Text> : null}
        {view.rocks.map((k) => (
          <Pressable key={k.key} onPress={() => onHit(k.key)} accessibilityRole="button" accessibilityLabel={k.word}
                     style={[st.rock, { left: k.x - k.r, top: k.y - k.r * 0.8, width: k.r * 2, height: k.r * 1.6, borderRadius: k.r }]}>
            <Text style={st.rockText} numberOfLines={1}>{k.word}</Text>
          </Pressable>
        ))}
        {view.laser ? (() => {
          const dx = view.laser.x - shipX, dy = view.laser.y - (shipY - 30), len = Math.hypot(dx, dy);
          return <View pointerEvents="none" style={{ position: 'absolute', left: shipX + dx / 2 - len / 2, top: shipY - 30 + dy / 2 - 1.5, width: len, height: 3,
                                                       backgroundColor: '#ffc457', borderRadius: 2, transform: [{ rotate: `${Math.atan2(dy, dx)}rad` }] }} />;
        })() : null}
        {size.w ? <>
          <View pointerEvents="none" style={[st.saucer, { left: shipX - 44, top: shipY }]} />
          <View pointerEvents="none" style={{ position: 'absolute', left: shipX - 36, top: shipY - 58 }}>
            <GeekMover pose={view.mood === 'cheer' ? 'cheer' : 'think'} size={72} paused={card !== null} />
          </View>
        </> : null}
        {view.msg ? <Text style={st.msg}>{view.msg}</Text> : null}
        {card === 'wave' && set ? (
          <View style={st.over}>
            <View style={st.result}>
              <Text style={st.cardTitle}>Wave {view.wave + 1}: shoot the {set.name}</Text>
              <Text style={st.small}>Tap the right words; let the others drift past. Drag to move GeeKOc. A wrong shot costs a shield.</Text>
              <Pressable onPress={onGo} style={[st.primary, { alignSelf: 'flex-start' }]} accessibilityRole="button">
                <Text style={st.primaryText}>Go</Text>
              </Pressable>
            </View>
          </View>
        ) : null}
        {card === 'question' && q ? (
          <View style={st.over}>
            <View style={st.result}>
              <Text style={st.cardTitle}>{q.q}</Text>
              {shuffleOnce(q).map((o) => {
                const mark = !qPick ? '' : o === q.options[0] ? 'right' : o === qPick ? 'wrong' : '';
                return (
                  <Pressable key={o} accessibilityRole="button" onPress={() => onPickQ(o)}
                             style={[st.cmd, mark === 'right' && { borderColor: C.green }, mark === 'wrong' && { borderColor: C.red }]}>
                    <Text style={st.body}>{o}</Text>
                  </Pressable>
                );
              })}
              {qPick ? <>
                <Text style={st.small}>{qPick === q.options[0] ? '✅ ' : '❌ '}{q.why}{q.source?.title ? `\nSource: ${q.source.title}` : ''}</Text>
                <Pressable onPress={onNextWave} style={[st.primary, { alignSelf: 'flex-start' }]} accessibilityRole="button">
                  <Text style={st.primaryText}>Next wave ›</Text>
                </Pressable>
              </> : null}
            </View>
          </View>
        ) : null}
      </View>
    </View>
  );
}

const shuffled = new Map<string, string[]>();
const shuffleOnce = (q: Question) => { if (!shuffled.has(q.id)) shuffled.set(q.id, shuffle(q.options)); return shuffled.get(q.id)!; };

const st = StyleSheet.create({
  wrap: { gap: 12 },
  hero: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 10, borderRadius: 18, backgroundColor: C.card },
  h1: { color: C.text, fontSize: 20, fontWeight: '800' },
  muted: { color: C.muted, fontSize: 12.5 },
  small: { color: C.muted, fontSize: 12.5, lineHeight: 18 },
  body: { color: C.text, fontSize: 14, lineHeight: 20 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  card: { width: '48%', flexGrow: 1, flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 16, backgroundColor: C.card },
  cardTitle: { color: C.text, fontSize: 14.5, fontWeight: '800' },
  soon: { color: C.amber, fontSize: 12, fontWeight: '800' },
  bar: { height: 5, borderRadius: 3, backgroundColor: tint(0.12), overflow: 'hidden' },
  barFill: { height: 5, backgroundColor: C.violet },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  back: { backgroundColor: C.violet, borderRadius: 12, paddingVertical: 6, paddingHorizontal: 12 },
  backText: { color: '#fff', fontWeight: '800', fontSize: 13 },
  headTitle: { color: C.text, fontSize: 16, fontWeight: '800', flex: 1 },
  task: { color: C.text, fontSize: 16, fontWeight: '800' },
  cmd: { borderWidth: 2, borderColor: tint(0.12), backgroundColor: C.cardHi, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12 },
  cmdText: { color: C.text, fontFamily: 'monospace', fontSize: 13.5 },
  primary: { backgroundColor: C.violet, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 16 },
  primaryText: { color: '#fff', fontWeight: '800', fontSize: 14 },
  ghost: { backgroundColor: C.cardHi, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 16 },
  ghostText: { color: C.text, fontWeight: '700', fontSize: 14 },
  row: { flexDirection: 'row', gap: 10, marginTop: 4 },
  result: { backgroundColor: C.sheet, borderRadius: 16, padding: 14, gap: 8, borderWidth: 1, borderColor: tint(0.1) },
  stars: { color: C.amber, fontSize: 20, fontWeight: '800' },
  field: { marginTop: 6, borderRadius: 16, overflow: 'hidden', backgroundColor: '#070712' },
  banner: { position: 'absolute', left: 0, right: 0, top: 0, paddingVertical: 6, textAlign: 'center', color: '#f0f0f5', fontWeight: '800',
            fontSize: 13.5, backgroundColor: 'rgba(139,69,224,0.35)' },
  rock: { position: 'absolute', backgroundColor: '#3b3550', borderWidth: 2, borderColor: '#6b6290', alignItems: 'center', justifyContent: 'center' },
  rockText: { color: '#fff', fontWeight: '800', fontSize: 12.5, paddingHorizontal: 4 },
  saucer: { position: 'absolute', width: 88, height: 22, borderRadius: 11, backgroundColor: '#7fd8ff' },
  msg: { position: 'absolute', left: 12, right: 12, bottom: 70, color: '#f0f0f5', backgroundColor: 'rgba(28,28,44,0.92)', borderRadius: 10,
         paddingVertical: 6, paddingHorizontal: 10, textAlign: 'center', fontSize: 12.5, fontWeight: '700' },
  over: { ...StyleSheet.absoluteFill, backgroundColor: 'rgba(7,7,18,0.72)', justifyContent: 'center', padding: 14 },
});
