// Circle → Researchers → 🌟 Leading lights: a few people who lead your field (a new set every three days, picked by your
// Model), each with why (🏅 🏆 📈 🛠), their latest papers, Follow and their links; a tap unfolds their report under them -- the
// desktop's gui/lights_ui.py. lib/lights.ts does the reading. Everything is plain text (it comes from the internet).
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Polyline, Rect, Text as SvgText } from 'react-native-svg';
import { useApp } from '../lib/app-state';
import * as L from '../lib/lights';
import { C } from '../lib/theme';
import { Empty, open } from './ui';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const day = (iso: string) => (iso.length >= 10 ? `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]}` : iso);
const today = () => new Date().toISOString().slice(0, 10);
const badge = (p: L.Light) => `${L.BADGES[p.badge][0]} ${L.BADGES[p.badge][1]}`;
const REPORT_MAIL = 'mailto:support@mygeeky.org?subject=Leading%20lights%3A%20a%20mistake'
  + '&body=Who%2C%20and%20what%20is%20wrong%20(wrong%20person%2C%20wrong%20prize%2C%20has%20passed%20away%E2%80%A6)%3A%0A';

/** Papers (bars) and citations (the line), the last ten years. */
function YearBars({ years, width }: { years: [number, number, number][]; width: number }) {
  const H = 110, h = H - 16, n = Math.max(1, years.length), step = width / n;
  const mostW = Math.max(1, ...years.map((y) => y[1])), mostC = Math.max(1, ...years.map((y) => y[2]));
  const pts = years.map((y, i) => [i * step + step / 2, h - ((h - 6) * y[2]) / mostC]);
  return (
    <Svg width={width} height={H}>
      {years.map(([y, w], i) => {
        const bh = ((h - 6) * w) / mostW;
        return <Rect key={y} x={i * step + step * 0.2} y={h - bh} width={step * 0.6} height={bh} fill={C.violet} opacity={0.75} />;
      })}
      <Polyline points={pts.map(([x, y]) => `${x},${y}`).join(' ')} fill="none" stroke={C.text} strokeWidth={1} />
      {pts.map(([x, y], i) => <Circle key={i} cx={x} cy={y} r={2} fill={C.text} />)}
      {years.map(([y], i) => (i % 3 === n % 3 || i === n - 1
        ? <SvgText key={`t${y}`} x={i * step + step / 2} y={H - 2} fontSize={9} fill={C.muted} textAnchor="middle">{y}</SvgText> : null))}
    </Svg>
  );
}

/** What a tap on someone shows, unfolded right under them in the list: their numbers, the last ten years, their
 *  topics (yours marked), their most cited papers and where to read more. Read once, then kept while the list is open. */
function ReportBox({ person, rep, note }: { person: L.Light; rep: L.Report | undefined; note: string }) {
  const [width, setWidth] = useState(0);
  return (
    <View style={st.report} onLayout={(e) => setWidth(e.nativeEvent.layout.width - 20)}>
      {!rep ? <Text style={st.muted}>{note || `Looking up ${person.name}…`}</Text> : <>
        {rep.institution ? <Text style={st.muted}>{rep.institution}</Text> : null}
        <View style={st.nums}>
          {([[rep.works, 'papers'], [rep.cited, 'citations'], [rep.h, 'h-index'], [rep.i10, 'i10-index']] as [number, string][]).map(([v, w]) => (
            <View key={w}><Text style={st.num}>{v.toLocaleString('en')}</Text><Text style={st.muted}>{w}</Text></View>
          ))}
        </View>
        <Text style={st.muted}>Papers (bars) and citations (line), the last ten years</Text>
        {width > 0 ? <YearBars years={rep.years} width={width} /> : null}
        {rep.topics.length ? <Text style={st.text}>Topics: {rep.topics.map(([t, mine]) => (mine ? '★ ' : '') + t).join(', ')}
          {rep.topics.some(([, m]) => m) ? '   (★ also yours)' : ''}</Text> : null}
        {rep.top.length ? <Text style={st.head}>MOST CITED</Text> : null}
        {rep.top.map((w) => (
          <Pressable key={w.url} onPress={() => open(w.url, 'paper')}>
            <Text style={st.text}>{w.title}  ·  {w.year || ''} · {w.cited.toLocaleString('en')} citations</Text>
          </Pressable>
        ))}
        <View style={st.row}>
          {L.links(person).map(([word, url]) => (
            <Pressable key={word} onPress={() => open(url, 'person')} style={st.btn}><Text style={st.btnText}>{word} ↗</Text></Pressable>
          ))}
        </View>
        {person.source ? <Pressable onPress={() => open(person.source)}><Text style={st.muted}>Why they&apos;re here: source ↗</Text></Pressable> : null}
      </>}
    </View>
  );
}

