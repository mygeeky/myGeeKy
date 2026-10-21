import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useApp } from '../lib/app-state';
import * as P from '../lib/packs';
import { follow, load as loadResearchers } from '../lib/researchers';
import { C, tint } from '../lib/theme';

// Receive a pack (You → Settings → 📦 Packs): the first code says how many there are, then it counts them in any
// order, shows which it has (✓ 1  ○ 2  ○ 3), asks for the next, and when all are in, shows what the pack holds
// before anything changes: Merge into mine, or Start from it.
export default function PackScan() {
  const { settings, save } = useApp();
  const [permission, requestPermission] = useCameraPermissions();
  const [g, setG] = useState<P.Gathering | null>(null);
  const [pack, setPack] = useState<P.Pack | null>(null);
  const [message, setMessage] = useState('');
  const gRef = useRef<P.Gathering | null>(null);
  const last = useRef('');

  const onScan = ({ data }: { data: string }) => {
    if (pack || data === last.current) return;          // the camera reports the same code many times a second
    last.current = data;
    const out = P.receive(gRef.current, data);
    gRef.current = out.g;
    setG(out.g);
    if (out.got === 'bad') setMessage("That's not a myGeeKy pack code.");
    else if (out.got === 'again') setMessage(`Already have code ${P.part(data)?.i}. Show the next one.`);
    else if (out.got === 'broken') setMessage("These codes don't make a whole pack. Start again from code 1.");
    else if (out.got === 'other') setMessage('That code is from a different pack: starting over with that one.');
    else setMessage('');
    if (out.got === 'new' || out.got === 'other' || out.got === 'done') Haptics.selectionAsync().catch(() => undefined);
    if (out.got === 'done' && out.pack) { setPack(out.pack); Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined); }
  };

  const take = async (how: 'merge' | 'start') => {
    if (!settings || !pack) return;
    const before = { keywords: settings.keywords, topics: settings.topics, field: settings.field };
    const had = new Set((await loadResearchers()).following.map((p) => p.id));
    const followed: string[] = [];
    for (const [id, name] of pack.r) if (!had.has(id)) { await follow({ id, name }); followed.push(id); }
    await save({ ...settings, ...P.applyPack(before, pack, how) });
    await P.saveUndo({ at: new Date().toISOString().slice(0, 10), note: pack.n, before, followed });
    router.back();
  };

  if (!permission) return <View style={st.safe} />;
  if (!permission.granted) {
    return (
      <SafeAreaView style={[st.safe, st.center]}>
        <Text style={st.title}>Receive a pack</Text>
        <Text style={st.body}>myGeeKy needs the camera only to read the pack&apos;s QR codes.</Text>
        <Pressable style={st.button} onPress={requestPermission}><Text style={st.buttonText}>Allow the camera</Text></Pressable>
        <Pressable onPress={() => router.back()}><Text style={st.link}>Back</Text></Pressable>
      </SafeAreaView>
    );
  }
  if (pack) {
    return (
      <SafeAreaView style={[st.safe, { backgroundColor: C.bg }]}>
        <ScrollView contentContainerStyle={{ padding: 20 }}>
          <Text style={[st.title, { color: C.text }]}>📦 A pack{pack.n ? `: ${pack.n}` : ''}</Text>
          <Text style={[st.body, { color: C.muted }]}>It holds {P.describe(pack)}. Nothing changes until you choose.</Text>
          {pack.k.length + pack.t.length ? <Text style={st.list}>🔤 {[...pack.k, ...pack.t].join(', ')}</Text> : null}
          {pack.f.length ? <Text style={st.list}>🔬 {pack.f.join(', ')}</Text> : null}
          {pack.r.length ? <Text style={st.list}>📄 {pack.r.map((p) => p[1] || p[0]).join(', ')}</Text> : null}
          <Pressable style={st.button} onPress={() => take('merge')}><Text style={st.buttonText}>Merge into mine (only adds)</Text></Pressable>
          <Pressable style={[st.button, { backgroundColor: C.card }]} onPress={() => take('start')}>
            <Text style={[st.buttonText, { color: C.text }]}>Start from it (its keywords, topics and field replace yours)</Text>
          </Pressable>
          <Text style={[st.body, { color: C.muted }]}>Either way you can undo it in You → Settings → 📦 Packs.</Text>
          <Pressable onPress={() => router.back()}><Text style={st.link}>Cancel</Text></Pressable>
        </ScrollView>
      </SafeAreaView>
    );
  }
  const need = P.missing(g);
  return (
    <View style={st.safe}>
      <CameraView style={StyleSheet.absoluteFill} facing="back" barcodeScannerSettings={{ barcodeTypes: ['qr'] }} onBarcodeScanned={onScan} />
      <SafeAreaView style={st.overlay} pointerEvents="box-none">
        <Text style={st.title}>Receive a pack</Text>
        {g ? (
          <>
            <Text style={st.body}>This pack has {g.n} codes.</Text>
            <View style={st.parts}>
              {Array.from({ length: g.n }, (_, i) => i + 1).map((i) => (
                <View key={i} style={[st.part, g.pieces[i] !== undefined && st.partOn]}>
                  <Text style={st.partText}>{g.pieces[i] !== undefined ? '✓' : ''} {i}</Text>
                </View>
              ))}
            </View>
            <Text style={st.next}>Got {g.n - need.length} of {g.n}. Now show code {need[0]}.</Text>
          </>
        ) : <Text style={st.body}>Point the camera at the first code (any one: it tells how many there are).</Text>}
        <View style={st.frame} />
        {message ? <Text style={st.message}>{message}</Text> : null}
        <Pressable onPress={() => router.back()}><Text style={st.link}>Back</Text></Pressable>
      </SafeAreaView>
    </View>
  );
}

const st = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#000' },
  center: { alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: C.bg },
  overlay: { flex: 1, alignItems: 'center', padding: 20, backgroundColor: 'rgba(0,0,0,0.25)' },
  title: { color: '#fff', fontSize: 22, fontWeight: '800', marginTop: 12, textAlign: 'center' },
  body: { color: tint(0.85), fontSize: 14, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  next: { color: '#fff', fontSize: 17, fontWeight: '800', marginTop: 10, textAlign: 'center' },
  parts: { flexDirection: 'row', gap: 10, marginTop: 10 },
  part: { minWidth: 54, paddingVertical: 8, borderRadius: 10, borderWidth: 2, borderColor: tint(0.6), alignItems: 'center' },
  partOn: { backgroundColor: C.green, borderColor: C.green },
  partText: { color: '#fff', fontWeight: '800', fontSize: 16 },
  list: { color: C.text, fontSize: 14, marginTop: 10, lineHeight: 20 },
  frame: { width: 250, height: 250, marginTop: 24, borderWidth: 3, borderColor: C.pink, borderRadius: 24 },
  message: { color: '#fff', backgroundColor: 'rgba(0,0,0,0.6)', padding: 10, borderRadius: 10, marginTop: 20, textAlign: 'center' },
  button: { backgroundColor: C.violet, borderRadius: 14, paddingVertical: 14, paddingHorizontal: 22, marginTop: 16 },
  buttonText: { color: '#fff', fontWeight: '800', fontSize: 15, textAlign: 'center' },
  link: { color: C.cyan, fontSize: 15, marginTop: 22, padding: 8, textAlign: 'center' },
});
