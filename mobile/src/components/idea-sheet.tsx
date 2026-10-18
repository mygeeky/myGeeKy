// 💡 Ideas, a part of You: an idea, a problem or a question to myGeeKy's maker, as on the desktop (src/mygeeky/ideas.py and its
// dialog). It becomes a prefilled issue in the public ideas repo, or the same message as an email to support, ready
// in your own browser or mail app, and you send it yourself. Nothing is sent from here, and no token is involved.
// The links are built in lib/ideas.ts.
import Constants from 'expo-constants';
import { useState } from 'react';
import { Linking, Platform, Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { emailUrl, issueUrl, KINDS, SUPPORT_EMAIL } from '../lib/ideas';
import { C, tint } from '../lib/theme';

const versionInfo = () => `myGeeKy phone ${Constants.expoConfig?.version ?? ''} · ${Platform.OS} ${Platform.Version}`;

/** The 💡 form, as its own part of You (after Settings). */
export function IdeaForm() {
  const [kind, setKind] = useState('idea');
  const [title, setTitle] = useState('');
  const [details, setDetails] = useState('');
  const [withVersion, setWithVersion] = useState(true);
  const [opened, setOpened] = useState<'' | 'github' | 'email'>('');
  const [note, setNote] = useState('');
  const send = (how: 'github' | 'email') => {
    if (!title.trim()) return setNote('Give it a short title first.');
    const version = withVersion ? versionInfo() : null;
    Linking.openURL(how === 'github' ? issueUrl(kind, title, details, version) : emailUrl(kind, title, details, version));
    setTitle('');
    setDetails('');
    setNote('');
    setOpened(how);
  };
  return (
    <View style={{ paddingTop: 8 }}>
      <Text style={st.title}>Send an idea to myGeeKy</Text>
      <Text style={st.muted}>Ideas, problems and questions go to myGeeKy&apos;s maker as a GitHub issue. Your browser opens it
        ready to send. Tap Submit there, with your GitHub account. It&apos;s public, so don&apos;t include tokens or private data.</Text>
      <Text style={[st.muted, { marginTop: 4 }]}>No GitHub account, or rather private? Use ✉ Send by email: the same
        message, ready in your own mail app.</Text>
      <View style={st.kinds}>
        {KINDS.map(([k, emoji, label]) => (
          <Pressable key={k} onPress={() => setKind(k)} style={[st.kind, kind === k && st.kindOn]}
                     accessibilityRole="radio" accessibilityState={{ selected: kind === k }}>
            <Text style={[st.kindText, kind === k && { color: '#fff' }]}>{emoji} {label}</Text>
          </Pressable>
        ))}
      </View>
      <TextInput style={st.input} value={title} onChangeText={setTitle} placeholder="In a few words" placeholderTextColor={C.muted} />
      <TextInput style={[st.input, { minHeight: 110, textAlignVertical: 'top' }]} value={details} onChangeText={setDetails} multiline
                 placeholder="Details: what would help, or what happened and what you expected" placeholderTextColor={C.muted} />
      <View style={st.switchRow}>
        <Switch value={withVersion} onValueChange={setWithVersion} />
        <Text style={[st.muted, { flex: 1 }]}>Include version info (myGeeKy and your phone&apos;s system; helps with problems)</Text>
      </View>
      <View style={st.buttons}>
        <Pressable onPress={() => send('email')} style={st.btn} accessibilityHint={`Opens your mail app with this message to ${SUPPORT_EMAIL}`}>
          <Text style={[st.btnText, { color: C.text }]}>✉ Send by email</Text></Pressable>
        <Pressable onPress={() => send('github')} style={[st.btn, st.accent]}><Text style={st.btnText}>Open on GitHub ↗</Text></Pressable>
      </View>
      {note ? <Text style={[st.muted, { marginTop: 10, color: C.amber }]}>{note}</Text> : null}
      {opened === 'github' ? <Text style={[st.muted, { marginTop: 10 }]}>Opened in your browser: tap Submit there to send it. Thank you!</Text> : null}
      {opened === 'email' ? <Text style={[st.muted, { marginTop: 10 }]}>Opened in your mail app, addressed to {SUPPORT_EMAIL}: tap Send there. Thank you!</Text> : null}
    </View>
  );
}

const st = StyleSheet.create({
  title: { color: C.text, fontSize: 18, fontWeight: '800', marginBottom: 6 },
  muted: { color: C.muted, fontSize: 13, lineHeight: 18 },
  link: { color: C.cyan },
  kinds: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginVertical: 12 },
  kind: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 14, backgroundColor: tint(0.08), minHeight: 38, justifyContent: 'center' },
  kindOn: { backgroundColor: C.violet },
  kindText: { color: C.text, fontSize: 14, fontWeight: '600' },
  input: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 12, color: C.text, paddingHorizontal: 12,
    paddingVertical: 10, fontSize: 15, marginBottom: 10 },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  buttons: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10 },
  btn: { backgroundColor: tint(0.08), borderRadius: 12, paddingHorizontal: 16, paddingVertical: 11 },
  accent: { backgroundColor: C.violet },
  btnText: { color: '#fff', fontWeight: '800', fontSize: 14 },
});
