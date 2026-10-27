// Small building blocks shared by the screens, in myGeeKy's style.
import { ReactNode } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { timeAgo } from '../lib/app-state';
import { logClick } from '../lib/badges';
import { C, tint } from '../lib/theme';
import { spot } from './tour-overlay';

/** A small switch between the parts of a tab (e.g. Headlines | Papers). */
// A long name ("Protocols", "Conferences") shrinks to fit its segment instead of being cut to "Protoc…".
export function Segments<T extends string>({ value, options, onChange }: {
  value: T; options: [T, string][]; onChange: (v: T) => void;
}) {
  return (
    <View style={s.segments}>
      {options.map(([v, label]) => (
        <Pressable key={v} onPress={() => onChange(v)} style={[s.segment, v === value && s.segmentOn]}>
          <Text style={[s.segmentText, v === value && s.segmentTextOn]} numberOfLines={1}
                adjustsFontSizeToFit minimumFontScale={0.7}>{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

/** A heading on a page; `tour` names it for GeeKOc's Settings tour ('settings:cv'), which shines a light on it. */
export function Section({ children, tour }: { children: ReactNode; tour?: string }) {
  return <Text ref={tour ? spot(tour) : undefined} style={s.section}>{children}</Text>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <Text style={s.empty}>{children}</Text>;
}

export function Card({ onPress, children, style }: { onPress?: () => void; children: ReactNode; style?: object }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [s.card, pressed && s.cardPressed, style]}>
      {children}
    </Pressable>
  );
}

/** Opens in the phone's browser -- only https links ever reach here. `kind`
 *  (headline, paper, model…) counts toward your badges; nothing else is kept. */
export function open(url: string, kind?: string, cat?: string, explore?: boolean) {
  if (!url.startsWith('https://')) return;
  if (kind) logClick(kind, cat, explore);
  Linking.openURL(url);
}

export { timeAgo };

export const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 10 },
  logo: { width: 30, height: 30, borderRadius: 8 },
  title: { color: C.text, fontSize: 24, fontWeight: '800', letterSpacing: -0.4, flex: 1 },
  strip: { flexDirection: 'row', gap: 4 },
  stripIcon: { width: 26, height: 26, borderRadius: 13, borderWidth: 2, alignItems: 'center', justifyContent: 'center',
               backgroundColor: tint(0.06) },
  segments: { flexDirection: 'row', marginHorizontal: 16, marginBottom: 6, padding: 3, borderRadius: 12,
              backgroundColor: C.card, borderWidth: 1, borderColor: C.line },
  segment: { flex: 1, paddingVertical: 8, borderRadius: 9, alignItems: 'center' },
  segmentOn: { backgroundColor: C.violet },
  segmentText: { color: C.muted, fontSize: 13, fontWeight: '700' },
  segmentTextOn: { color: '#fff' },
  scroll: { paddingHorizontal: 16, paddingTop: 4, paddingBottom: 40 },
  subtitle: { color: C.muted, fontSize: 13, lineHeight: 19 },
  meta: { color: C.muted, fontSize: 12, marginTop: 6 },
  error: { color: C.red, fontSize: 13, marginTop: 8 },
  section: { color: C.text, fontSize: 12, fontWeight: '800', letterSpacing: 0.8, marginTop: 18, marginBottom: 8 },
  empty: { color: C.muted, fontSize: 14, marginTop: 8, lineHeight: 20 },
  card: { backgroundColor: C.card, borderRadius: 14, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: C.line },
  cardPressed: { backgroundColor: C.cardHi },
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  itemTitle: { color: C.text, fontSize: 15, lineHeight: 21, flex: 1 },
  name: { color: C.text, fontSize: 15, fontWeight: '800' },
  small: { color: C.muted, fontSize: 12, marginTop: 3 },
});
