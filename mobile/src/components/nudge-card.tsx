// The card that asks again for what setup skipped (lib/nudges.ts decides which and when): above the page, with its
// one action (opens Settings → Accounts, and counts as "Not now" so it comes back if nothing gets linked), "Not now"
// and "Don't ask again". The desktop has the same card (gui/nudge_ui.py).
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { load, never, pick, save, skip, text, today, type NudgeKey } from '../lib/nudges';
import { C } from '../lib/theme';

/** `missing` is null while what's linked isn't known yet: no card then (it would ask for what you may have). */
export function NudgeCard({ page, missing, onGo }: { page: string; missing: NudgeKey[] | null; onGo: () => void }) {
  const [picked, setPicked] = useState<{ page: string; key: NudgeKey | '' }>({ page: '', key: '' });
  const missingKey = missing === null ? null : missing.join(',');
  useEffect(() => {
    if (!page || missingKey === null) return;
    let live = true;
    (async () => {
      const s = await load();
      const k = pick(s, page, today(), missingKey ? (missingKey.split(',') as NudgeKey[]) : []);
      await save(s);
      if (live) setPicked({ page, key: k });
    })().catch(() => undefined);
    return () => { live = false; };
  }, [page, missingKey]);
  const shown = picked.page === page && missingKey !== null ? picked.key : '';    // only for the page it was picked on
  if (!shown) return null;
  const t = text(shown, 'phone');
  const act = (what: 'go' | 'skip' | 'never') => {
    const key = shown;
    setPicked({ page, key: '' });
    load().then((s) => { (what === 'never' ? never : skip)(s, key); return save(s); }).catch(() => undefined);
    if (what === 'go') onGo();
  };
  return (
    <View style={st.card}>
      <Text style={st.title}>{t.title}</Text>
      <Text style={st.text}>{t.text}</Text>
      <View style={st.row}>
        <Pressable onPress={() => act('go')} style={st.go} accessibilityRole="button"><Text style={st.goText}>{t.go}</Text></Pressable>
        <Pressable onPress={() => act('skip')} accessibilityRole="button" hitSlop={8}><Text style={st.quiet}>Not now</Text></Pressable>
        <Pressable onPress={() => act('never')} accessibilityRole="button" hitSlop={8}><Text style={st.quiet}>Don&apos;t ask again</Text></Pressable>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  card: { backgroundColor: C.card, borderWidth: 1.5, borderColor: C.violet, borderRadius: 16, padding: 14, marginBottom: 12, gap: 6 },
  title: { color: C.text, fontSize: 16, fontWeight: '800' },
  text: { color: C.muted, fontSize: 13.5, lineHeight: 19 },
  row: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 14, marginTop: 4 },
  go: { backgroundColor: C.violet, borderRadius: 12, paddingVertical: 9, paddingHorizontal: 14 },
  goText: { color: '#ffffff', fontWeight: '800', fontSize: 14 },
  quiet: { color: C.muted, fontSize: 13.5, fontWeight: '600' },
});
