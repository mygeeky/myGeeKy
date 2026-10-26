// Circle → Researchers → 🌟 Leading lights: a few people who lead your field (a new set every three days, picked by your
// Model), each with why (🏅 🏆 📈 🛠), their latest papers, Follow and their links; a tap opens their report -- the
// desktop's gui/lights_ui.py. lib/lights.ts does the reading. Everything is plain text (it comes from the internet).
import { useEffect, useMemo, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
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

function ReportSheet({ person, onClose }: { person: L.Light; onClose: () => void }) {
  const { profile } = useApp();
  const [rep, setRep] = useState<L.Report | null>(null);
  const [note, setNote] = useState('');
  const [width, setWidth] = useState(0);
  useEffect(() => {
    let live = true;
    L.fetchReport(person.id, profile?.weights ?? {}).then((out) => {
      if (!live) return;
      if (out.report) setRep(out.report); else setNote('OpenAlex is resting for now (its daily budget). Try again later.');
    }).catch(() => undefined);
    return () => { live = false; };
  }, [person.id, profile?.weights]);
  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={st.shade}>
        <View style={st.sheet}>
          <ScrollView onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
            <Text style={st.big}>{person.name}</Text>
            <Text style={st.text}>{badge(person)} · {person.why}</Text>
            <Text style={st.muted}>{rep?.institution || person.institution}</Text>
            {!rep ? <Text style={[st.muted, { marginTop: 12 }]}>{note || `Reading ${person.name}'s record…`}</Text> : <>
              <View style={st.nums}>
                {([[rep.works, 'papers'], [rep.cited, 'citations'], [rep.h, 'h-index'], [rep.i10, 'i10-index']] as [number, string][]).map(([v, w]) => (
                  <View key={w}><Text style={st.num}>{v.toLocaleString('en')}</Text><Text style={st.muted}>{w}</Text></View>
                ))}
              </View>
              <Text style={st.muted}>Papers (bars) and citations (line), the last ten years</Text>
              {width ? <YearBars years={rep.years} width={width} /> : null}
              {rep.topics.length ? <Text style={st.text}>Topics: {rep.topics.map(([t, mine]) => (mine ? '★ ' : '') + t).join(', ')}
                {rep.topics.some(([, m]) => m) ? '   (★ also yours)' : ''}</Text> : null}
              {rep.top.length ? <Text style={st.head}>MOST CITED</Text> : null}
              {rep.top.map((w) => (
                <Pressable key={w.url} onPress={() => open(w.url, 'paper')}>
                  <Text style={st.text}>{w.title}  ·  {w.year || ''} · {w.cited.toLocaleString('en')} citations</Text>
                </Pressable>
              ))}
            </>}
            <View style={st.row}>
              {L.links(person).map(([word, url]) => (
                <Pressable key={word} onPress={() => open(url, 'person')} style={st.btn}><Text style={st.btnText}>{word} ↗</Text></Pressable>
              ))}
            </View>
            {person.source ? <Pressable onPress={() => open(person.source)}><Text style={st.muted}>Why they&apos;re here: source ↗</Text></Pressable> : null}
          </ScrollView>
          <Pressable onPress={onClose} style={[st.btn, { alignSelf: 'flex-end', marginTop: 8 }]}><Text style={st.btnText}>Close</Text></Pressable>
        </View>
      </View>
    </Modal>
  );
}

export function LightsView({ following, onFollow }: { following: Set<string>; onFollow: (p: { id: string; name: string; institution: string; topics: string[] }) => void }) {
  const { profile } = useApp();
  const weights = profile?.weights;
  const shown = useMemo(() => L.pick(L.load().people, weights ?? {}, today()), [weights]);
  const [recent, setRecent] = useState<Record<string, L.Paper[]>>({});
  const [note, setNote] = useState('');
  const [report, setReport] = useState<L.Light | null>(null);
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
            <Pressable style={{ flex: 1 }} onPress={() => setReport(p)}><Text style={st.title}>{p.name}</Text></Pressable>
            <Text style={st.badge}>{badge(p)}</Text>
          </View>
          <Text style={st.muted}>{[p.why, p.institution].filter(Boolean).join(' · ')}</Text>
          {(recent[p.id] ?? []).map((w) => (
            <Pressable key={w.url + w.title} onPress={() => open(w.url, 'paper')}>
              <Text style={st.paper}>📄 {w.title}  ·  {day(w.date)}{w.venue ? ` · ${w.venue}` : ''}</Text>
            </Pressable>
          ))}
          <View style={st.row}>
            <Pressable onPress={() => setReport(p)} style={[st.btn, { backgroundColor: C.violet }]}><Text style={[st.btnText, { color: '#fff' }]}>Report</Text></Pressable>
            {following.has(p.id) ? <Text style={st.muted}>✓ Following</Text>
              : <Pressable onPress={() => onFollow({ id: p.id, name: p.name, institution: p.institution, topics: p.topics.slice(0, 3) })} style={st.btn}>
                <Text style={st.btnText}>Follow</Text></Pressable>}
            <Pressable onPress={() => open(L.links(p)[0][1], 'person')} style={st.btn}><Text style={st.btnText}>{L.links(p)[0][0]} ↗</Text></Pressable>
          </View>
        </View>
      ))}
      <Pressable onPress={() => open(REPORT_MAIL)}>
        <Text style={st.muted}>Something wrong (wrong person, wrong prize, someone who has passed away)? Report a mistake ↗</Text>
      </Pressable>
      {report ? <ReportSheet person={report} onClose={() => setReport(null)} /> : null}
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
  shade: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: C.bg, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 16, maxHeight: '88%' },
  big: { color: C.text, fontSize: 18, fontWeight: '800' },
  nums: { flexDirection: 'row', justifyContent: 'space-between', marginVertical: 10 },
  num: { color: C.text, fontSize: 17, fontWeight: '800' },
});