export function LightsView({ following, onFollow }: { following: Set<string>; onFollow: (p: { id: string; name: string; institution: string; topics: string[] }) => void }) {
  const { profile } = useApp();
  const weights = profile?.weights;
  const shown = useMemo(() => L.pick(L.load().people, weights ?? {}, today()), [weights]);
  const [recent, setRecent] = useState<Record<string, L.Paper[]>>({});
  const [note, setNote] = useState('');
  const [openId, setOpenId] = useState('');                      // whose report is unfolded
  const [reports, setReports] = useState<Record<string, L.Report>>({});
  const [wait, setWait] = useState('');
  const toggle = (p: L.Light) => {
    if (openId === p.id) { setOpenId(''); return; }
    setOpenId(p.id);
    setWait('');
    if (reports[p.id]) return;
    L.fetchReport(p.id, weights ?? {}).then((out) => {
      if (out.report) setReports((r) => ({ ...r, [p.id]: out.report! }));
      else setWait('OpenAlex is resting for now (its daily budget). Try again later.');
    }).catch(() => undefined);
  };
  const ids = shown.map((p) => p.id).join('|');
  useEffect(() => {                                 // their latest papers: one search for everyone on show
    let live = true;
    L.fetchRecent(shown).then((out) => {
      if (!live) return;
      setRecent(out.recent);
      if (out.busy) setNote('OpenAlex is resting for now (its daily budget): their latest papers come later.');
    }).catch(() => undefined);
    return () => { live = false; };
  }, [ids]);   // eslint-disable-line react-hooks/exhaustive-deps -- once per set

  return (
    <View>
      {note ? <Text style={[st.muted, { color: C.amber }]}>{note}</Text> : null}
      <Text style={st.muted}>People who lead your field, picked by your Model: a new set every {L.EVERY_DAYS} days (next on {day(L.nextChange(today()))}). Tap a name for their numbers.</Text>
      {!shown.length ? <Empty>The list isn&apos;t here yet.</Empty> : null}
      {shown.map((p) => (
        <View key={p.id} style={st.card}>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            <Pressable style={{ flex: 1 }} onPress={() => toggle(p)}><Text style={st.title}>{p.name}</Text></Pressable>
            <Text style={st.badge}>{badge(p)}</Text>
          </View>
          <Text style={st.muted}>{[p.why, p.institution].filter(Boolean).join(' · ')}</Text>
          {(recent[p.id] ?? []).map((w) => (
            <Pressable key={w.url + w.title} onPress={() => open(w.url, 'paper')}>
              <Text style={st.paper}>📄 {w.title}  ·  {day(w.date)}{w.venue ? ` · ${w.venue}` : ''}</Text>
            </Pressable>
          ))}
          <View style={st.row}>
            <Pressable onPress={() => toggle(p)} style={[st.btn, { backgroundColor: C.violet }]}><Text style={[st.btnText, { color: '#fff' }]}>{openId === p.id ? 'Hide' : 'Report'}</Text></Pressable>
            {following.has(p.id) ? <Text style={st.muted}>✓ Following</Text>
              : <Pressable onPress={() => onFollow({ id: p.id, name: p.name, institution: p.institution, topics: p.topics.slice(0, 3) })} style={st.btn}>
                <Text style={st.btnText}>Follow</Text></Pressable>}
            <Pressable onPress={() => open(L.links(p)[0][1], 'person')} style={st.btn}><Text style={st.btnText}>{L.links(p)[0][0]} ↗</Text></Pressable>
          </View>
          {openId === p.id ? <ReportBox person={p} rep={reports[p.id]} note={wait} /> : null}
        </View>
      ))}
      <Pressable onPress={() => open(REPORT_MAIL)}>
        <Text style={st.muted}>Something wrong (wrong person, wrong prize, someone who has passed away)? Report a mistake ↗</Text>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  muted: { color: C.muted, fontSize: 12, marginTop: 2, lineHeight: 17 },
  text: { color: C.text, fontSize: 13, lineHeight: 19, marginTop: 4 },
  head: { color: C.text, fontSize: 11.5, fontWeight: '800', letterSpacing: 0.6, marginTop: 12, marginBottom: 2 },
  card: { backgroundColor: C.card, borderRadius: 12, padding: 10, marginBottom: 6, marginTop: 6 },
  title: { color: C.text, fontSize: 14, fontWeight: '700', lineHeight: 19 },
  badge: { color: C.cyan, fontSize: 11.5, fontWeight: '800' },
  paper: { color: C.text, fontSize: 12.5, lineHeight: 18, marginTop: 4 },
  row: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginTop: 8 },
  btn: { backgroundColor: C.cardHi, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  btnText: { color: C.text, fontSize: 12.5, fontWeight: '700' },
  report: { borderWidth: 1, borderColor: C.violet, borderRadius: 10, padding: 10, marginTop: 8 },
  nums: { flexDirection: 'row', justifyContent: 'space-between', marginVertical: 10 },
  num: { color: C.text, fontSize: 17, fontWeight: '800' },
});
