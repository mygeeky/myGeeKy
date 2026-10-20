// News → 🏁 AI race: who leads, what's new, the race replayed, how far open models trail, what each model is best at,
// fingerprints, and a picker for your own work -- the desktop's gui/airace_ui.py. lib/ai-race.ts works out every
// number (the same as airace.py). Everything fits the phone's width; details come on a tap.
import { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Path, Polygon, Polyline, Text as SvgText } from 'react-native-svg';
import { GROUPS, loadRace, pick, race, type Race, stats } from '../lib/ai-race';
import { C } from '../lib/theme';
import { GeekLoader, useHold } from './geek-loader';
import { open } from './ui';

// the two kinds of weights, and a colour per skill in GROUPS order (the dataviz palette's validated order; the
// ninth a neutral grey) -- the same as the desktop
const CLOSED = C.dark ? '#3987e5' : '#2a78d6';
const OPEN = C.dark ? '#d95926' : '#eb6834';
const ACCENT = C.dark ? '#a08cff' : '#6d4fff';
const SKILL = C.dark
  ? ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767', '#8f8ba8']
  : ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948', '#7c7896'];
const SHORT_ORG: Record<string, string> = { 'Google DeepMind': 'Google', 'Z.ai (Zhipu AI)': 'Z.ai', 'Thinking Machines': 'Thinking M.' };
const SHORT: Record<string, string> = { Reasoning: 'Rsn', Coding: 'Code', Math: 'Math', Science: 'Sci', Agents: 'Agt', Knowledge: 'Know',
  Writing: 'Wri', Vision: 'Vis', Security: 'Sec' };
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const monthLabel = (iso: string) => `${MONTHS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}`;
const kind = (isOpen: boolean) => (isOpen ? OPEN : CLOSED);

function Head({ title, note }: { title: string; note: string }) {
  return <View style={st.head}><Text style={st.h2}>{title}</Text><Text style={st.note}>{note}</Text></View>;
}

function Bar({ value, color, width }: { value: number; color: string; width: number }) {
  return <View style={[st.track, { width }]}><View style={[st.fill, { width: `${Math.max(4, value * 100)}%`, backgroundColor: color }]} /></View>;
}

function RaceBlock({ data, months }: { data: Race; months: string[] }) {
  const [i, setI] = useState(months.length - 1);
  const [w, setW] = useState(300);
  const [playing, setPlaying] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);
  const play = () => {
    if (timer.current) { clearInterval(timer.current); timer.current = null; setPlaying(false); return; }
    let k = i >= months.length - 1 ? 0 : i;
    setPlaying(true);
    timer.current = setInterval(() => {
      setI(k);
      if (++k >= months.length) { clearInterval(timer.current!); timer.current = null; setPlaying(false); }
    }, 420);
  };
  const rows = race(data, months[i]);
  const lo = Math.min(...rows.map((r) => r.eci)) - 18, hi = rows[0]?.eci ?? 1;
  const scrub = (x: number) => { if (timer.current) { clearInterval(timer.current); timer.current = null; setPlaying(false); }
    setI(Math.max(0, Math.min(months.length - 1, Math.round(x / Math.max(1, w - 110) * (months.length - 1))))); };
  return (
    <View>
      <View style={st.raceTop}>
        <Pressable onPress={play} style={st.play} accessibilityLabel={playing ? 'Pause' : 'Replay the race'}>
          <Text style={{ color: C.text, fontWeight: '800' }}>{playing ? '❚❚' : '▶'}</Text>
        </Pressable>
        <Text style={st.month}>{monthLabel(months[i])}</Text>
        <Pressable style={st.scrub} onPress={(e) => scrub(e.nativeEvent.locationX)} accessibilityLabel="Choose a month">
          <View style={st.scrubLine} /><View style={[st.scrubDot, { left: `${(i / Math.max(1, months.length - 1)) * 100}%` }]} />
        </Pressable>
      </View>
      <View onLayout={(e) => setW(e.nativeEvent.layout.width)}>
        {rows.map((r) => {
          const bw = Math.max(56, (r.eci - lo) / Math.max(1, hi - lo) * (w - 34));
          return (
            <Pressable key={r.org} onPress={() => setPicked(picked === r.org ? null : r.org)} style={st.lane}>
              <View style={[st.laneBar, { width: bw, backgroundColor: kind(r.open) }]}>
                <Text style={st.laneText} numberOfLines={1}>{SHORT_ORG[r.org] ?? r.org}</Text>
              </View>
              <Text style={st.laneVal}>{r.eci.toFixed(0)}</Text>
            </Pressable>
          );
        })}
      </View>
      {picked ? <Text style={st.small}>{picked}: {rows.find((r) => r.org === picked)?.model ?? 'not in the top six this month'}</Text> : null}
      <View style={st.legend}><Text style={st.small}><Text style={{ color: CLOSED }}>●</Text> Closed   <Text style={{ color: OPEN }}>●</Text> Open weights</Text></View>
    </View>
  );
}

