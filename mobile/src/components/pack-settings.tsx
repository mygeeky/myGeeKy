// Settings → Data & privacy → 📦 Packs: make a pack from your setup and show it as one to three QR codes, one at a time ("Code 2
// of 3", Back / Next), receive one (app/pack-scan.tsx), and undo the last pack you took. The desktop's
// gui/packs_ui.py makes and shows packs the same way.
import { router } from 'expo-router';
import QRCode from 'qrcode';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import Svg, { Path, Rect } from 'react-native-svg';
import { useApp } from '../lib/app-state';
import * as P from '../lib/packs';
import { load as loadResearchers, unfollow } from '../lib/researchers';
import { C } from '../lib/theme';

/** One QR code, drawn crisply (dark on white, as scanners like best). */
export function QrCode({ text, size }: { text: string; size: number }) {
  const path = useMemo(() => {
    const m = QRCode.create(text, { errorCorrectionLevel: 'M' }).modules;   // get(row, column)
    let d = '';
    for (let y = 0; y < m.size; y++) for (let x = 0; x < m.size; x++) if (m.get(y, x)) d += `M${x + 3} ${y + 3}h1v1h-1z`;
    return { d, n: m.size + 6 };
  }, [text]);
  return (
    <Svg width={size} height={size} viewBox={`0 0 ${path.n} ${path.n}`}>
      <Rect width={path.n} height={path.n} fill="#fff" />
      <Path d={path.d} fill="#12121c" />
    </Svg>
  );
}

/** The codes, one at a time, with "Code 2 of 3" and Back / Next. */
export function PackCodes({ codes, onClose }: { codes: string[]; onClose: () => void }) {
  const [at, setAt] = useState(0);
  return (
    <View style={{ alignItems: 'center', marginTop: 8 }}>
      <Text style={st.count}>{codes.length > 1 ? `Code ${at + 1} of ${codes.length}` : 'Your pack'}</Text>
      {codes.length > 1 ? <View style={st.dots}>{codes.map((_, i) => <View key={i} style={[st.dot, i === at && st.dotOn]} />)}</View> : null}
      <View style={{ padding: 8, backgroundColor: '#fff', borderRadius: 12 }}><QrCode text={codes[at]} size={280} /></View>
      <Text style={[st.text, { textAlign: 'center', marginTop: 6 }]}>
        On the other phone: Settings → Data & privacy → 📦 Packs → Receive a pack. {codes.length > 1 ? 'It counts the codes and tells you when to show the next one.' : ''}
      </Text>
      <View style={st.row}>
        {codes.length > 1 ? <Pressable disabled={at === 0} onPress={() => setAt(at - 1)} style={[st.btn, at === 0 && { opacity: 0.4 }]}><Text style={st.btnText}>‹ Back</Text></Pressable> : null}
        {at < codes.length - 1
          ? <Pressable onPress={() => setAt(at + 1)} style={[st.btn, { backgroundColor: C.violet }]}><Text style={[st.btnText, { color: '#fff' }]}>Next code ›</Text></Pressable>
          : <Pressable onPress={onClose} style={st.btn}><Text style={st.btnText}>Done</Text></Pressable>}
      </View>
    </View>
  );
}

export function PackSettings() {
  const { settings, save } = useApp();
  const [parts, setParts] = useState<Set<string>>(new Set(['words', 'field']));
  const [note, setNote] = useState('');
  const [people, setPeople] = useState<{ id: string; name: string }[]>([]);
  const [shown, setShown] = useState<string[] | null>(null);
  const [undo, setUndo] = useState<P.Undo | null>(null);
  const [said, setSaid] = useState('');
  const again = useCallback(() => {
    loadResearchers().then((s) => setPeople(s.following.map((p) => ({ id: p.id, name: p.name })))).catch(() => undefined);
    P.loadUndo().then(setUndo).catch(() => undefined);
  }, []);
  useEffect(() => { again(); }, [again]);
  if (!settings) return null;
  const pack = P.make(settings, parts, note, people);
  const codes = P.codes(pack);
  const flip = (k: string) => { const n = new Set(parts); if (n.has(k)) n.delete(k); else n.add(k); setParts(n); setShown(null); };
  const choices: [string, string][] = [['words', `Keywords and topics (${settings.keywords.length + settings.topics.length})`],
    ['field', `Research field${settings.field.length ? ` (${settings.field.slice(0, 2).join(', ')}…)` : ' (none yet)'}`],
    ['people', `Researchers you follow (${people.length})`]];
  const undoIt = async () => {
    if (!undo) return;
    for (const id of undo.followed) await unfollow(id);
    await save({ ...settings, ...undo.before });
    await P.saveUndo(null);
    setSaid('Undone: your keywords, topics and field are back as they were.');
    again();
  };
  return (
    <View>
      <Text style={st.text}>Share your setup like a seed: a lab or a class starts from yours instead of from zero. It goes only as QR codes the other phone scans, with no internet. Only what you tick goes in; never your account, tokens or Model.</Text>
      {choices.map(([k, label]) => (
        <View key={k} style={st.choice}>
          <Text style={[st.text, { flex: 1 }]}>{label}</Text>
          <Switch value={parts.has(k)} onValueChange={() => flip(k)} />
        </View>
      ))}
      <TextInput value={note} onChangeText={(t) => { setNote(t); setShown(null); }} maxLength={120} placeholder="A note, e.g. Plant genomics lab, 2026" placeholderTextColor={C.muted} style={st.input} />
      <Text style={st.text}>{codes.length ? `Holds ${P.describe(pack)}: ${codes.length} QR code${codes.length > 1 ? 's' : ''}.` : 'Too much for three QR codes: untick something.'}</Text>
      {shown ? <PackCodes codes={shown} onClose={() => setShown(null)} /> : (
        <View style={st.row}>
          <Pressable disabled={!codes.length || P.describe(pack) === 'nothing yet'} onPress={() => setShown(codes)}
                     style={[st.btn, { backgroundColor: C.violet }, (!codes.length || P.describe(pack) === 'nothing yet') && { opacity: 0.4 }]}>
            <Text style={[st.btnText, { color: '#fff' }]}>📦 Show my pack</Text>
          </Pressable>
          <Pressable onPress={() => router.push('/pack-scan')} style={st.btn}><Text style={st.btnText}>📷 Receive a pack</Text></Pressable>
        </View>
      )}
      {undo ? (
        <Pressable onPress={undoIt} style={[st.btn, { alignSelf: 'flex-start' }]}>
          <Text style={st.btnText}>↩ Undo the pack from {undo.at}{undo.note ? ` (${undo.note})` : ''}</Text>
        </Pressable>
      ) : null}
      {said ? <Text style={[st.text, { color: C.green }]}>{said}</Text> : null}
    </View>
  );
}

const st = StyleSheet.create({
  text: { color: C.muted, fontSize: 13, lineHeight: 18 },
  count: { color: C.text, fontSize: 20, fontWeight: '800' },
  dots: { flexDirection: 'row', gap: 6, marginVertical: 6 },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: C.muted, opacity: 0.4 },
  dotOn: { backgroundColor: C.violet, opacity: 1 },
  choice: { flexDirection: 'row', alignItems: 'center', marginTop: 4 },
  input: { color: C.text, borderColor: C.muted, borderWidth: 1, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 6, marginVertical: 6, fontSize: 13 },
  row: { flexDirection: 'row', gap: 8, marginVertical: 8, flexWrap: 'wrap' },
  btn: { backgroundColor: C.card, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, marginTop: 4 },
  btnText: { color: C.text, fontWeight: '700', fontSize: 13 },
});
