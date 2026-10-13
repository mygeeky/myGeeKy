// Small pieces shared by the 🌱 Grow and 🎯 Chances planets: the 👍/👎 pair, a
// "hidden by your 👎" line, and a card. Everything shown comes from lists someone
// else wrote, so it's always plain Text (React Native never renders markup).
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { C } from '../lib/theme';

export function Thumbs({ vote, onVote }: { vote: number; onVote: (up: boolean) => Promise<number> }) {
  const [v, setV] = useState(vote);
  const press = async (up: boolean) => setV(await onVote(up).catch(() => v));
  return (
    <View style={s.thumbs}>
      <Pressable onPress={() => press(true)} style={[s.thumb, v > 0 && s.thumbOn]} accessibilityLabel="More like this"
                 accessibilityState={{ selected: v > 0 }}>
        <Text style={s.thumbText}>👍</Text>
      </Pressable>
      <Pressable onPress={() => press(false)} style={[s.thumb, v < 0 && s.thumbOn]} accessibilityLabel="Not for me"
                 accessibilityState={{ selected: v < 0 }}>
        <Text style={s.thumbText}>👎</Text>
      </Pressable>
    </View>
  );
}

export function Hidden({ n, onShow }: { n: number; onShow: () => void }) {
  if (!n) return null;
  return (
    <View style={s.hiddenRow}>
      <Text style={s.muted}>{n} hidden by your 👎.</Text>
      <Pressable onPress={onShow}><Text style={s.link}>Show them again</Text></Pressable>
    </View>
  );
}

export function GCard({ children }: { children: React.ReactNode }) {
  return <View style={s.card}>{children}</View>;
}

export function Button({ label, onPress, accent, disabled }: { label: string; onPress: () => void; accent?: boolean; disabled?: boolean }) {
  return (
    <Pressable onPress={onPress} disabled={disabled}
               style={[s.btn, accent && { backgroundColor: C.violet }, disabled && { opacity: 0.5 }]}>
      <Text style={[s.btnText, accent && { color: '#fff' }]}>{label}</Text>
    </Pressable>
  );
}

export const s = StyleSheet.create({
  thumbs: { flexDirection: 'row', gap: 4 },
  thumb: { width: 40, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  thumbOn: { backgroundColor: 'rgba(122,92,255,0.35)' },
  thumbText: { fontSize: 16 },
  card: { backgroundColor: C.card, borderRadius: 14, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: C.line },
  head: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  title: { color: C.text, fontSize: 15, fontWeight: '800', lineHeight: 20, flex: 1 },
  muted: { color: C.muted, fontSize: 12.5, lineHeight: 18, marginTop: 3 },
  body: { color: C.text, fontSize: 13, lineHeight: 19, marginTop: 4 },
  good: { color: C.green, fontSize: 12.5, marginTop: 3 },
  warn: { color: C.amber, fontSize: 12, marginTop: 4 },
  link: { color: C.cyan, fontSize: 12.5, textDecorationLine: 'underline' },
  hiddenRow: { flexDirection: 'row', gap: 10, alignItems: 'center', marginVertical: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8, flexWrap: 'wrap' },
  btn: { borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9, backgroundColor: 'rgba(255,255,255,0.08)' },
  btnText: { color: C.text, fontSize: 13, fontWeight: '700' },
  section: { color: C.text, fontSize: 12, fontWeight: '800', letterSpacing: 0.8, marginTop: 14, marginBottom: 8 },
  step: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', marginTop: 10 },
  box: { width: 30, height: 30, borderRadius: 8, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.06)' },
  bar: { height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.10)', marginTop: 8, overflow: 'hidden' },
  barFill: { height: 4, backgroundColor: C.green },
});
