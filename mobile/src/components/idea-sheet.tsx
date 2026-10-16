// 💡 Ideas, a part of You: an idea, a problem or a question to myGeeKy's maker, as on the desktop (src/mygeeky/ideas.py and its
// dialog). It becomes a prefilled issue in the public ideas repo: the phone's browser opens it ready to send,
// and you press Submit with your own GitHub account. Nothing is sent from here, and no token is involved.
import Constants from 'expo-constants';
import { useState } from 'react';
import { Linking, Platform, Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { C, tint } from '../lib/theme';

const IDEAS_REPO = 'mygeeky/myGeeKy-ideas';
const MAX_URL = 7000;          // browsers and GitHub cope with ~8k; stay well under
// ideas.KINDS, without report and protocol (those are sent from the listing or protocol itself)
const KINDS: [string, string, string, string][] = [
  ['idea', '💡', 'Idea', 'idea'], ['problem', '🐞', 'Problem', 'problem'], ['question', '❓', 'Question', 'question'],
  ['keyword', '🔤', 'Keyword', 'keyword'], ['score', '🏆', 'Quiz score', 'leaderboard'],
];

const versionInfo = () => `myGeeKy phone ${Constants.expoConfig?.version ?? ''} · ${Platform.OS} ${Platform.Version}`;

/** ideas.issue_url: the prefilled new-issue page for this idea. */
export function issueUrl(kind: string, title: string, details: string, includeVersion: boolean): string {
  const [, emoji, label, ghLabel] = KINDS.find((k) => k[0] === kind) ?? KINDS[0];
  const t = title.split(/\s+/).filter(Boolean).join(' ').slice(0, 120) || label;
  let body = details.trim();
  if (kind === 'problem' && !body) body = 'What happened, and what did you expect?\n';
  body += includeVersion ? `\n\n---\n<sub>Sent from the 💡 in myGeeKy · ${versionInfo()}</sub>` : '\n\n---\n<sub>Sent from the 💡 in myGeeKy</sub>';
  const make = (b: string) => `https://github.com/${IDEAS_REPO}/issues/new?${new URLSearchParams({ title: `${emoji} ${t}`, body: b, labels: ghLabel })}`;
  let url = make(body);
  while (url.length > MAX_URL && body.length > 200) {     // a very long text: trim, never drop the title
    body = `${body.slice(0, Math.floor(body.length * 0.8))}\n\n(trimmed: please add the rest after opening)`;
    url = make(body);
  }
  return url;
}

/** The 💡 form, as its own part of You (after Settings). */
export function IdeaForm() {
  const [kind, setKind] = useState('idea');
  const [title, setTitle] = useState('');
  const [details, setDetails] = useState('');
  const [withVersion, setWithVersion] = useState(true);
  const [opened, setOpened] = useState(false);
  const send = () => {
    Linking.openURL(issueUrl(kind, title, details, withVersion));
    setTitle('');
    setDetails('');
    setOpened(true);
  };
  return (
    <View style={{ paddingTop: 8 }}>
      <Text style={st.title}>Send an idea to myGeeKy</Text>
      <Text style={st.muted}>Ideas, problems and questions go to myGeeKy&apos;s maker as a GitHub issue. Your browser opens it
        ready to send. Tap Submit there, with your GitHub account. It&apos;s public, so don&apos;t include tokens or private data.</Text>
      <Text style={[st.muted, { marginTop: 4 }]}>No GitHub account, or rather private?{' '}
        <Text style={st.link} onPress={() => Linking.openURL('mailto:support@mygeeky.org')}>support@mygeeky.org</Text></Text>
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
        <Pressable onPress={send} style={[st.btn, st.accent]}><Text style={st.btnText}>Open on GitHub ↗</Text></Pressable>
      </View>
      {opened ? <Text style={[st.muted, { marginTop: 10 }]}>Opened in your browser: tap Submit there to send it. Thank you!</Text> : null}
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
