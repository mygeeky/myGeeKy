// You → 📑 Cited by: your citations at a glance, the new papers citing you, the people who cite you most, and where
// you're read -- the desktop's gui/citedby_ui.py. lib/cited-by.ts does the reading (the same as citedby.py).
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useApp } from '../lib/app-state';
import { authorFor, loadCitedBy, refreshCitedBy, summary, type CitedState } from '../lib/cited-by';
import { C } from '../lib/theme';
import { GeekLoader, useHold } from './geek-loader';
import { open } from './ui';

export const flag = (code: string) => (/^[A-Za-z]{2}$/.test(code ?? '')
  ? String.fromCodePoint(...code.toUpperCase().split('').map((c) => 0x1f1e6 + c.charCodeAt(0) - 65)) : '🌍');

export function CitedByView() {
  const { settings } = useApp();
  const [author, setAuthor] = useState<string | null>(null);
  const [state, setState] = useState<CitedState | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    (async () => {
      const a = await authorFor(settings?.orcid ?? '', settings?.openalex ?? '');
      if (!live) return;
      setAuthor(a);
      if (!a) return;
      const kept = await loadCitedBy();
      if (live && kept.author === a) setState(kept);
      const out = await refreshCitedBy(a);
      if (!live) return;
      setState(out.state.author === a ? out.state : {});
      setBusy(!!out.busy);
    })().catch(() => undefined);
    return () => { live = false; };
  }, [settings?.orcid, settings?.openalex]);
  const holding = useHold(author === null || (!!author && state === null));
  if (holding) return <GeekLoader text="Looking for who cites you…" />;
  if (!author) {
    return <Text style={st.muted}>See who cites your papers: add your ORCID iD, or find your papers by your name (Settings → Your profile → Your papers).</Text>;
  }
  const s = summary(state ?? {}, new Date().toISOString().slice(0, 10));
  const tot = s.totals as { cited?: number; h?: number };
  const top = Math.max(1, ...s.countries.map((c) => c.count));
  return (
    <View style={{ paddingBottom: 24 }}>
      <View style={st.tiles}>
        {[[tot.cited ?? 0, 'citations'], [tot.h ?? 0, 'h-index'], [s.this_month, 'this month'], [s.new, 'new to you']].map(([v, k]) => (
          <View key={String(k)} style={st.tile}><Text style={st.tileV}>{String(v)}</Text><Text style={st.tileK} numberOfLines={1}>{k}</Text></View>
        ))}
      </View>
      {busy ? <Text style={[st.muted, { color: C.amber, marginTop: 8 }]}>OpenAlex is busy right now: this is what was found before. It looks again tomorrow.</Text> : null}

      <Text style={st.head}>📑 NEW PAPERS CITING YOU</Text>
      {s.citing.length ? s.citing.slice(0, 12).map((c) => {
        const first = c.authors[0];
        const who = first ? `${first.name}${c.authors.length > 1 ? ' et al.' : ''}` : '';
        const where = first ? [first.institution, first.country].filter(Boolean).join(', ') : '';
        const mine = c.cites_titles.filter(Boolean);
        return (
          <Pressable key={c.id} onPress={() => c.url.startsWith('https://') && open(c.url)} style={({ pressed }) => [st.card, pressed && { opacity: 0.8 }]}>
            <Text style={st.title}>{c.new ? '🆕 ' : ''}{c.title}</Text>
            <Text style={st.muted}>{[who, where, c.date].filter(Boolean).join(' · ')}</Text>
            {mine.length ? <Text style={st.cites} numberOfLines={2}>cites: {mine.slice(0, 2).map((m) => m.slice(0, 70)).join('; ')}</Text> : null}
          </Pressable>
        );
      }) : <Text style={st.muted}>No citing papers found yet. They appear here as they&apos;re published.</Text>}

      {s.people.length ? <>
        <Text style={st.head}>👥 WHO CITES YOU MOST</Text>
        {s.people.slice(0, 6).map((p) => (
          <Pressable key={p.id || p.name} onPress={() => p.id && open(`https://openalex.org/${p.id}`)} style={({ pressed }) => [st.person, pressed && { opacity: 0.8 }]}>
            <Text style={st.name} numberOfLines={1}>{flag(p.country)}  {p.name}</Text>
            {p.institution ? <Text style={[st.muted, { flex: 1 }]} numberOfLines={1}>{p.institution}</Text> : <View style={{ flex: 1 }} />}
            <Text style={st.muted}>{p.count}×</Text>
          </Pressable>
        ))}
      </> : null}

      {s.countries.length ? <>
        <Text style={st.head}>🌍 WHERE YOU&apos;RE READ</Text>
        {s.countries.slice(0, 6).map((c) => (
          <View key={c.code} style={st.bar}>
            <Text style={[st.muted, { width: 52, color: C.text }]}>{flag(c.code)} {c.code}</Text>
            <View style={[st.fill, { width: `${Math.max(4, (c.count / top) * 60)}%` }]} />
            <Text style={st.muted}>{c.count}</Text>
          </View>
        ))}
      </> : null}
      <Pressable onPress={() => open('https://openalex.org')} hitSlop={6}>
        <Text style={[st.muted, { marginTop: 12 }]}>Data: <Text style={{ color: C.violet }}>OpenAlex</Text>, checked once a day.</Text>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  tiles: { flexDirection: 'row', gap: 6, marginTop: 6 },
  tile: { flex: 1, backgroundColor: C.card, borderRadius: 10, paddingVertical: 7, alignItems: 'center' },
  tileV: { color: C.text, fontSize: 16, fontWeight: '800' },
  tileK: { color: C.muted, fontSize: 10.5 },
  head: { color: C.text, fontSize: 11.5, fontWeight: '800', letterSpacing: 0.6, marginTop: 16, marginBottom: 6 },
  card: { backgroundColor: C.card, borderRadius: 12, padding: 10, marginBottom: 6 },
  title: { color: C.text, fontSize: 14, fontWeight: '700', lineHeight: 19 },
  muted: { color: C.muted, fontSize: 12, marginTop: 2 },
  cites: { color: C.cyan, fontSize: 11.5, marginTop: 3 },
  person: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: C.card, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8, marginBottom: 5 },
  name: { color: C.text, fontSize: 13, fontWeight: '700', maxWidth: '50%' },
  bar: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  fill: { height: 7, borderRadius: 4, backgroundColor: C.violet },
});
