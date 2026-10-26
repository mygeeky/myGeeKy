// 🔔 Notifications: one switch per kind, all off until you switch one on -- in setup (short) and in More → Settings
// (full: what you agreed to in one line, how often, quiet hours, and "Turn all off"). The desktop has the same in
// setup and ⚙ Settings (gui/notify_ui.py). Each change is saved at once (lib/notify-store.ts).
import { useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, Switch, Text, View } from 'react-native';
import * as N from '../lib/notify';
import { loadNotify, permission, saveNotify } from '../lib/notify-store';
import { C } from '../lib/theme';

export function NotifySettings({ full = false }: { full?: boolean }) {
  const [s, setS] = useState<N.Settings | null>(null);
  const [blocked, setBlocked] = useState(false);
  useEffect(() => {
    loadNotify().then(setS).catch(() => setS(N.defaults()));
    permission().then((p) => setBlocked(p === 'blocked')).catch(() => undefined);
  }, []);
  if (!s) return null;

  const change = async (next: N.Settings) => {
    setS(next);                                         // at once on screen; Android may still say no
    const { saved, denied } = await saveNotify(next);
    setS(saved);
    setBlocked(denied);
  };
  const toggle = (kind: string, on: boolean) =>
    change({ ...s, kinds: on ? [...s.kinds, kind] : s.kinds.filter((k) => k !== kind) });
  const hour = (i: 0 | 1, step: number) => {
    const q: [number, number] = [...s.quiet];
    q[i] = (q[i] + step + 24) % 24;
    change({ ...s, quiet: q });
  };
  const on = s.kinds.length > 0;

  return (
    <View>
      {full ? <Text style={[st.summary, on && { color: C.green }]}>{N.describe(s)}</Text> : (
        <Text style={st.lead}>
          myGeeKy can tell you, at most once a day, when something important fits you. All off unless you switch it
          on; you can change it any time in More → Settings.
        </Text>
      )}
      {blocked ? (
        <View style={st.warn}>
          <Text style={st.warnText}>Android isn&apos;t letting myGeeKy notify you, so everything stays off.</Text>
          <Pressable onPress={() => Linking.openSettings()} hitSlop={6}><Text style={st.link}>Allow it in Android&apos;s settings ↗</Text></Pressable>
        </View>
      ) : null}
      {N.KINDS.map(([kind, emoji, label, about]) => (
        <View key={kind} style={st.row}>
          <View style={{ flex: 1 }}>
            <Text style={st.label}>{emoji}  {label}</Text>
            <Text style={st.about}>{about}</Text>
          </View>
          <Switch value={s.kinds.includes(kind)} onValueChange={(v) => toggle(kind, v)}
                  trackColor={{ true: C.violet, false: C.raised }} thumbColor="#fff" />
        </View>
      ))}
      {on ? (
        <View style={st.every}>
          {(['daily', 'weekly'] as const).map((e) => (
            <Pressable key={e} onPress={() => change({ ...s, every: e })} style={[st.chip, s.every === e && st.chipOn]}>
              <Text style={[st.chipText, s.every === e && { color: C.text, fontWeight: '800' }]}>
                {e === 'daily' ? 'At most once a day' : 'At most once a week'}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : null}
      {full && on ? (
        <View style={st.quiet}>
          <Text style={st.label}>Quiet hours</Text>
          {([0, 1] as const).map((i) => (
            <View key={i} style={st.stepper}>
              <Text style={st.about}>{i === 0 ? 'from' : 'to'}</Text>
              <Pressable onPress={() => hour(i, -1)} hitSlop={8} style={st.step}><Text style={st.stepText}>−</Text></Pressable>
              <Text style={st.hour}>{String(s.quiet[i]).padStart(2, '0')}:00</Text>
              <Pressable onPress={() => hour(i, 1)} hitSlop={8} style={st.step}><Text style={st.stepText}>+</Text></Pressable>
            </View>
          ))}
        </View>
      ) : null}
      {full && on ? (
        <Pressable onPress={() => change({ ...s, kinds: [] })} style={({ pressed }) => [st.off, pressed && { opacity: 0.8 }]}>
          <Text style={st.offText}>Turn all off</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  lead: { color: C.muted, fontSize: 13.5, lineHeight: 19, marginBottom: 6 },
  summary: { color: C.muted, fontSize: 14, fontWeight: '700', marginBottom: 6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: C.line },
  label: { color: C.text, fontSize: 14.5, fontWeight: '700' },
  about: { color: C.muted, fontSize: 12, marginTop: 2 },
  every: { flexDirection: 'row', gap: 8, marginTop: 12, flexWrap: 'wrap' },
  chip: { borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7, backgroundColor: C.card, borderWidth: 1, borderColor: C.line },
  chipOn: { borderColor: C.violet, backgroundColor: 'rgba(122,92,255,0.25)' },
  chipText: { color: C.muted, fontSize: 13 },
  quiet: { marginTop: 14, gap: 6 },
  stepper: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  step: { width: 32, height: 32, borderRadius: 10, backgroundColor: C.card, alignItems: 'center', justifyContent: 'center' },
  stepText: { color: C.text, fontSize: 18, fontWeight: '800' },
  hour: { color: C.text, fontSize: 15, fontWeight: '700', minWidth: 52, textAlign: 'center' },
  off: { marginTop: 14, borderRadius: 12, paddingVertical: 11, alignItems: 'center', borderWidth: 1, borderColor: C.red },
  offText: { color: C.red, fontSize: 14, fontWeight: '800' },
  warn: { backgroundColor: 'rgba(255,196,87,0.12)', borderColor: 'rgba(255,196,87,0.45)', borderWidth: 1, borderRadius: 12,
    padding: 10, marginVertical: 6 },
  warnText: { color: C.text, fontSize: 13, lineHeight: 18 },
  link: { color: C.violet, fontSize: 13, fontWeight: '800', marginTop: 6 },
});
