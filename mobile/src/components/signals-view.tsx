// The 📡 Signals planet: private thank-yous and collab invites between myGeeKy users,
// read and sent from the phone (same beacons and encryption as the desktop).
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Image, Linking, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { timeAgo, useApp } from '../lib/app-state';
import {
  GESTURES, inboxAndPeople, isSetUp, loadBeacons, type Parsed, type Person, type Received, send, setUp, turnOff,
} from '../lib/signals';
import { C } from '../lib/theme';
import { Card, Empty, open, Section } from './ui';

const TOKEN_PAGE = 'https://github.com/settings/personal-access-tokens/new';
const ORDER = ['thanks', 'learn', 'used', 'watching', 'collab'];
const LABEL: Record<string, string> = { thanks: 'Thanks', learn: 'Learned', used: 'Used it', watching: 'Following', collab: 'Collaborate' };

export function SignalsView() {
  const { settings, token } = useApp();
  const me = settings?.username ?? '';
  const [ready, setReady] = useState<boolean | null>(null);
  const [users, setUsers] = useState<Parsed[]>([]);
  const [inbox, setInbox] = useState<Received[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState('');
  const [picked, setPicked] = useState<string | null>(null);
  const [repo, setRepo] = useState('');
  const keywords = settings?.keywords;
  const topics = settings?.topics;

  const load = useCallback(async () => {
    if (!me) return;
    setLoading(true);
    setNote('');
    try {
      const found = await loadBeacons(me, token);
      const mine = [...(keywords ?? []), ...(topics ?? [])];
      const { inbox: got, people: who } = await inboxAndPeople(me, mine, found);
      setUsers(found);
      setInbox(got);
      setPeople(who);
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Couldn't reach GitHub. Pull down to try again.");
    } finally {
      setLoading(false);
    }
  }, [me, token, keywords, topics]);

  useEffect(() => {
    isSetUp().then((ok) => {
      setReady(ok);
      if (ok) load();
    });
  }, [load]);

  if (ready === null) return <ActivityIndicator color={C.pink} style={{ marginTop: 24 }} />;
  if (!ready) return <SetupCard me={me} onDone={() => { setReady(true); load(); }} />;

  const doSend = async (p: Person, gesture: string) => {
    const target = users.find((u) => u.owner === p.login);
    if (!target) return;
    setNote('Sending…');
    try {
      await send(me, target, gesture, gesture === 'used' ? repo.trim() : undefined);
      setNote(`${GESTURES[gesture][0]} sent to ${p.login}. ${gesture === 'collab'
        ? 'They only ever see it if they choose you too.' : 'No reply needed.'}`);
      setPicked(null);
      setRepo('');
      load();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "It didn't send. Try again.");
    }
  };

  return (
    <View>
      <View style={st.top}>
        <Text style={st.muted}>{loading ? 'Looking for signals…' : 'Private: only the person a signal is for can read it.'}</Text>
        <Pressable onPress={load} disabled={loading}><Text style={st.link}>Refresh</Text></Pressable>
      </View>
      {note ? <Text style={st.note}>{note}</Text> : null}

      <Section>FOR YOU</Section>
      {inbox.length ? inbox.map((g) => (
        <Card key={`${g.from}-${g.type}-${g.at}`} onPress={() => open(`https://github.com/${g.from}`, 'person')}>
          <View style={st.row}>
            <Image source={{ uri: `${g.avatar}${g.avatar.includes('?') ? '&' : '?'}s=88` }} style={st.avatar} />
            <View style={{ flex: 1 }}>
              <Text style={st.name}>{g.from}</Text>
              <Text style={[st.small, g.mutual && { color: C.green }]}>{g.text}</Text>
              <Text style={st.tiny}>{timeAgo(g.at)}{g.mutual ? '' : ' · no reply needed'}</Text>
            </View>
          </View>
        </Card>
      )) : <Empty>{loading ? 'Loading…' : 'Nothing yet. When someone sends you a signal, it shows here.'}</Empty>}

      <Section>ON SIGNALS</Section>
      {people.length ? people.map((p) => (
        <Card key={p.login} onPress={() => setPicked(picked === p.login ? null : p.login)}>
          <View style={st.row}>
            <Image source={{ uri: `${p.avatar}${p.avatar.includes('?') ? '&' : '?'}s=88` }} style={st.avatar} />
            <View style={{ flex: 1 }}>
              <Text style={st.name}>{p.login}{p.signalledYou ? '  ✦' : ''}</Text>
              <Text style={st.small} numberOfLines={2}>
                {[p.status, p.shared.length ? `shares: ${p.shared.slice(0, 4).join(', ')}` : ''].filter(Boolean).join(' · ') || 'on myGeeKy'}
              </Text>
            </View>
          </View>
          {picked === p.login ? (
            p.canReceive ? (
              <View style={st.gestures}>
                {ORDER.map((g) => (
                  <Pressable key={g} style={st.gesture} onPress={() => (g === 'used' && !repo.trim()
                    ? setNote('Type the repo you used (owner/name) below, then tap ⭐ again.') : doSend(p, g))}>
                    <Text style={st.gestureText}>{GESTURES[g][0]} {LABEL[g]}</Text>
                  </Pressable>
                ))}
                <TextInput style={st.input} value={repo} onChangeText={setRepo} autoCapitalize="none" autoCorrect={false}
                           placeholder={`for ⭐: ${p.login}/their-repo`} placeholderTextColor={C.muted} />
              </View>
            ) : <Text style={[st.small, { marginTop: 8 }]}>{p.status || "They can't receive private signals yet."}</Text>
          ) : null}
        </Card>
      )) : <Empty>{loading ? 'Loading…' : 'Nobody else on Signals found yet.'}</Empty>}

      <Pressable onPress={async () => { await turnOff(); setReady(false); }} style={{ marginTop: 18 }}>
        <Text style={[st.tiny, { textAlign: 'center' }]}>Turn off Signals on this phone</Text>
      </Pressable>
    </View>
  );
}

