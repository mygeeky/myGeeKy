// The arcade games of Play with GeeKOc, the desktop's gui/games_arcade.py on the same GEMS rules and the same
// numbers: Whack-a-bug (tap the bugs, spare the friends, 30 s), Sort the catch (tap a net to drop the falling name in),
// GeeKOc run (tap to jump the bugs; at a gate, jump for the top answer or stay low for the bottom one) and Flappy
// GeeKOc (tap to puff ink and swim up through the right answer's gap). One engine runs them all: the world lives in a
// ref touched only by the loop and by taps, the screen draws a plain snapshot, and the field is 420 wide in game units
// (as on the desktop), scaled to the phone. Everything shown comes from the pack: plain text only.
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { useApp } from '../lib/app-state';
import * as G from '../lib/gems';
import { finish, roundItems } from '../lib/games-store';
import { C, tint } from '../lib/theme';
import { GeekMover } from './tour-overlay';

type Result = Awaited<ReturnType<typeof finish>>;
export type Ask = { title: string; kicker?: string; options: string[]; right: number; why: string; go: string };
export type Api = {
  answer: (id: string, right: boolean, level: number, terms: string[]) => void; say: (t: string, s?: number) => void;
  end: (outro?: { title: string; text: string }) => void;              // an outro: a card before the result (Rise's pipeline)
  ask: (q: Ask, done: (right: boolean) => void) => void;                // a question over the field (the maze's doors)
};
export type World = Record<string, any> & { W: number; H: number; msg: string; msgT: number; bonus: number; hud: string };
export type Spec = {
  game: string; title: string; howto: string; bg: string;
  load: (weights: Record<string, number>) => Promise<G.Item[]>;
  init: (items: G.Item[], w: World) => void;
  step: (w: World, dt: number, api: Api) => void;
  press: (w: World, x: number, y: number, api: Api) => void;
  snap: (w: World) => Record<string, any>;
  draw: (v: Record<string, any>, k: number) => ReactNode;
};
export const W0 = 420;
const shuffle = <T,>(xs: T[]): T[] => { const a = xs.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const pick = <T,>(xs: T[]): T => xs[Math.floor(Math.random() * xs.length)];
const rnd = (a: number, b: number) => a + Math.random() * (b - a);

export function Pill({ text, x, y, bg, k, ink = '#1a1428', size = 13 }: { text: string; x: number; y: number; bg: string; k: number; ink?: string; size?: number }) {
  return (
    <View pointerEvents="none" style={{ position: 'absolute', left: x * k, top: (y - 12) * k, transform: [{ translateX: '-50%' as never }] }}>
      <Text numberOfLines={1} style={{ backgroundColor: bg, color: ink, fontWeight: '800', fontSize: size * Math.min(1.15, Math.max(0.85, k)),
        paddingHorizontal: 9, paddingVertical: 3, borderRadius: 12, overflow: 'hidden' }}>{text}</Text>
    </View>
  );
}
// true while the game waits behind a card (before Go, a question, the end): GeeKOc holds still then
const Resting = createContext(false);
export const Oc = ({ pose, x, y, size, k }: { pose: string; x: number; y: number; size: number; k: number }) => {
  const resting = useContext(Resting);
  return (
    <View pointerEvents="none" style={{ position: 'absolute', left: (x - size / 2) * k, top: (y - size / 2) * k }}>
      <GeekMover pose={pose} size={size * k} paused={resting} />
    </View>
  );
};

// ------------------------------------------------------------------------------------------------ the four games
const countOnce = (w: World, api: Api, c: any, right: boolean) => {
  if (w.counted.has(c.id)) return;
  w.counted.add(c.id);
  api.answer(c.id, right, c.level, c.terms);
};
const WHACK: Spec = {
  game: 'whack', title: 'Whack the bugs, spare the friends', bg: '#2b1d3a',
  howto: 'Bugs (an off-by-one, a memory leak) pop up: tap them. Friends (a unit test, a README) pop up too: leave them be. 30 seconds.',
  load: (wts) => roundItems('whack', 'critter', 16, wts),
  init: (items, w) => { w.critters = items; w.queue = [...items]; w.holes = Array.from({ length: 9 }, () => ({ up: null })); w.left = 30; w.spawn = 0; w.score = 0; w.counted = new Set<string>(); },
  step: (w, dt, api) => {
    w.left -= dt; w.spawn -= dt;
    if (w.spawn <= 0) {
      const free = w.holes.filter((h: any) => !h.up);
      if (free.length) { if (!w.queue.length) w.queue = shuffle(w.critters); pick(free as any[]).up = { c: w.queue.pop(), life: rnd(1.4, 2.1) - (30 - w.left) * 0.015 }; }
      w.spawn = rnd(0.45, 0.85);
    }
    // each critter counts once a round, its first outcome: a friend rightly spared, a bug that got away
    for (const h of w.holes) if (h.up) { h.up.life -= dt; if (h.up.life <= 0) { countOnce(w, api, h.up.c, !h.up.c.bug); h.up = null; } }
    if (w.left <= 0) api.end();
    w.hud = `${Math.max(0, Math.ceil(w.left))} s · ${w.score}`;
  },
  press: (w, x, y, api) => {
    const top = 190, gap = (w.H - top - 40) / 3;
    w.holes.forEach((h: any, i: number) => {
      const hx = W0 / 2 + ((i % 3) - 1) * (W0 / 3.2), hy = top + gap * Math.floor(i / 3) + gap * 0.6;
      if (h.up && Math.abs(x - hx) < 58 && y > hy - 80 && y < hy + 30) {
        const c = h.up.c; h.up = null;
        if (c.bug) { w.score += 10; countOnce(w, api, c, true); }
        else { w.score = Math.max(0, w.score - 15); countOnce(w, api, c, false); api.say(`You whacked a ${c.label.toLowerCase()}: ${c.why[0].toLowerCase()}${c.why.slice(1)}`); }
      }
    });
  },
  snap: (w) => ({ H: w.H, left: w.left, score: w.score, holes: w.holes.map((h: any) => (h.up ? { label: h.up.c.label, bug: h.up.c.bug } : null)) }),
  draw: (v, k) => {
    const top = 190, gap = (v.H - top - 40) / 3;
    return <>
      <Oc pose="point" x={54} y={56} size={96} k={k} />
      <Text style={[st.hudBig, { left: 104 * k, top: 40 * k }]}>{Math.max(0, Math.ceil(v.left))} s left · {v.score}</Text>
      {v.holes.map((h: any, i: number) => {
        const hx = W0 / 2 + ((i % 3) - 1) * (W0 / 3.2), hy = top + gap * Math.floor(i / 3) + gap * 0.6;
        return <View key={i} pointerEvents="none">
          <View style={{ position: 'absolute', left: (hx - 50) * k, top: (hy - 2) * k, width: 100 * k, height: 30 * k, borderRadius: 50 * k, backgroundColor: '#120a1c' }} />
          {h ? <>
            <Text style={{ position: 'absolute', left: (hx - 25) * k, top: (hy - 46) * k, width: 50 * k, textAlign: 'center', fontSize: 34 * k }}>{h.bug ? '🐛' : '🦋'}</Text>
            <Pill text={h.label} x={hx} y={hy - 60} bg={h.bug ? '#f87171' : '#34d399'} k={k} size={11} />
          </> : null}
        </View>;
      })}
    </>;
  },
};

const NET_COLORS = ['#7fd8ff', '#ffc457', '#34d399'];
const netX = (i: number, n: number) => W0 / 2 + (i - (n - 1) / 2) * (W0 / n);
const CATCH: Spec = {
  game: 'catch', title: 'Sort the catch', bg: '#071628', howto: 'Names fall one at a time. Tap the net each one belongs in.',
  load: (wts) => roundItems('catch', 'sort', 1, wts),
  init: (items, w) => { w.set = items[0]; w.things = shuffle(w.set.things as [string, number][]).slice(0, 10); w.cur = null; w.flash = null; w.n = 0; w.right = 0; },
  step: (w, dt, api) => {
    const nb = w.set.bins.length;
    if (!w.cur) {
      if (!w.things.length) { api.end(); return; }
      const [name, bin] = w.things.pop();
      w.cur = { name, bin, lane: Math.floor(nb / 2), x: W0 / 2, y: 70, vy: 46 + w.n * 5 };
    }
    const c = w.cur;
    c.x += (netX(c.lane, nb) - c.x) * Math.min(1, dt * 10);
    c.y += c.vy * dt;
    if (c.y > w.H - 130) {
      w.n += 1;
      const ok = c.lane === c.bin;
      w.right += ok ? 1 : 0;
      api.answer(`${w.set.id}:${c.name}`, ok, w.set.level, w.set.terms);
      w.flash = { lane: c.lane, ok, t: 0.8 };
      if (!ok) api.say(`${c.name} goes in “${w.set.bins[c.bin]}”.`);
      w.cur = null;
    }
    if (w.flash) { w.flash.t -= dt; if (w.flash.t <= 0) w.flash = null; }
    w.hud = `${w.right}/${w.n} right · ${w.things.length + (w.cur ? 1 : 0)} to go`;
  },
  press: (w, x) => {
    if (!w.cur) return;
    const nb = w.set.bins.length;
    let best = 0;
    for (let i = 1; i < nb; i++) if (Math.abs(x - netX(i, nb)) < Math.abs(x - netX(best, nb))) best = i;
    w.cur.lane = best; w.cur.vy = 520;
  },
  snap: (w) => ({ H: w.H, name: w.set?.name ?? '', bins: w.set?.bins ?? [], cur: w.cur && { ...w.cur }, flash: w.flash && { ...w.flash } }),
  draw: (v, k) => <>
    <Oc pose="point" x={50} y={52} size={90} k={k} />
    <Text style={[st.hudBig, { left: 100 * k, top: 30 * k, right: 10 }]}>{v.name}</Text>
    {v.bins.map((b: string, i: number) => {
      const nb = v.bins.length, x = netX(i, nb), wNet = W0 / nb - 18, top = v.H - 110;
      const lit = v.flash && v.flash.lane === i ? (v.flash.ok ? 'rgba(52,211,153,0.3)' : 'rgba(248,113,113,0.3)') : 'rgba(255,255,255,0.05)';
      return <View key={b} pointerEvents="none">
        <Text style={{ position: 'absolute', left: (x - wNet / 2) * k, top: (top - 26) * k, width: wNet * k, textAlign: 'center', color: NET_COLORS[i % 3], fontWeight: '800', fontSize: 14 }}>{b}</Text>
        <View style={{ position: 'absolute', left: (x - wNet / 2) * k, top: top * k, width: wNet * k, height: 90 * k, borderWidth: 2.5, borderColor: NET_COLORS[i % 3],
                       borderTopWidth: 0, borderBottomLeftRadius: 60 * k, borderBottomRightRadius: 60 * k, backgroundColor: lit }} />
      </View>;
    })}
    {v.cur ? <Pill text={v.cur.name} x={v.cur.x} y={v.cur.y} bg="#ff6fd8" k={k} size={14} /> : null}
  </>,
};

const BUGS = ['NaN', 'Segfault', '404', 'OOM', 'Merge conflict', 'Typo'];
const RUN: Spec = {
  game: 'run', title: 'GeeKOc run', bg: '#f4efe9',
  howto: 'Tap to jump. Jump the bugs. At a gate, jump for the top answer or stay low for the bottom one.',
  load: (wts) => roundItems('run', 'gate', 8, wts),
  init: (items, w) => { Object.assign(w, { gates: items, gi: 0, y: 0, vy: 0, obs: [], speed: 200, dist: 0, nextObs: 1.4, nextGate: 3.5, lives: 3, hurt: 0 }); },
  step: (w, dt, api) => {
    const px = 92;
    w.dist += w.speed * dt; w.speed += dt * 5;
    w.vy += 1650 * dt; w.y = Math.min(0, w.y + w.vy * dt); if (w.y >= 0) w.vy = 0;
    w.nextObs -= dt; w.nextGate -= dt; w.hurt -= dt;
    const far = w.obs.some((o: any) => o.x > W0 - 160);
    if (w.nextGate <= 0 && !far && w.gi < w.gates.length) {
      w.obs.push({ gate: w.gates[w.gi++], x: W0 + 30, w: 22, top: Math.random() < 0.5 });
      w.nextGate = rnd(5.5, 7); w.nextObs = 1.8;
    } else if (w.nextObs <= 0 && !far) {
      w.obs.push({ label: pick(BUGS), x: W0 + 20, w: 34, h: rnd(28, 40) });
      w.nextObs = rnd(1.3, 2.2);
    }
    for (const o of w.obs) o.x -= w.speed * dt;
    for (const o of w.obs) {
      if (o.done) continue;
      if (o.gate && o.x < px + 10 && px + 10 < o.x + o.w + 20) {
        o.done = true;
        const ok = (w.y < -60) === o.top;
        api.answer(o.gate.id, ok, o.gate.level, o.gate.terms);
        if (ok) w.bonus += 5; else { w.lives -= 1; w.hurt = 1; api.say(`${o.gate.q}? ${o.gate.right}.`); }
      } else if (o.label && o.x < px + 16 && o.x + o.w > px - 16 && -w.y < o.h - 6) {
        o.done = true; w.lives -= 1; w.hurt = 1; api.say(`Ouch: ${o.label}!`, 1.2);
      }
    }
    w.obs = w.obs.filter((o: any) => o.x + o.w > -40);
    if (w.lives <= 0 || (w.gi >= w.gates.length && !w.obs.some((o: any) => o.gate && !o.done))) api.end();
    w.hud = `${Math.round(w.dist / 10)} m · gate ${Math.min(w.gi, w.gates.length)}/${w.gates.length} · ${'♥'.repeat(Math.max(0, w.lives))}`;
  },
  press: (w) => { if (w.y >= -1) w.vy = -560; },
  snap: (w) => ({ H: w.H, y: w.y, hurt: w.hurt, dist: w.dist, obs: (w.obs ?? []).map((o: any) => ({ ...o })) }),
  draw: (v, k) => {
    const g = v.H - 90, nxt = v.obs.find((o: any) => o.gate && !o.done);
    return <>
      {nxt ? <Text style={[st.question, { color: '#241f1a', top: 18 * k }]}>{nxt.gate.q}?</Text> : null}
      <View style={{ position: 'absolute', left: 0, right: 0, top: (g + 22) * k, height: 2, backgroundColor: '#8a8070' }} />
      {v.obs.map((o: any, i: number) => o.gate ? (
        <View key={`g${i}`} pointerEvents="none">
          <View style={{ position: 'absolute', left: o.x * k, top: 80 * k, width: o.w * k, height: (g + 22 - 80) * k, backgroundColor: '#6d28d9' }} />
          <View style={{ position: 'absolute', left: (o.x - 2) * k, top: (g - 110) * k, width: (o.w + 4) * k, height: 4 * k, backgroundColor: '#f4efe9' }} />
          <Pill text={o.top ? o.gate.right : o.gate.wrong} x={o.x + o.w / 2} y={g - 150} bg="#ffc457" k={k} ink="#241f1a" size={14} />
          <Pill text={o.top ? o.gate.wrong : o.gate.right} x={o.x + o.w / 2} y={g - 30} bg="#ffc457" k={k} ink="#241f1a" size={14} />
        </View>
      ) : (
        <View key={`o${i}`} pointerEvents="none">
          <Text style={{ position: 'absolute', left: (o.x - 40) * k, top: (g + 2 - o.h - 18) * k, width: (o.w + 80) * k, textAlign: 'center', color: '#c0367f', fontWeight: '800', fontSize: 11 }}>{o.label}</Text>
          <View style={{ position: 'absolute', left: o.x * k, top: (g + 22 - o.h) * k, width: o.w * k, height: o.h * k, borderRadius: 6, backgroundColor: '#c0367f', alignItems: 'center', justifyContent: 'center' }}>
            <Text style={{ fontSize: 16 * k }}>🐛</Text>
          </View>
        </View>
      ))}
      {v.hurt <= 0 || Math.floor(v.dist / 12) % 2 ? <Oc pose={v.y < -2 ? 'jet' : 'wave'} x={92} y={g - 8 + v.y} size={76} k={k} /> : null}
    </>;
  },
};

const gaps = (H: number) => [[H * 0.16, H * 0.16 + 120], [H * 0.84 - 120, H * 0.84]] as const;
const FLAPPY: Spec = {
  game: 'flappy', title: 'Flappy GeeKOc', bg: '#0b3b5e',
  howto: 'Tap to puff ink and swim up. Fly through the gap of the right answer; the coral costs a life.',
  load: (wts) => roundItems('flappy', 'gate', 8, wts),
  init: (items, w) => { Object.assign(w, { gates: items, gi: 0, y: 200, vy: 0, pipes: [], next: 0.8, lives: 3, hurt: 0 }); },
  step: (w, dt, api) => {
    const [[t0, t1], [b0, b1]] = gaps(w.H), gx = 120;
    w.vy += 820 * dt; w.y += w.vy * dt; w.hurt -= dt; w.next -= dt;
    if (w.next <= 0 && w.gi < w.gates.length) { w.pipes.push({ g: w.gates[w.gi++], x: W0 + 40, top: Math.random() < 0.5 }); w.next = 3.4; }
    for (const pp of w.pipes) pp.x -= 128 * dt;
    for (const pp of w.pipes) {
      if (pp.done) continue;
      if (pp.x < gx + 14 && pp.x + 54 > gx - 14) {
        const inTop = w.y > t0 && w.y < t1, inLow = w.y > b0 && w.y < b1;
        if (!inTop && !inLow && w.hurt <= 0) { w.lives -= 1; w.hurt = 1; api.say('Bonk! Into the coral.', 1.2); w.y = pp.top ? (t0 + t1) / 2 : (b0 + b1) / 2; w.vy = -100; }
        else if (inTop || inLow) pp.gap = inTop ? 'top' : 'low';
      } else if (pp.x + 54 <= gx - 14 && pp.gap) {
        pp.done = true;
        const ok = (pp.gap === 'top') === pp.top;
        api.answer(pp.g.id, ok, pp.g.level, pp.g.terms);
        if (ok) w.bonus += 5; else { w.lives -= 1; w.hurt = 1; api.say(`${pp.g.q}? ${pp.g.right}.`); }
      } else if (pp.x + 54 <= gx - 14) pp.done = true;
    }
    w.pipes = w.pipes.filter((pp: any) => pp.x > -80);
    if (w.y > w.H - 12 || w.y < 8) { if (w.hurt <= 0) { w.lives -= 1; w.hurt = 1; api.say('Careful: stay in the water!', 1.2); } w.y = w.H / 2; w.vy = -120; }
    if (w.lives <= 0 || (w.gi >= w.gates.length && !w.pipes.length)) api.end();
    w.hud = `gate ${Math.min(w.gi, w.gates.length)}/${w.gates.length} · ${'♥'.repeat(Math.max(0, w.lives))}`;
  },
  press: (w) => { w.vy = -300; },
  snap: (w) => ({ H: w.H, y: w.y, vy: w.vy, hurt: w.hurt, pipes: (w.pipes ?? []).map((pp: any) => ({ ...pp })) }),
  draw: (v, k) => {
    const [[t0, t1], [b0, b1]] = gaps(v.H), nxt = v.pipes.find((pp: any) => !pp.done);
    return <>
      {v.pipes.map((pp: any, i: number) => (
        <View key={i} pointerEvents="none">
          {[[0, t0], [t1, b0 - t1], [b1, v.H - b1]].map(([y, h], j) => (
            <View key={j} style={{ position: 'absolute', left: pp.x * k, top: y * k, width: 54 * k, height: h * k, backgroundColor: '#ff7a8a' }} />
          ))}
          <Pill text={pp.top ? pp.g.right : pp.g.wrong} x={pp.x + 27} y={(t0 + t1) / 2} bg="#ffc457" k={k} ink="#241f1a" />
          <Pill text={pp.top ? pp.g.wrong : pp.g.right} x={pp.x + 27} y={(b0 + b1) / 2} bg="#ffc457" k={k} ink="#241f1a" />
        </View>
      ))}
      {nxt ? <Text style={[st.question, { color: '#fff', top: 10 * k }]}>{nxt.g.q}?</Text> : null}
      <Oc pose={v.vy < 0 ? 'jet' : 'cheer'} x={120} y={v.y} size={66} k={k} />
    </>;
  },
};

const SPECS: Record<string, Spec> = { whack: WHACK, catch: CATCH, run: RUN, flappy: FLAPPY };
export const ARCADE_GAMES = Object.keys(SPECS);

// ------------------------------------------------------------------------------------------------ the engine
export function ArcadeGame(props: {
  id: string; onAgain: () => void; onHub: () => void; Result: (p: { r: Result; onAgain: () => void; onHub: () => void }) => ReactNode;
}) {
  return <ArcadeEngine spec={SPECS[props.id]} {...props} />;
}

export function ArcadeEngine({ spec, onAgain, onHub, Result }: {
  spec: Spec; onAgain: () => void; onHub: () => void; Result: (p: { r: Result; onAgain: () => void; onHub: () => void }) => ReactNode;
}) {
  const { profile } = useApp();
  const { height: screenH } = useWindowDimensions();
  const [fieldW, setFieldW] = useState(0);
  const fieldH = Math.max(380, Math.round(screenH * 0.66));
  const world = useRef<World>({ W: W0, H: 560, msg: '', msgT: 0, bonus: 0, hud: '' });
  const meta = useRef({ answers: [] as G.Answer[], t0: 0, ended: false, ready: false, paused: true });
  const [view, setView] = useState<Record<string, any> | null>(null);
  const [hud, setHud] = useState('');
  const [msg, setMsg] = useState('');
  const [started, setStarted] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  const [outro, setOutro] = useState<{ title: string; text: string } | null>(null);
  const [ask, setAsk] = useState<(Ask & { done: (right: boolean) => void; picked: number | null }) | null>(null);
  // the short wait before the result: cleared if you leave, so a round you left is never saved
  const finishTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(finishTimer.current), []);
  const finishNow = useCallback(() => {
    const m = meta.current;
    setOutro(null);
    finishTimer.current = setTimeout(async () => { setResult(await finish(spec.game, m.answers, (Date.now() - m.t0) / 1000, world.current.bonus)); }, 450);
  }, [spec]);
  const end = useCallback((o?: { title: string; text: string }) => {
    const m = meta.current;
    if (m.ended) return;
    m.ended = true; m.paused = true;
    if (o) setOutro(o); else finishNow();
  }, [finishNow]);
  const wake = useRef<() => void>(() => undefined);      // starts the frame loop again after it rested
  const api = useRef<Api>({
    answer: (iid, right, level, terms) => { meta.current.answers.push({ id: iid, right, level, terms: [...terms] }); },
    say: (t, s = 2.6) => { world.current.msg = t; world.current.msgT = s; wake.current(); },
    end: () => undefined,
    ask: (q, done) => { meta.current.paused = true; setAsk({ ...q, done, picked: null }); },
  });
  useEffect(() => { api.current.end = end; }, [end]);

  useEffect(() => {
    spec.load(profile?.weights ?? {}).then((items) => {
      spec.init(items, world.current);
      meta.current.ready = true;
      setView(spec.snap(world.current));
    }).catch(() => undefined);
  }, [spec, profile]);

  useEffect(() => {
    let raf = 0, last = 0, wasStill = false, running = false;
    const loop = (now: number) => {
      const dt = last ? Math.min(0.05, (now - last) / 1000) : 0.016;
      last = now;
      const w = world.current, m = meta.current;
      if (m.ready && !m.paused) spec.step(w, dt, api.current);
      w.msgT -= dt;
      // before Go, during a question and after the end nothing moves: draw once, then the loop rests (no frames
      // at all) until play goes on -- wake() starts it again
      const still = m.ready && m.paused && w.msgT <= 0;
      if (still && wasStill) { running = false; last = 0; return; }
      if (m.ready) { setView(spec.snap(w)); setHud(w.hud); setMsg(w.msgT > 0 ? w.msg : ''); }
      wasStill = still;
      raf = requestAnimationFrame(loop);
    };
    wake.current = () => { if (!running) { running = true; wasStill = false; raf = requestAnimationFrame(loop); } };
    wake.current();
    return () => { cancelAnimationFrame(raf); wake.current = () => undefined; };
  }, [spec]);

  const go = () => { const m = meta.current; m.paused = false; m.t0 = Date.now(); setStarted(true); wake.current(); };
  const tap = (x: number, y: number) => {
    if (meta.current.paused || !fieldW) return;
    const k = fieldW / W0;
    spec.press(world.current, x / k, y / k, api.current);
  };

  if (result) return <Result r={result} onAgain={onAgain} onHub={onHub} />;
  const k = fieldW ? fieldW / W0 : 1;
  return (
    <View>
      <Text style={st.hud}>{hud || ' '}</Text>
      <Pressable onPressIn={(e) => tap(e.nativeEvent.locationX, e.nativeEvent.locationY)} accessibilityRole="button" accessibilityLabel={spec.title}
                 style={[st.field, { height: fieldH, backgroundColor: spec.bg }]}
                 onLayout={(e) => { const { width, height } = e.nativeEvent.layout; setFieldW(width); world.current.W = W0; world.current.H = Math.max(360, (W0 * height) / width); }}>
        <Resting.Provider value={!started || !!ask || !!outro}>{view && fieldW ? spec.draw(view, k) : null}</Resting.Provider>
        {msg ? <Text style={st.msg}>{msg}</Text> : null}
        {outro ? (
          <View style={st.over}>
            <View style={st.card}>
              <Text style={st.cardTitle}>{outro.title}</Text>
              <Text style={st.small}>{outro.text}</Text>
              <Pressable onPress={finishNow} style={st.primary} accessibilityRole="button"><Text style={st.primaryText}>See how you did</Text></Pressable>
            </View>
          </View>
        ) : null}
        {ask ? (
          <View style={st.over}>
            <View style={st.card}>
              {ask.kicker ? <Text style={[st.small, { fontWeight: '800' }]}>{ask.kicker}</Text> : null}
              <Text style={st.cardTitle}>{ask.title}</Text>
              {ask.options.map((o, i) => {
                const mark = ask.picked === null ? '' : i === ask.right ? 'right' : i === ask.picked ? 'wrong' : '';
                return (
                  <Pressable key={o} accessibilityRole="button" onPress={() => { if (ask.picked === null) setAsk({ ...ask, picked: i }); }}
                             style={[st.opt, mark === 'right' && { borderColor: C.green }, mark === 'wrong' && { borderColor: C.red }]}>
                    <Text style={st.optText}>{o}</Text>
                  </Pressable>
                );
              })}
              {ask.picked !== null ? <>
                <Text style={st.small}>{ask.picked === ask.right ? '✅ ' : '❌ '}{ask.why}</Text>
                <Pressable accessibilityRole="button" style={st.primary} onPress={() => {
                  const ok = ask.picked === ask.right;
                  setAsk(null);
                  meta.current.paused = false;
                  wake.current();
                  ask.done(ok);
                }}><Text style={st.primaryText}>{ask.picked === ask.right ? ask.go : 'OK'}</Text></Pressable>
              </> : null}
            </View>
          </View>
        ) : null}
        {!started ? (
          <View style={st.over}>
            <View style={st.card}>
              <Text style={st.cardTitle}>{spec.title}</Text>
              <Text style={st.small}>{spec.howto}</Text>
              <Pressable onPress={go} style={st.primary} accessibilityRole="button"><Text style={st.primaryText}>Go</Text></Pressable>
            </View>
          </View>
        ) : null}
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  hud: { color: C.muted, fontSize: 12.5, marginBottom: 6 },
  field: { borderRadius: 16, overflow: 'hidden' },
  hudBig: { position: 'absolute', color: '#f0f0f5', fontWeight: '800', fontSize: 15 },
  question: { position: 'absolute', left: 12, right: 12, textAlign: 'center', fontWeight: '800', fontSize: 15 },
  msg: { position: 'absolute', left: 12, right: 12, bottom: 18, color: '#f0f0f5', backgroundColor: 'rgba(28,28,44,0.92)', borderRadius: 10,
         paddingVertical: 7, paddingHorizontal: 10, textAlign: 'center', fontSize: 12.5, fontWeight: '700' },
  over: { ...StyleSheet.absoluteFill, backgroundColor: 'rgba(7,7,18,0.6)', justifyContent: 'center', padding: 14 },
  card: { backgroundColor: C.sheet, borderRadius: 16, padding: 14, gap: 8, borderWidth: 1, borderColor: tint(0.12) },
  cardTitle: { color: C.text, fontSize: 15, fontWeight: '800' },
  small: { color: C.muted, fontSize: 12.5, lineHeight: 18 },
  primary: { alignSelf: 'flex-start', backgroundColor: C.violet, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 16 },
  primaryText: { color: '#fff', fontWeight: '800', fontSize: 14 },
  opt: { borderWidth: 2, borderColor: tint(0.12), backgroundColor: C.cardHi, borderRadius: 12, paddingVertical: 9, paddingHorizontal: 12 },
  optText: { color: C.text, fontSize: 13.5, lineHeight: 19 },
});