function GapChart({ s }: { s: Extract<ReturnType<typeof stats>, { empty: false }> }) {
  const [w, setW] = useState(220);
  const [k, setK] = useState<number | null>(null);
  const H = 92;
  const idx = s.months.map((_, i) => i).filter((i) => s.closed[i] != null && s.open[i] != null);
  if (idx.length < 2) return null;
  const vals = idx.flatMap((i) => [s.closed[i]!, s.open[i]!]);
  const lo = Math.min(...vals) - 3, hi = Math.max(...vals) + 3;
  const X = (i: number) => 2 + i / (s.months.length - 1) * (w - 4), Y = (v: number) => 4 + (1 - (v - lo) / (hi - lo)) * (H - 24);
  const closed = idx.map((i) => `${X(i)},${Y(s.closed[i]!)}`), opened = idx.map((i) => `${X(i)},${Y(s.open[i]!)}`);
  const years = s.months.map((m, i) => [m, i] as const).filter(([m, i]) => m.slice(5, 7) === '01' && i > 0);
  return (
    <View style={{ flex: 1 }} onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      <Pressable onPress={(e) => setK(Math.max(0, Math.min(s.months.length - 1, Math.round((e.nativeEvent.locationX - 2) / (w - 4) * (s.months.length - 1)))))}>
        <Svg width={w} height={H}>
          <Polygon points={[...closed, ...opened.reverse()].join(' ')} fill={ACCENT} fillOpacity={0.14} />
          <Polyline points={idx.map((i) => `${X(i)},${Y(s.closed[i]!)}`).join(' ')} fill="none" stroke={CLOSED} strokeWidth={2} />
          <Polyline points={idx.map((i) => `${X(i)},${Y(s.open[i]!)}`).join(' ')} fill="none" stroke={OPEN} strokeWidth={2} />
          {years.map(([m, i]) => <SvgText key={m} x={X(i)} y={H - 4} fontSize={9.5} fill={C.muted} textAnchor="middle">{m.slice(0, 4)}</SvgText>)}
          {k !== null ? <Line x1={X(k)} x2={X(k)} y1={2} y2={H - 16} stroke={C.muted} strokeDasharray="3 3" /> : null}
        </Svg>
      </Pressable>
      {k !== null && s.closed[k] != null && s.open[k] != null
        ? <Text style={st.small}>{monthLabel(s.months[k])}: closed {s.closed[k]!.toFixed(0)}, open {s.open[k]!.toFixed(0)}, {s.behind[k]} months behind</Text> : null}
    </View>
  );
}

