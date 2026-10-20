// Circle → 📄 Researchers: 🆕 New work from the people you follow (preprints first, a preprint and its published version
// as one), 👥 Following (find anyone by name, with the "is this the right one?" check), ✨ Suggested (who cites you, who
// leads your field's rising papers). The parts are planets in the navigation, not tabs here -- the desktop's
// gui/researchers_ui.py. lib/researchers.ts does the reading.
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { loadCitedBy, summary as citedSummary } from '../lib/cited-by';
import { readCache } from '../lib/storage';
import * as R from '../lib/researchers';
import type { Candidate } from '../lib/whois';
import { C } from '../lib/theme';
import { GeekLoader } from './geek-loader';
import { Empty, open } from './ui';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const dayText = (iso: string) => (iso.length >= 10 ? `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}` : iso);
const rateText = (r: number) => (r >= 1 ? `about ${Math.round(r)} paper${Math.round(r) !== 1 ? 's' : ''} a month` : r > 0 ? `about ${Math.round(r * 12)} a year` : 'nothing in the last year yet');
const today = () => new Date().toISOString().slice(0, 10);

export function ResearchersView({ part }: { part: string }) {
  const [state, setState] = useState<R.State | null>(null);
  const [note, setNote] = useState('');
  const [query, setQuery] = useState('');
  const [cands, setCands] = useState<Candidate[]>([]);
  const [sugg, setSugg] = useState<R.Suggestion[]>([]);
  const reload = useCallback(() => R.load().then(setState).catch(() => undefined), []);

  useEffect(() => {
    let live = true;
    reload();
    R.refresh().then((out) => { if (live) { setState(out.state); if (out.busy) setNote('OpenAlex is resting for now (its daily budget): this is what was found before.'); } })
      .catch(() => undefined);
    return () => { live = false; };
  }, [reload]);

  useEffect(() => {                                 // suggestions: from what's already read (no request)
    if (part !== 'suggested' || !state) return;
    (async () => {
      const cited = citedSummary(await loadCitedBy(), today()).people ?? [];
      const research = await readCache<{ rising?: any[] }>('research');
      setSugg(R.suggestions(cited, R.fieldPeople(research?.data?.rising ?? []), state.following.map((p) => p.id)));
    })().catch(() => undefined);
  }, [part, state]);

  const items = state && part === 'new' ? R.feed(state, today()).slice(0, 40) : [];
  useEffect(() => { if (items.length) R.markSeen(items.map((w) => w.id)).catch(() => undefined); }, [items.length]);   // eslint-disable-line react-hooks/exhaustive-deps -- once per list

  const follow = async (p: { id: string; name: string; institution?: string; country?: string; topics?: string[] }) => {
    const s = await R.follow(p);
    setState(s);
    setCands((c) => c.filter((x) => x.id !== p.id));
    setNote(`Following ${p.name}. Their new work appears in 🆕 New work.`);
    R.refresh().then((out) => setState(out.state)).catch(() => undefined);
  };
  const find = async () => {
    setNote('Looking…');
    const out = await R.search(query);
    setCands(out.candidates);
    setNote(out.candidates.length ? '' : out.why ?? (out.status === 'busy' ? 'OpenAlex is resting for now (its daily budget). Try again later.'
      : 'Nobody by that name. Try their full name as it appears on their papers.'));
  };

  if (!state) return <GeekLoader text="Reading the people you follow…" />;
  return (
    <View style={{ paddingBottom: 24 }}>
      {note ? <Text style={[st.muted, { color: C.amber }]}>{note}</Text> : null}

      {part === 'new' ? <>
        <Text style={st.muted}>New preprints and papers from the people you follow, as they appear: a preprint and its published version show as one.</Text>
        <View style={st.row}>
          <Text style={[st.muted, { flex: 1 }]}>Following {state.following.length} · updated {dayText((state.updated_at ?? '').slice(0, 10)) || 'never'}</Text>
          <Pressable style={st.btn} onPress={() => { setNote('Looking for new work…'); R.refresh(true).then((o) => { setState(o.state); setNote(o.busy ? 'OpenAlex is resting for now (its daily budget): this is what was found before.' : ''); }); }}>
            <Text style={st.btnText}>Refresh</Text>
          </Pressable>
        </View>
        {!state.following.length ? <Empty>You don&apos;t follow anyone yet: find people in 👥 Following, or start from ✨ Suggested.</Empty> : null}
        {items.map((w) => (
          <Pressable key={w.id} onPress={() => open(w.url)} style={({ pressed }) => [st.card, pressed && { opacity: 0.8 }]}>
            <Text style={st.title}>{w.new ? '🆕 ' : ''}{w.title}</Text>
            <Text style={st.muted}>{w.names.join(', ')}{w.authors > w.names.length ? ` and ${w.authors - w.names.length} more` : ''}</Text>
            <Text style={st.muted}>{w.preprint ? '📄 preprint · ' : ''}{w.venue}{w.venue ? ' · ' : ''}{dayText(w.date)}</Text>
            {w.preprint_of ? <Text style={[st.muted, { color: C.green }]}>now published · first as a preprint on {w.preprint_of.venue || 'a preprint server'}, {dayText(w.preprint_of.date)}</Text> : null}
          </Pressable>
        ))}
      </> : null}

      {part === 'following' ? <>
        <Text style={st.muted}>Follow anyone who publishes, by name. The list stays on this phone: nobody is told, and myGeeKy never contacts them.</Text>
        <View style={st.row}>
          <TextInput value={query} onChangeText={setQuery} onSubmitEditing={find} placeholder="First and last name" placeholderTextColor={C.muted}
                     style={st.input} autoCorrect={false} returnKeyType="search" />
          <Pressable style={[st.btn, { backgroundColor: C.violet }]} onPress={find}><Text style={st.btnText}>Find</Text></Pressable>
        </View>
        {cands.map((c) => (
          <View key={c.id} style={st.card}>
            <Text style={st.title}>{c.name}</Text>
            <Text style={st.muted}>{[c.institution, c.topics.join(', '), `${c.works} works`].filter(Boolean).join(' · ')}</Text>
            {c.titles.slice(0, 2).map((t) => <Text key={t} style={st.muted} numberOfLines={2}>· {t}</Text>)}
            <Pressable style={[st.btn, { alignSelf: 'flex-start', marginTop: 6, backgroundColor: C.violet }]} onPress={() => follow(c)}><Text style={st.btnText}>Follow</Text></Pressable>
          </View>
        ))}
        {state.following.length ? <Text style={st.head}>YOU FOLLOW ({state.following.length})</Text> : null}
        {state.following.map((p) => (
          <View key={p.id} style={st.card}>
            <View style={st.row}>
              <Text style={[st.title, { flex: 1 }]}>{p.name}</Text>
              <Pressable style={st.btn} onPress={() => R.unfollow(p.id).then(setState)}><Text style={st.btnText}>Unfollow</Text></Pressable>
            </View>
            <Text style={st.muted}>{[p.institution, rateText(p.rate || 0), p.checked ? `checked ${dayText(p.checked)}` : ''].filter(Boolean).join(' · ')}</Text>
          </View>
        ))}
      </> : null}

      {part === 'suggested' ? <>
        <Text style={st.muted}>People worth following, from what myGeeKy already read: who cites your work, and who leads the papers rising in your field.</Text>
        {!sugg.length ? <Empty>No suggestions yet. They come from You → Cited by and World → Papers.</Empty> : null}
        {sugg.map((p) => (
          <View key={p.id} style={st.card}>
            <Text style={st.title}>{p.name}</Text>
            <Text style={st.muted}>{[p.institution, p.why].filter(Boolean).join(' · ')}</Text>
            <Pressable style={[st.btn, { alignSelf: 'flex-start', marginTop: 6, backgroundColor: C.violet }]} onPress={() => follow(p)}><Text style={st.btnText}>Follow</Text></Pressable>
          </View>
        ))}
      </> : null}
    </View>
  );
}

const st = StyleSheet.create({
  muted: { color: C.muted, fontSize: 12, marginTop: 2 },
  head: { color: C.text, fontSize: 11.5, fontWeight: '800', letterSpacing: 0.6, marginTop: 14, marginBottom: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, marginVertical: 6 },
  card: { backgroundColor: C.card, borderRadius: 12, padding: 10, marginBottom: 6 },
  title: { color: C.text, fontSize: 14, fontWeight: '700', lineHeight: 19 },
  btn: { backgroundColor: C.cardHi, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  btnText: { color: C.text, fontSize: 12.5, fontWeight: '700' },
  input: { flex: 1, color: C.text, backgroundColor: C.card, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7, borderWidth: 1, borderColor: C.line },
});
