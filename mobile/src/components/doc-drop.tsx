// Drop a CV, thesis or abstract: pick a file (PDF, Word, text) or paste the text, see what myGeeKy found -- your
// field's keywords, your methods and tools, your co-authors -- untick what's wrong, and keep the rest. In setup and
// in More → Settings (the desktop's setup page and ⚙ → From a document, gui/docread_ui.py). Read on this phone:
// the file isn't sent anywhere or kept (lib/doc-text.ts, lib/doc-read.ts).
import { useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useApp } from '../lib/app-state';
import { readDocument, mergeWords, type Found } from '../lib/doc-read';
import { documentText, MAX_BYTES } from '../lib/doc-text';
import { C } from '../lib/theme';
import { GeekLoader } from './geek-loader';

export type Kept = { keywords: string[]; methods: string[]; coauthors: string[] };

const OLD_APP = 'Choosing a file needs the newest version of the app. Paste the text instead.';

async function pickFile(): Promise<{ text: string; ok: boolean; why?: string } | null> {
  // loaded only when asked for: an app built before these add-ons existed still opens, and says so here
  let DocumentPicker: typeof import('expo-document-picker'), File: typeof import('expo-file-system').File;
  try {
    DocumentPicker = await import('expo-document-picker');
    File = (await import('expo-file-system')).File;
  } catch {
    return { text: '', ok: false, why: OLD_APP };
  }
  const r = await DocumentPicker.getDocumentAsync({ type: '*/*', copyToCacheDirectory: true, multiple: false });
  if (r.canceled || !r.assets?.length) return null;
  const a = r.assets[0];
  if (a.size && a.size > MAX_BYTES) return { text: '', ok: false, why: 'That file is too big (over 15 MB). Paste the text instead.' };
  let bytes: Uint8Array;
  if (Platform.OS === 'web' && a.file) bytes = new Uint8Array(await a.file.arrayBuffer());
  else {
    const f = new File(a.uri);
    bytes = await f.bytes();
    try { f.delete(); } catch { /* the picker's copy in the cache: gone either way when the cache is cleared */ }
  }
  await new Promise((done) => setTimeout(done, 30));      // let the loader show before the reading starts
  return documentText(bytes, a.name);
}