function SkillRow({ row }: { row: Extract<ReturnType<typeof stats>, { empty: false }>['best_at'][number] }) {
  const [opened, setOpened] = useState(false);
  const top = row.top[0];
  return (
    <View>
      <Pressable onPress={() => setOpened(!opened)} style={({ pressed }) => [st.skill, pressed && { backgroundColor: C.card }]}
                 accessibilityRole="button" accessibilityState={{ expanded: opened }}>
        <Text style={st.skillName}>{row.group}</Text>
        <View style={{ flex: 1 }}>
          <View style={st.dots}>
            {row.models.slice(0, 22).map((m) => <View key={m.model} style={[st.dot, { backgroundColor: kind(m.open) }]} />)}
            <Text style={st.count}>{row.models.length}</Text>
          </View>
          <Text style={st.small} numberOfLines={1}>{top ? `Top: ${top.model} ${top.score.toFixed(2)}` : 'Not enough results yet'}</Text>
        </View>
        <Text style={[st.small, { width: 14, textAlign: 'center' }]}>{opened ? '▾' : '▸'}</Text>
      </Pressable>
      {opened ? (
        <View style={st.more}>
          {row.top.map((t) => (
            <View key={t.model} style={st.mrow}>
              <Text style={[st.small, { flex: 1, color: C.text }]} numberOfLines={1}>{t.model}{t.open ? '  · open' : ''}</Text>
              <Bar value={t.score} color={kind(t.open)} width={54} />
              <Text style={[st.small, { width: 30, textAlign: 'right' }]}>{t.score.toFixed(2)}</Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function Flower({ m, size }: { m: { model: string; best: string; groups: Record<string, { score: number }> }; size: number }) {
  const n = GROUPS.length;
  const pt = (a: number, r: number) => `${(r * Math.cos(a)).toFixed(1)},${(r * Math.sin(a)).toFixed(1)}`;
  return (
    <Svg width={size} height={size} viewBox="-68 -66 136 132">
      <Circle r={50} fill="none" stroke={C.line} />
      {GROUPS.map((g, i) => {
        const a = -Math.PI / 2 + i / n * Math.PI * 2, w = Math.PI / n * 0.8, sc = m.groups[g];
        const label = <SvgText key={`l${g}`} x={57 * Math.cos(a)} y={57 * Math.sin(a) + 3} fontSize={9} fill={C.muted} textAnchor="middle">{SHORT[g]}</SvgText>;
        if (!sc) return [label, <Circle key={g} cx={7 * Math.cos(a)} cy={7 * Math.sin(a)} r={1.8} fill={C.muted} />];
        const L = 5 + sc.score * 40, best = m.best === g;
        return [label, <Path key={g} d={`M0,0 L${pt(a - w, L * 0.8)} Q${pt(a, L * 1.12)} ${pt(a + w, L * 0.8)} Z`} fill={SKILL[i]}
                             fillOpacity={best ? 1 : 0.6} stroke={best ? C.text : 'none'} strokeWidth={best ? 1.6 : 0} />];
      })}
    </Svg>
  );
}

export function AiRaceView() {
  const [data, setData] = useState<Race | null>(null);
  const [chosen, setChosen] = useState<string[]>(['Coding', 'Math']);
  const [printW, setPrintW] = useState(300);
  useEffect(() => { let live = true; loadRace().then((d) => { if (live) setData(d); }).catch(() => undefined); return () => { live = false; }; }, []);
  const s = useMemo(() => (data ? stats(data) : null), [data]);
  const holding = useHold(!data);
  if (holding || !data || !s) return <GeekLoader text="Loading the AI race…" />;
  if (s.empty) return <Text style={st.small}>The AI race isn&apos;t here yet. It arrives with the next update.</Text>;
  const lead = s.leader, best = s.best_open;
  const picks = pick(data, chosen);
  const toggle = (g: string) => setChosen((c) => (c.includes(g) ? (c.length > 1 ? c.filter((x) => x !== g) : c) : [...c, g]));
  return (
    <View style={st.wrap}>
      <Text style={st.h1}>{lead.org} leads. <Text style={{ color: ACCENT }}>Open is {s.behind_now} months behind.</Text></Text>
      {best ? <Text style={st.lede}>{lead.model} tops {s.count} models. Best open: {best.model}, {(lead.eci - best.eci).toFixed(1)} points back.</Text> : null}
      <View style={st.tiles}>
        {[[lead.eci.toFixed(0), 'top score'], [best ? best.eci.toFixed(0) : '–', 'best open'], [`+${s.rise.toFixed(0)}`, 'in 12 months'], [String(s.count), 'models']]
          .map(([v, k]) => <View key={k} style={st.tile}><Text style={st.tileV}>{v}</Text><Text style={st.tileK} numberOfLines={1}>{k}</Text></View>)}
      </View>

      <Head title="New and recent" note="the latest releases" />
      {s.recent.map((r) => (
        <View key={r.model} style={st.newRow}>
          <View style={st.when}><Text style={st.whenDay}>{Number(r.date.slice(8, 10))}</Text><Text style={st.whenMon}>{MONTHS[Number(r.date.slice(5, 7)) - 1]}</Text></View>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={st.newName} numberOfLines={1}>{r.model}{r.fresh ? <Text style={st.fresh}>  NEW </Text> : null}</Text>
            <Text style={st.small} numberOfLines={1}>{r.org} · {r.open ? 'open weights' : 'closed'}{r.best
              ? <Text style={{ color: SKILL[GROUPS.indexOf(r.best)], fontWeight: '700' }}> · ● {r.best}</Text> : null}</Text>
          </View>
          <View style={{ alignItems: 'flex-end' }}><Text style={st.rank}>#{r.rank}</Text><Text style={st.small}>of {s.count}</Text></View>
        </View>
      ))}

      <Head title="The race" note="each lab's best model" />
      <RaceBlock data={data} months={s.months} />

      <Head title="Open trails closed" note="tap the chart" />
      <View style={st.gapRow}>
        <View style={{ width: 84 }}><Text style={[st.big, { color: OPEN }]}>{s.behind_now} mo</Text><Text style={st.small}>behind the best closed model</Text></View>
        <GapChart s={s} />
      </View>

      <Head title="Best at" note="each dot is a recent model" />
      {s.best_at.map((row) => <SkillRow key={row.group} row={row} />)}

      <Head title="Fingerprints" note="one petal per skill" />
      <Text style={st.small}>{GROUPS.map((g, i) => <Text key={g}><Text style={{ color: SKILL[i] }}>■</Text> {g}{'   '}</Text>)}</Text>
      <View style={st.prints} onLayout={(e) => setPrintW(e.nativeEvent.layout.width)}>
        {s.prints.map((m) => (
          <View key={m.model} style={{ width: '33.3%', alignItems: 'center' }}>
            <Flower m={m} size={Math.min(110, printW / 3 - 4)} />
            <Text style={st.printName} numberOfLines={1}>{m.model}</Text>
            {m.best ? <Text style={st.small} numberOfLines={1}><Text style={{ color: SKILL[GROUPS.indexOf(m.best)] }}>●</Text> {m.best} · {m.eci.toFixed(0)}</Text> : null}
          </View>
        ))}
      </View>

      <Head title="For my work" note="pick skills" />
      <View style={st.chips}>
        {GROUPS.map((g) => (
          <Pressable key={g} onPress={() => toggle(g)} style={[st.chip, chosen.includes(g) && st.chipOn]} accessibilityRole="checkbox"
                     accessibilityState={{ checked: chosen.includes(g) }}>
            <Text style={[st.chipText, chosen.includes(g) && { color: '#fff', fontWeight: '800' }]}>{g}</Text>
          </Pressable>
        ))}
      </View>
      {picks.length ? picks.map((r, i) => (
        <View key={r.model} style={st.mrow}>
          <Text style={[st.small, { width: 14 }]}>{i + 1}</Text>
          <Text style={[st.newName, { flex: 1, fontSize: 13 }]} numberOfLines={1}>{r.model}{r.open ? '  · open' : ''}</Text>
          <Bar value={r.score} color={kind(r.open)} width={70} />
          <Text style={[st.small, { width: 32, textAlign: 'right', color: C.text }]}>{r.score.toFixed(2)}</Text>
        </View>
      )) : <Text style={st.small}>No recent model has results in all of these. Choose fewer.</Text>}

      <Pressable onPress={() => open('https://epoch.ai/benchmarks')} hitSlop={6}>
        <Text style={[st.small, { marginTop: 12 }]}>Data: <Text style={{ color: C.violet }}>Epoch AI</Text>, CC BY 4.0. Skill groups and scores are myGeeKy&apos;s own.</Text>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { paddingBottom: 30 },
  h1: { color: C.text, fontSize: 21, fontWeight: '900', lineHeight: 25, marginTop: 4 },
  lede: { color: C.muted, fontSize: 12.5, marginTop: 4 },
  tiles: { flexDirection: 'row', gap: 6, marginTop: 10 },
  tile: { flex: 1, backgroundColor: C.card, borderRadius: 10, paddingVertical: 7, alignItems: 'center' },
  tileV: { color: C.text, fontSize: 15, fontWeight: '800' },
  tileK: { color: C.muted, fontSize: 10.5 },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 18, marginBottom: 6,
    borderTopWidth: 1, borderTopColor: C.line, paddingTop: 12 },
  h2: { color: C.text, fontSize: 15, fontWeight: '800' },
  note: { color: C.muted, fontSize: 11 },
  small: { color: C.muted, fontSize: 11.5 },
  newRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: C.card, borderRadius: 12, paddingHorizontal: 8, paddingVertical: 6, marginBottom: 6 },
  when: { width: 32, alignItems: 'center' },
  whenDay: { color: ACCENT, fontSize: 15, fontWeight: '800' },
  whenMon: { color: C.muted, fontSize: 9.5, textTransform: 'uppercase' },
  newName: { color: C.text, fontSize: 13, fontWeight: '700' },
  fresh: { color: ACCENT, fontSize: 10, fontWeight: '900' },
  rank: { color: C.text, fontSize: 14, fontWeight: '800' },
  raceTop: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  play: { width: 32, height: 26, borderRadius: 13, borderWidth: 1, borderColor: C.line, alignItems: 'center', justifyContent: 'center' },
  month: { color: ACCENT, fontWeight: '800', fontSize: 13, width: 70 },
  scrub: { flex: 1, height: 26, justifyContent: 'center' },
  scrubLine: { height: 3, borderRadius: 2, backgroundColor: C.line },
  scrubDot: { position: 'absolute', width: 14, height: 14, borderRadius: 7, marginLeft: -7, backgroundColor: ACCENT },
  lane: { flexDirection: 'row', alignItems: 'center', height: 24 },
  laneBar: { height: 18, borderTopRightRadius: 5, borderBottomRightRadius: 5, justifyContent: 'center', paddingLeft: 7 },
  laneText: { color: '#fff', fontSize: 11.5, fontWeight: '700' },
  laneVal: { color: C.muted, fontSize: 11.5, marginLeft: 5 },
  legend: { marginTop: 4 },
  gapRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  big: { fontSize: 28, fontWeight: '900' },
  skill: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 5, paddingHorizontal: 4, borderRadius: 10 },
  skillName: { color: C.text, fontSize: 12.5, fontWeight: '800', width: 72 },
  dots: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 2 },
  dot: { width: 7, height: 7, borderRadius: 4 },
  count: { color: C.muted, fontSize: 11, marginLeft: 4 },
  more: { paddingLeft: 82, paddingBottom: 8, gap: 3 },
  mrow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 2 },
  track: { height: 6, borderRadius: 3, backgroundColor: C.line, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3 },
  prints: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 6 },
  printName: { color: C.text, fontSize: 11, fontWeight: '700', maxWidth: '96%' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 },
  chip: { borderWidth: 1, borderColor: C.line, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  chipOn: { backgroundColor: ACCENT, borderColor: ACCENT },
  chipText: { color: C.text, fontSize: 12 },
});
