// "Is this you?": type your name and institution, see the researchers OpenAlex knows, pick yourself -- in setup and
// in You → Settings (the desktop's setup page and ⚙ → Your papers, gui/whois_ui.py). If OpenAlex is busy, you carry
// on without it and the search is kept and tried again later (lib/whois-store.ts).
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import type { Candidate } from '../lib/whois';
import { search } from '../lib/whois';
import { keepPending, loadWhois, saveWhois, type WhoisState } from '../lib/whois-store';
import { useApp } from '../lib/app-state';
import { C } from '../lib/theme';
import { GeekLoader } from './geek-loader';

export function CandidateList({ cands, onPick, onNone }: { cands: Candidate[]; onPick: (c: Candidate) => void; onNone: () => void }) {
  return (
    <View>
      <Text style={st.ask}>Is this you? Pick yourself (only you know):</Text>
      {cands.map((c) => (
        <Pressable key={c.id} onPress={() => onPick(c)} style={({ pressed }) => [st.cand, pressed && { opacity: 0.8 }]}>
          <Text style={st.name}>{c.name}</Text>
          <Text style={st.meta}>{[c.institution, c.country, `${c.works} works`].filter(Boolean).join(' · ')}</Text>
          {c.topics.length ? <Text style={st.meta}>Topics: {c.topics.join(', ')}</Text> : null}
          {c.titles.map((t) => <Text key={t} style={st.title}>• {t}</Text>)}
        </Pressable>
      ))}
      <Pressable onPress={onNone} hitSlop={8}><Text style={st.none}>None of these</Text></Pressable>
    </View>
  );
}

/** The search. onPick: you chose yourself; onNone: no match; onBusy: OpenAlex busy (kept as pending already). */
export function WhoisFind({ onPick, onNone, onBusy }: { onPick: (c: Candidate) => void; onNone: () => void; onBusy: () => void }) {
  const [name, setName] = useState('');
  const [hint, setHint] = useState('');
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [cands, setCands] = useState<Candidate[] | null>(null);

  const go = async () => {
    setNote('');
    setBusy(true);
    const out = await search(name.trim(), hint.trim());
    setBusy(false);
    if (out.status === 'busy') {
      await keepPending(name.trim(), hint.trim(), out.retry_after ?? 0);
      onBusy();
      return;
    }
    if (out.status === 'none') {
      setNote(out.why ?? 'No researcher by that name on OpenAlex. Check the spelling, or add your institution.');
      return;
    }
    setCands(out.candidates);
  };

  if (busy) return <GeekLoader text="Looking on OpenAlex…" size={60} />;
  if (cands) return <CandidateList cands={cands} onPick={onPick} onNone={() => { setCands(null); onNone(); }} />;
  return (
    <View>
      <Text style={st.hint}>Your name as on your papers, and your institution (or institutional email, or a co-author&apos;s name).</Text>
      <TextInput style={st.input} value={name} onChangeText={setName} placeholder="e.g. Ada Lovelace" placeholderTextColor={C.muted} />
      <TextInput style={st.input} value={hint} onChangeText={setHint} autoCapitalize="none" placeholder="e.g. Lund University, or you@lu.se"
                 placeholderTextColor={C.muted} />
      {note ? <Text style={st.note}>{note}</Text> : null}
      <Pressable onPress={go} disabled={name.trim().split(/\s+/).length < 2}
                 style={({ pressed }) => [st.btn, (pressed || name.trim().split(/\s+/).length < 2) && { opacity: 0.6 }]}>
        <Text style={st.btnText}>🔎  Search OpenAlex</Text>
      </Pressable>
    </View>
  );
}

/** You → Settings → 📄 Your papers: who you are on OpenAlex, or "Is this you?" candidates, or the search. */
export function WhoisSettings() {
  const { settings, save } = useApp();
  const [state, setState] = useState<WhoisState | null>(null);
  const [note, setNote] = useState('');
  useEffect(() => { loadWhois().then(setState).catch(() => setState({})); }, []);
  if (!settings || !state) return null;
  const pick = async (c: Candidate) => {
    await save({ ...settings, openalex: c.id });
    await saveWhois({ confirmed: c.id });
    setState({ confirmed: c.id });
    setNote(`✓ That's you: ${c.name}. Your papers will shape your profile.`);
  };
  const none = async () => { await saveWhois({ none: true }); setState({ none: true }); };
  if (settings.orcid) return <Text style={st.hint}>Found through your ORCID iD.</Text>;
  if (settings.openalex) {
    return (
      <View>
        <Text style={[st.hint, { color: C.green }]}>{note || `✓ Your OpenAlex author: ${settings.openalex}`}</Text>
        <Pressable onPress={async () => { await save({ ...settings, openalex: '' }); await saveWhois({}); setState({}); setNote(''); }} hitSlop={8}>
          <Text style={st.none}>Not me: forget it</Text>
        </Pressable>
      </View>
    );
  }
  if (state.found?.length) return <CandidateList cands={state.found} onPick={pick} onNone={none} />;
  return (
    <View>
      {state.pending ? <Text style={st.hint}>Looking for “{state.pending.name}”: OpenAlex was busy, myGeeKy tries again by itself and asks here.</Text>
        : <Text style={st.hint}>No ORCID? Find your papers by your name and institution.</Text>}
      {note ? <Text style={st.note}>{note}</Text> : null}
      <WhoisFind onPick={pick} onNone={() => setNote('No match. Check the spelling, or try another institution.')}
                 onBusy={() => { loadWhois().then(setState); setNote('OpenAlex is busy: myGeeKy will try again later by itself.'); }} />
    </View>
  );
}

const st = StyleSheet.create({
  hint: { color: C.muted, fontSize: 13, lineHeight: 18, marginBottom: 4 },
  input: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 12, color: C.text, paddingHorizontal: 14,
    paddingVertical: 12, fontSize: 16, marginTop: 8 },
  note: { color: C.amber, fontSize: 13, marginTop: 8, lineHeight: 18 },
  btn: { backgroundColor: '#4a92dd', borderRadius: 12, paddingVertical: 12, alignItems: 'center', marginTop: 10 },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '800' },
  ask: { color: C.text, fontSize: 14, fontWeight: '800', marginVertical: 6 },
  cand: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 14, padding: 12, marginTop: 8 },
  name: { color: C.text, fontSize: 15.5, fontWeight: '800' },
  meta: { color: C.muted, fontSize: 12.5, marginTop: 3 },
  title: { color: C.text, fontSize: 12.5, marginTop: 3 },
  none: { color: C.violet, fontSize: 14, fontWeight: '700', marginTop: 12, textAlign: 'center' },
});