function SetupCard({ me, onDone }: { me: string; onDone: () => void }) {
  const [value, setValue] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    setNote('Checking the token and adding this phone to your beacon…');
    try {
      await setUp(me, value);
      onDone();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <Text style={st.title}>Signals on this phone</Text>
      <Text style={[st.small, { marginTop: 6 }]}>
        Private thank-yous and collab invites between myGeeKy users. This phone gets its own key (kept only here) and
        joins your beacon next to your computers, so signals sent to you open here too. Turn Signals on on your
        computer first.
      </Text>
      <Text style={[st.small, { marginTop: 10 }]}>
        1. Make a token just for this phone: tap below, name it “myGeeKy Signals – phone”, pick Only select
        repositories → {me || 'you'}/mygeeky-beacon, and under Permissions set Contents: Read and write.{'\n'}
        2. Copy it, paste it here, tap Turn on.
      </Text>
      <Pressable onPress={() => Linking.openURL(TOKEN_PAGE)} style={st.button}>
        <Text style={st.buttonText}>Make a Signals token on GitHub ↗</Text>
      </Pressable>
      <TextInput style={st.input} value={value} onChangeText={setValue} autoCapitalize="none" autoCorrect={false}
                 secureTextEntry placeholder="github_pat_…" placeholderTextColor={C.muted} />
      <Pressable onPress={go} disabled={busy || !value.trim()} style={[st.button, (busy || !value.trim()) && { opacity: 0.5 }]}>
        <Text style={st.buttonText}>{busy ? 'Turning on…' : 'Turn on Signals here'}</Text>
      </Pressable>
      {note ? <Text style={st.note}>{note}</Text> : null}
    </Card>
  );
}

const st = StyleSheet.create({
  top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: C.cardHi },
  name: { color: C.text, fontSize: 15, fontWeight: '700' },
  title: { color: C.text, fontSize: 16, fontWeight: '700' },
  small: { color: C.muted, fontSize: 13, lineHeight: 18 },
  tiny: { color: C.muted, fontSize: 11, marginTop: 2 },
  muted: { color: C.muted, fontSize: 12, flex: 1 },
  link: { color: C.cyan, fontSize: 13, fontWeight: '600' },
  note: { color: C.amber, fontSize: 13, marginVertical: 6 },
  gestures: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  gesture: { backgroundColor: C.cardHi, borderRadius: 14, paddingVertical: 7, paddingHorizontal: 11 },
  gestureText: { color: C.text, fontSize: 13 },
  input: { borderWidth: 1, borderColor: C.line, borderRadius: 10, color: C.text, paddingHorizontal: 10, paddingVertical: 8,
    marginTop: 10, alignSelf: 'stretch' },
  button: { backgroundColor: C.violet, borderRadius: 12, paddingVertical: 10, alignItems: 'center', marginTop: 10 },
  buttonText: { color: '#fff', fontWeight: '700' },
});
