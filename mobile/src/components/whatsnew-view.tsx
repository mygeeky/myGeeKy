// News → 📰 What's new, on the phone (the desktop's gui/whatsnew_ui.py): the AI and technology news the maker checked
// and published (lib/whatsnew-shape.ts, from TRACE), newest first and nudged toward your field. Plain text only; a
// link opens in the browser only if it's https (ui.open).
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useApp } from '../lib/app-state';
import { loadLists } from '../lib/curated';
import { C } from '../lib/theme';
import { ranked, type WhatsNew } from '../lib/whatsnew-shape';
import { open, s } from './ui';

const hostOf = (u: string) => {
  const m = /^https:\/\/([^/?#]+)/.exec(u);
  return m ? m[1].replace(/^www\./, '').toLowerCase() : '';
};

export function WhatsNewView() {
  const { settings } = useApp();
  const [items, setItems] = useState<WhatsNew[] | null>(null);
  useEffect(() => {
    let alive = true;
    loadLists().then((l) => {
      if (!alive) return;
      const weights: Record<string, number> = { ...(settings?.interests ?? {}) };
      for (const k of [...(settings?.keywords ?? []), ...(settings?.topics ?? [])]) weights[k.toLowerCase()] = 1;
      setItems(ranked(l.whatsnew ?? [], weights));
    }).catch(() => alive && setItems([]));
    return () => { alive = false; };
  }, [settings]);
  if (items === null) return <Text style={s.small}>Loading…</Text>;
  if (!items.length) {
    return <Text style={s.small}>Nothing here yet. New AI and technology news appears here once it has been checked: every item is read against its sources first.</Text>;
  }
  return (
    <>
      <Text style={[s.small, { marginBottom: 8 }]}>AI and technology news worth knowing, each item checked against its sources before it&apos;s shown.</Text>
      {items.map((it) => {
        const hosts = [...new Set(it.sources.map(hostOf).filter(Boolean))];
        return (
          <Pressable key={it.id} onPress={() => open(it.url, 'headline')} style={({ pressed }) => [w.card, pressed && { opacity: 0.85 }]}
                     accessibilityRole="link" accessibilityLabel={`${it.title}. Opens in your browser`}>
            <View style={w.top}>
              {it.topic ? <Text style={w.topic}>{it.topic}</Text> : null}
              <Text style={w.date}>{it.added}</Text>
            </View>
            <Text style={w.title}>{it.title}</Text>
            {it.summary ? <Text style={w.body}>{it.summary}</Text> : null}
            {it.why ? <Text style={w.why}>Why it matters: {it.why}</Text> : null}
            <Text style={w.sources}>{hosts.length} source{hosts.length === 1 ? '' : 's'}: {hosts.slice(0, 4).join(' · ')}  ·  Open ↗</Text>
          </Pressable>
        );
      })}
    </>
  );
}

const w = StyleSheet.create({
  card: { backgroundColor: C.card, borderRadius: 14, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: C.line, gap: 4 },
  top: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  topic: { color: C.cyan, fontSize: 11, fontWeight: '800' },
  date: { color: C.muted, fontSize: 11 },
  title: { color: C.text, fontSize: 15, fontWeight: '800', lineHeight: 21 },
  body: { color: C.text, fontSize: 13, lineHeight: 19 },
  why: { color: C.muted, fontSize: 12, lineHeight: 17 },
  sources: { color: C.muted, fontSize: 11, marginTop: 2 },
});