function Chips({ title, items, off, toggle }: { title: string; items: string[]; off: Set<string>; toggle: (w: string) => void }) {
  if (!items.length) return null;
  return (
    <View style={{ marginTop: 10 }}>
      <Text style={st.group}>{title}</Text>
      <View style={st.chips}>
        {items.map((w) => (
          <Pressable key={w} onPress={() => toggle(w)} hitSlop={4} accessibilityRole="checkbox"
                     accessibilityState={{ checked: !off.has(w) }}
                     style={({ pressed }) => [st.chip, off.has(w) && st.chipOff, pressed && { opacity: 0.7 }]}>
            <Text style={[st.chipText, off.has(w) && st.chipTextOff]}>{off.has(w) ? '+ ' : '✓ '}{w}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

/** Pick or paste → what was found → keep. `ownName` (when known) is left out of the co-authors. */
export function DocDrop({ ownName = '', onKeep, keepLabel = 'Keep these' }:
  { ownName?: string; onKeep: (k: Kept) => void; keepLabel?: string }) {
  const [paste, setPaste] = useState('');
  const [pasting, setPasting] = useState(false);
  const [reading, setReading] = useState(false);
  const [note, setNote] = useState('');
  const [found, setFound] = useState<Found | null>(null);
  const [off, setOff] = useState<Set<string>>(new Set());

  const show = (text: string) => {
    const f = readDocument(text, ownName);
    if (!f.keywords.length && !f.methods.length && !f.coauthors.length) {
      setNote('Nothing from the dictionary turned up in it. Try your CV or an abstract, or type a few keywords.');
      return;
    }
    setOff(new Set());
    setFound(f);
  };
  const pick = async () => {
    setNote('');
    setReading(true);
    try {
      const got = await pickFile();
      if (!got) return;
      if (!got.ok) { setNote(got.why ?? 'This file couldn\'t be read. Paste the text instead.'); setPasting(true); return; }
      show(got.text);
    } catch {
      setNote('This file couldn\'t be opened. Paste the text instead.');
      setPasting(true);
    } finally {
      setReading(false);
    }
  };
  const toggle = (w: string) => setOff((s) => { const n = new Set(s); if (n.has(w)) n.delete(w); else n.add(w); return n; });

  if (reading) return <GeekLoader text="Reading it on this phone…" size={60} />;
  if (found) {
    const keep = (xs: string[]) => xs.filter((w) => !off.has(w));
    const n = keep(found.keywords).length + keep(found.methods).length + keep(found.coauthors).length;
    return (
      <View>
        <Text style={st.ask}>Here&apos;s what I found. Untick anything that isn&apos;t you:</Text>
        <Chips title="🔬 YOUR FIELD" items={found.keywords} off={off} toggle={toggle} />
        <Chips title="🛠 METHODS AND TOOLS" items={found.methods} off={off} toggle={toggle} />
        <Chips title="👥 PEOPLE YOU'VE WRITTEN WITH" items={found.coauthors} off={off} toggle={toggle} />
        <Pressable onPress={() => {
          onKeep({ keywords: keep(found.keywords), methods: keep(found.methods), coauthors: keep(found.coauthors) });
          setFound(null); setPaste(''); setPasting(false);           // done: back to the start, for another one
        }}
                   disabled={!n} style={({ pressed }) => [st.btn, (pressed || !n) && { opacity: 0.6 }]}>
          <Text style={st.btnText}>{keepLabel} ({n})</Text>
        </Pressable>
        <Pressable onPress={() => { setFound(null); setPaste(''); }} hitSlop={8}><Text style={st.link}>Read another</Text></Pressable>
      </View>
    );
  }
  return (
    <View>
      <Text style={st.hint}>Your CV, thesis, proposal or an abstract. myGeeKy picks out your field, your methods and the
        people you&apos;ve written with, and you choose what to keep. It&apos;s read on this phone: the file isn&apos;t sent
        anywhere or kept.</Text>
      <Pressable onPress={pick} style={({ pressed }) => [st.btn, pressed && { opacity: 0.85 }]} accessibilityLabel="Choose a file">
        <Text style={st.btnText}>📄  Choose a file (PDF, Word, text)</Text>
      </Pressable>
      <Pressable onPress={() => setPasting(!pasting)} hitSlop={8}>
        <Text style={st.link}>{pasting ? '▾' : '▸'}  Or paste the text</Text>
      </Pressable>
      {pasting ? <>
        <TextInput style={st.paste} value={paste} onChangeText={setPaste} multiline textAlignVertical="top"
                   placeholder="Paste your abstract, proposal or CV here" placeholderTextColor={C.muted} />
        <Pressable onPress={() => { setNote(''); show(paste); }} disabled={paste.trim().length < 40}
                   style={({ pressed }) => [st.btnSoft, (pressed || paste.trim().length < 40) && { opacity: 0.6 }]}>
          <Text style={st.btnSoftText}>Read it</Text>
        </Pressable>
      </> : null}
      {note ? <Text style={st.note}>{note}</Text> : null}
    </View>
  );
}

/** More → Settings: add what a document says to your profile, and see the co-authors you kept. */
export function DocSettings() {
  const { settings, save } = useApp();
  const [done, setDone] = useState('');
  if (!settings) return null;
  const people = settings.coauthors ?? [];
  return (
    <View>
      {people.length ? <Text style={st.hint}>👥 People you&apos;ve written with: {people.join(', ')}</Text> : null}
      {done ? <Text style={[st.hint, { color: C.green }]}>{done}</Text> : null}
      <DocDrop keepLabel="Add to my profile" onKeep={async (k) => {
        const keywords = mergeWords(settings.keywords, [...k.keywords, ...k.methods]);
        await save({ ...settings, keywords, coauthors: mergeWords(people, k.coauthors) });
        setDone(`✓ Added ${keywords.length - settings.keywords.length} words to your profile${k.coauthors.length
          ? ` and ${k.coauthors.length} co-authors` : ''}.`);
      }} />
    </View>
  );
}

const st = StyleSheet.create({
  hint: { color: C.muted, fontSize: 13, lineHeight: 18, marginBottom: 4 },
  ask: { color: C.text, fontSize: 14, fontWeight: '800', marginTop: 4 },
  group: { color: C.muted, fontSize: 11.5, fontWeight: '800', letterSpacing: 0.5 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 6 },
  chip: { backgroundColor: 'rgba(139,108,255,0.18)', borderColor: C.violet, borderWidth: 1, borderRadius: 999,
    paddingHorizontal: 12, paddingVertical: 7 },
  chipOff: { backgroundColor: C.card, borderColor: C.line },
  chipText: { color: C.text, fontSize: 14 },
  chipTextOff: { color: C.muted },
  btn: { backgroundColor: '#8b6cff', borderRadius: 12, paddingVertical: 12, alignItems: 'center', marginTop: 12 },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '800' },
  btnSoft: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 12, paddingVertical: 10,
    alignItems: 'center', marginTop: 8 },
  btnSoftText: { color: C.text, fontSize: 15, fontWeight: '700' },
  link: { color: C.violet, fontSize: 14, fontWeight: '700', marginTop: 12, textAlign: 'center' },
  paste: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 12, color: C.text, padding: 12,
    fontSize: 14, minHeight: 140, marginTop: 8 },
  note: { color: C.amber, fontSize: 13, marginTop: 10, lineHeight: 18 },
});
