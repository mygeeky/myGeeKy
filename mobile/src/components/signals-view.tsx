// The 📡 Signals planet: private thank-yous between myGeeKy users, and calls for contributors
// (invite people whose skills fit to help with one of your repos). The same beacons, matching
// and encryption as the desktop; "Your field" folds into a thin ruler and opens into a radar.
import AsyncStorage from '@react-native-async-storage/async-storage';
import Ionicons from '@expo/vector-icons/Ionicons';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Image, Linking, Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { quickProfile, timeAgo, useApp } from '../lib/app-state';
import {
  blockPerson, type CallForMe, closeCall, createCall, GESTURES, hideCall, isSetUp, joinCall, leaveCall, loadBeacons,
  loadMyCalls, type MyCall, type Parsed, type Person, reportUrl, send, setUp, type SignalsData, signalsData, turnOff,
  readQuiet, setQuiet as setQuietOn, unblockPerson,
} from '../lib/signals';
import { C } from '../lib/theme';
import { type Dot, FieldMap } from './field-map';
import { type CallInput, InviteSheet, SendSheet } from './signals-sheets';
import { Card, Empty, open, Section } from './ui';
import { TokenGuide } from './token-guide';


const TOKEN_PAGE = 'https://github.com/settings/personal-access-tokens/new';
const RADAR_KEY = 'mygeeky.signals.radar';
const QUICK = ['thanks', 'learn', 'watching', 'collab'];
const EMPTY: SignalsData = { inbox: [], people: [], calls: [], myCalls: [], blocked: [] };

export function SignalsView() {
  const { settings, token, profile, save } = useApp();
  const me = settings?.username ?? '';
  const [ready, setReady] = useState<boolean | null>(null);
  const [users, setUsers] = useState<Parsed[]>([]);
  const [data, setData] = useState<SignalsData>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState('');
  const [unfolded, setUnfolded] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [sheet, setSheet] = useState<null | { kind: 'invite' } | { kind: 'send'; to?: string; gesture?: string }>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [quiet, setQuiet] = useState(false);
  const weights = useMemo(() => profile?.weights ?? (settings ? quickProfile(settings).weights : {}), [profile, settings]);
  const share = settings?.exploreShare ?? 0.2;

  const load = useCallback(async () => {
    if (!me) return;
    setLoading(true);
    setNote('');
    try {
      const [found, mine, q] = await Promise.all([loadBeacons(me, token), loadMyCalls(me, token), readQuiet(me)]);
      setUsers(found);
      setQuiet(q);
      setData(await signalsData(me, weights, found, mine, share));
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Couldn't reach GitHub. Try Refresh.");
    } finally {
      setLoading(false);
    }
  }, [me, token, weights, share]);

  useEffect(() => {
    AsyncStorage.getItem(RADAR_KEY).then((v) => setUnfolded(v === '1')).catch(() => undefined);
    isSetUp().then((ok) => {
      setReady(ok);
      if (ok) load();
    });
  }, [load]);

  if (ready === null) return <ActivityIndicator color={C.pink} style={{ marginTop: 24 }} />;
  if (!ready) return <SetupCard me={me} onDone={() => { setReady(true); load(); }} />;

  const fold = (v: boolean) => {
    setUnfolded(v);
    AsyncStorage.setItem(RADAR_KEY, v ? '1' : '').catch(() => undefined);
  };
  const run = async (key: string, fn: () => Promise<void>, ok: string) => {
    setBusy(key);
    setNote('');
    try {
      await fn();
      setNote(ok);
      await load();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "That didn't work. Try again.");
    } finally {
      setBusy(null);
    }
  };
  const ownerOf = (login: string) => users.find((u) => u.owner === login);
  const join = (c: CallForMe) => run(`join:${c.owner}/${c.id}`, async () => {
    const owner = ownerOf(c.owner);
    if (!owner) throw new Error('Refresh and try again.');
    await joinCall(me, owner, c.id, c.matched);
    if (settings) {      // your suggestions lean a little toward this area, as they do on the computer
      const interests = { ...settings.interests };
      for (const s of c.skills) interests[s] = Math.max(interests[s] ?? 0, 0.8);
      await save({ ...settings, interests });
    }
  }, `🙋 Sent privately to ${c.owner}, with the skills that matched.`);
  const leave = (c: CallForMe) => run(`join:${c.owner}/${c.id}`, () => leaveCall(me, c.owner, c.id), 'Taken back.');
  const hide = async (c: CallForMe) => {
    await hideCall(c.owner, c.id);
    setData((d) => ({ ...d, calls: d.calls.filter((x) => !(x.owner === c.owner && x.id === c.id)) }));
  };
  // Block or report: offered on everything someone else put here (a signal, a call, a person)
  const flag = (login: string) => Alert.alert(login, 'Block them on this phone, or report them to GitHub, where their beacon lives.', [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Report to GitHub', onPress: () => { Linking.openURL(reportUrl(login)).catch(() => undefined); } },
    { text: `Block ${login}`, style: 'destructive', onPress: async () => {
      await blockPerson(login);
      setPicked(null);
      await load();
      setNote(`Blocked ${login}: their signals and calls won't show on this phone.`);
    } },
  ]);
  const unblock = async (login: string) => {
    await unblockPerson(login);
    await load();
    setNote(`Unblocked ${login}.`);
  };
  const close = (c: MyCall, filled: boolean) => run(`mine:${c.id}`, () => closeCall(me, c.id, filled),
    filled ? 'Marked as filled. It stops showing to others.' : 'Closed. It left your beacon.');
  const publishCall = async (input: CallInput) => {
    await createCall(me, input);
    load();
  };
  const sendSignal = async (to: string, gesture: string, repo?: string) => {
    const target = ownerOf(to);
    if (!target) throw new Error('Refresh and try again.');
    await send(me, target, gesture, repo);
    load();
  };

  const dots: Dot[] = [
    ...data.calls.map((c) => ({ id: `c:${c.owner}/${c.id}`, login: c.owner, label: c.fullName, fit: c.fit, call: true })),
    ...data.people.map((p) => ({ id: `p:${p.login}`, login: p.login, label: p.login, fit: p.fit, call: false })),
  ];
  const pickedCall = data.calls.find((c) => `c:${c.owner}/${c.id}` === picked);
  const pickedPerson = data.people.find((p) => `p:${p.login}` === picked);
  const callCard = (c: CallForMe) => (
    <CallCardView key={`${c.owner}/${c.id}`} c={c} busy={busy === `join:${c.owner}/${c.id}`}
                  onJoin={() => join(c)} onLeave={() => leave(c)} onHide={() => hide(c)} onFlag={() => flag(c.owner)} />
  );
  const personCard = (p: Person) => (
    <PersonCard key={p.login} p={p} onGesture={(g) => setSheet({ kind: 'send', to: p.login, gesture: g })}
                onFlag={() => flag(p.login)} />
  );

  return (
    <View>
      <View style={st.top}>
        <Text style={st.muted}>{loading ? 'Looking for signals…' : '🔒 Private: only the person a signal is for can read it.'}</Text>
        <Pressable onPress={load} disabled={loading}><Text style={st.link}>Refresh</Text></Pressable>
      </View>
      {note ? <Text style={st.note}>{note}</Text> : null}

      <View style={st.field}>
        <View style={st.fieldHead}>
          <Text style={st.fieldTitle}>📡 Your field <Text style={st.muted}>· {data.people.length} {data.people.length === 1 ? 'person' : 'people'} · {data.calls.length} calling</Text></Text>
          <Pressable onPress={() => fold(!unfolded)} style={st.toggle} accessibilityLabel={unfolded ? 'Fold the radar' : 'Open the radar'}>
            <Ionicons name={unfolded ? 'chevron-up' : 'chevron-down'} size={14} color={C.cyan} />
          </Pressable>
        </View>
        <FieldMap dots={dots} selected={picked} unfolded={unfolded} onPick={setPicked} />
        {pickedCall ? callCard(pickedCall) : pickedPerson ? personCard(pickedPerson) : null}
        <View style={st.acts}>
          <Pressable onPress={() => setSheet({ kind: 'invite' })} style={[st.act, st.actInvite]}>
            <Ionicons name="person-add-outline" size={15} color="#fff" />
            <Text style={st.actText}>Invite to a project</Text>
          </Pressable>
          <Pressable onPress={() => setSheet({ kind: 'send' })} style={st.act}>
            <Ionicons name="paper-plane-outline" size={14} color={C.text} />
            <Text style={st.actText}>Send a signal</Text>
          </Pressable>
        </View>
      </View>

      <View style={st.quietRow}>
        <View style={{ flex: 1 }}>
          <Text style={st.quietTitle}>🔕 Not taking signals right now</Text>
          <Text style={st.quietSub}>{quiet ? 'On: nobody can send you a signal. The ones that came are kept for later.'
            : 'Turn on when you need a break. It applies on your computers too.'}</Text>
        </View>
        <Switch value={quiet} disabled={busy === 'quiet'} accessibilityLabel="Not taking signals right now"
                onValueChange={(v) => run('quiet', async () => { await setQuietOn(me, v); setQuiet(v); },
                  v ? 'Quiet: nobody can send you signals until you turn this off.' : 'Taking signals again.')} />
      </View>

      <Section>FOR YOU {!quiet && data.inbox.length ? data.inbox.length : ''}</Section>
      {quiet ? (
        <Empty>{data.inbox.length ? `${data.inbox.length} waiting: turn quiet off to see them.` : 'Nothing waiting.'}</Empty>
      ) : data.inbox.length ? data.inbox.map((g) => (
        <Card key={`${g.from}-${g.type}-${g.at}`} onPress={() => open(`https://github.com/${g.from}`, 'person')}>
          <View style={st.row}>
            <Image source={{ uri: `${g.avatar}${g.avatar.includes('?') ? '&' : '?'}s=88` }} style={st.avatar} />
            <View style={{ flex: 1 }}>
              <Text style={st.name}>{g.from}{g.type === 'join' ? <Text style={st.mine}>  your call</Text> : null}</Text>
              <Text style={[st.small, g.mutual && { color: C.green }]}>{g.text}</Text>
              {g.type === 'join' && g.skills?.length ? <Text style={[st.small, { color: C.green }]}>✓ {g.skills.join('  ✓ ')}</Text> : null}
              <Text style={st.tiny}>{timeAgo(g.at)}{g.mutual || g.type === 'join' ? '' : ' · no reply needed'}</Text>
            </View>
            <FlagButton login={g.from} onPress={() => flag(g.from)} />
          </View>
        </Card>
      )) : <Empty>{loading ? 'Loading…' : 'Nothing yet. When someone sends you a signal, it shows here.'}</Empty>}

      <Section>PROJECTS CALLING FOR YOU {data.calls.length ? data.calls.length : ''}</Section>
      {data.calls.length ? data.calls.map(callCard)
        : <Empty>{loading ? 'Loading…' : 'No calls fit your work right now. When someone invites contributors with your skills, it shows here.'}</Empty>}

      <Section>YOUR CALLS {data.myCalls.length ? data.myCalls.length : ''}</Section>
      {data.myCalls.map((c) => <MyCallView key={c.id} c={c} busy={busy === `mine:${c.id}`} onClose={(f) => close(c, f)} />)}
      {!data.myCalls.length ? <Empty>{"Invite people whose skills fit to help with one of your repos: they say they're in, privately."}</Empty> : null}

      <Section>PEOPLE ON SIGNALS {data.people.length ? data.people.length : ''}</Section>
      {data.people.length ? data.people.map(personCard) : <Empty>{loading ? 'Loading…' : 'Nobody else on Signals found yet.'}</Empty>}

      {data.blocked.length ? (
        <>
          <Section>BLOCKED {data.blocked.length}</Section>
          {data.blocked.map((login) => (
            <Card key={login}>
              <View style={st.row}>
                <Text style={[st.name, { flex: 1 }]}>{login}</Text>
                <Btn label="Unblock" onPress={() => unblock(login)} />
              </View>
            </Card>
          ))}
        </>
      ) : null}

      <Pressable onPress={async () => { await turnOff(); setReady(false); }} style={{ marginTop: 18 }}>
        <Text style={[st.tiny, { textAlign: 'center' }]}>Turn off Signals on this phone</Text>
      </Pressable>

      {sheet?.kind === 'invite' ? (
        <InviteSheet me={me} token={token} openCalls={data.myCalls.filter((c) => !c.filled).length}
                     onClose={() => setSheet(null)} onPublish={publishCall} />
      ) : null}
      {sheet?.kind === 'send' ? (
        <SendSheet people={data.people} token={token} to={sheet.to} gesture={sheet.gesture}
                   onClose={() => setSheet(null)} onSend={sendSignal} />
      ) : null}
    </View>
  );
}

function FlagButton({ login, onPress }: { login: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} hitSlop={10} accessibilityLabel={`Block or report ${login}`}>
      <Ionicons name="flag-outline" size={15} color={C.muted} />
    </Pressable>
  );
}

function CallCardView({ c, busy, onJoin, onLeave, onHide, onFlag }: {
  c: CallForMe; busy: boolean; onJoin: () => void; onLeave: () => void; onHide: () => void; onFlag: () => void;
}) {
  return (
    <Card>
      <View style={st.row}>
        <Image source={{ uri: `${c.avatar}${c.avatar.includes('?') ? '&' : '?'}s=64` }} style={st.avatarSm} />
        <View style={{ flex: 1 }}>
          <Text style={st.repo} numberOfLines={1}>{c.fullName}</Text>
          <Text style={st.tiny}>{c.levelLabel} · {c.timeLabel} · {c.daysLeft} days left</Text>
        </View>
        <Text style={st.fit}>{Math.round(c.fit * 100)}%</Text>
        <FlagButton login={c.owner} onPress={onFlag} />
      </View>
      <Text style={st.body}>{c.note}</Text>
      <Text style={st.small}>{c.skills.map((s) => (c.matched.includes(s) ? `✓ ${s}` : s)).join('  ·  ')}</Text>
      <Text style={[st.tag, c.explore && { color: '#c4b5fd' }]}>{c.explore ? '🔭 new territory: outside your usual work' : 'fits your work'}</Text>
      {c.joined ? (
        <>
          <Text style={[st.small, { color: C.green }]}>✓ Sent privately to {c.owner}{c.matched.length ? `, with: ${c.matched.join(', ')}` : ''}.</Text>
          <View style={st.btns}><Btn label="Changed my mind" onPress={onLeave} disabled={busy} /></View>
        </>
      ) : (
        <View style={st.btns}>
          <Btn label={busy ? 'Sending…' : "🙋 I'm in"} onPress={onJoin} disabled={busy} accent />
          <Btn label="See the repo" onPress={() => Linking.openURL(`https://github.com/${c.fullName}`)} />
          <Btn label="Not for me" onPress={onHide} />
        </View>
      )}
    </Card>
  );
}

function MyCallView({ c, busy, onClose }: { c: MyCall; busy: boolean; onClose: (filled: boolean) => void }) {
  return (
    <Card>
      <View style={st.row}>
        <Text style={[st.repo, { flex: 1 }]} numberOfLines={1}>{c.fullName}</Text>
        <Text style={st.mine}>{c.filled ? 'filled' : `${c.responders.length} in`}</Text>
      </View>
      <Text style={st.tiny}>{c.levelLabel} · {c.timeLabel} · {c.daysLeft} days left</Text>
      <Text style={st.body}>{c.note}</Text>
      <Text style={st.small}>{c.skills.join(' · ')}</Text>
      <Text style={st.label}>{"WHO'S IN"}</Text>
      {c.responders.length ? c.responders.map((r) => (
        <Pressable key={r.login} onPress={() => open(`https://github.com/${r.login}`, 'person')} style={[st.row, { marginTop: 4 }]}>
          <Image source={{ uri: `${r.avatar}${r.avatar.includes('?') ? '&' : '?'}s=64` }} style={st.avatarSm} />
          <View style={{ flex: 1 }}>
            <Text style={st.name}>{r.login}</Text>
            {r.skills.length ? <Text style={[st.small, { color: C.green }]}>✓ {r.skills.join('  ✓ ')}</Text> : null}
          </View>
        </Pressable>
      )) : <Text style={st.small}>{"Nobody yet. It's shown to people whose skills fit; you'll see who says yes."}</Text>}
      <View style={st.btns}>
        {!c.filled ? <Btn label="Mark as filled" onPress={() => onClose(true)} disabled={busy} /> : null}
        <Btn label="Close the call" onPress={() => onClose(false)} disabled={busy} />
      </View>
    </Card>
  );
}

function PersonCard({ p, onGesture, onFlag }: { p: Person; onGesture: (g: string) => void; onFlag: () => void }) {
  return (
    <Card>
      <View style={st.row}>
        <Image source={{ uri: `${p.avatar}${p.avatar.includes('?') ? '&' : '?'}s=88` }} style={st.avatar} />
        <View style={{ flex: 1 }}>
          <Text style={st.name}>{p.login}{p.signalledYou ? '  ✦' : ''}</Text>
          <Text style={st.small} numberOfLines={2}>
            {[p.status, p.shared.length ? `shares: ${p.shared.slice(0, 4).join(', ')}` : ''].filter(Boolean).join(' · ') || 'on myGeeKy'}
          </Text>
        </View>
        <Pressable onPress={() => open(`https://github.com/${p.login}`, 'person')} hitSlop={8}>
          <Ionicons name="open-outline" size={16} color={C.muted} />
        </Pressable>
        <FlagButton login={p.login} onPress={onFlag} />
      </View>
      {p.canReceive ? (
        <View style={st.btns}>
          {QUICK.map((g) => <Btn key={g} label={GESTURES[g][0]} onPress={() => onGesture(g)} />)}
        </View>
      ) : <Text style={[st.small, { marginTop: 6 }]}>{p.status || "They can't receive private signals yet."}</Text>}
    </Card>
  );
}

function Btn({ label, onPress, disabled, accent }: { label: string; onPress: () => void; disabled?: boolean; accent?: boolean }) {
  return (
    <Pressable onPress={onPress} disabled={disabled} style={[st.btn, accent && st.btnAccent, disabled && { opacity: 0.5 }]}>
      <Text style={[st.btnText, accent && { color: '#fff' }]}>{label}</Text>
    </Pressable>
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
      <TokenGuide which="signals" />
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
  quietRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 14, padding: 12, borderRadius: 14, backgroundColor: C.card },
  quietTitle: { color: C.text, fontSize: 14, fontWeight: '700' },
  quietSub: { color: C.muted, fontSize: 12, marginTop: 2, lineHeight: 16 },
  top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, gap: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: C.cardHi },
  avatarSm: { width: 28, height: 28, borderRadius: 14, backgroundColor: C.cardHi },
  name: { color: C.text, fontSize: 15, fontWeight: '700' },
  title: { color: C.text, fontSize: 16, fontWeight: '700' },
  small: { color: C.muted, fontSize: 13, lineHeight: 18, marginTop: 4 },
  tiny: { color: C.muted, fontSize: 11, marginTop: 2 },
  muted: { color: C.muted, fontSize: 12, flexShrink: 1 },
  link: { color: C.cyan, fontSize: 13, fontWeight: '600' },
  note: { color: C.amber, fontSize: 13, marginVertical: 6 },
  label: { color: C.muted, fontSize: 10.5, fontWeight: '800', letterSpacing: 0.8, marginTop: 10 },
  body: { color: C.text, fontSize: 14, lineHeight: 20, marginTop: 8 },
  repo: { color: C.cyan, fontSize: 14, fontWeight: '700' },
  fit: { color: C.green, fontSize: 12, fontWeight: '700' },
  tag: { color: C.cyan, fontSize: 11.5, fontWeight: '700', marginTop: 6 },
  mine: { color: C.pink, fontSize: 11.5, fontWeight: '700' },
  field: { backgroundColor: C.card, borderRadius: 16, borderWidth: 1, borderColor: C.line, padding: 10, marginTop: 2 },
  fieldHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 2 },
  fieldTitle: { color: C.text, fontSize: 13, fontWeight: '800', flex: 1 },
  toggle: { width: 28, height: 22, borderRadius: 11, borderWidth: 1, borderColor: C.line, alignItems: 'center', justifyContent: 'center' },
  acts: { flexDirection: 'row', gap: 8, marginTop: 8 },
  act: { flex: 1, flexDirection: 'row', gap: 6, alignItems: 'center', justifyContent: 'center', paddingVertical: 10,
         borderRadius: 12, backgroundColor: C.cardHi, borderWidth: 1, borderColor: C.line },
  actInvite: { backgroundColor: C.pink, borderColor: C.pink },
  actText: { color: C.text, fontSize: 13, fontWeight: '700' },
  btns: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  btn: { backgroundColor: C.cardHi, borderRadius: 12, paddingVertical: 7, paddingHorizontal: 11 },
  btnAccent: { backgroundColor: C.pink },
  btnText: { color: C.text, fontSize: 13, fontWeight: '600' },
  input: { borderWidth: 1, borderColor: C.line, borderRadius: 10, color: C.text, paddingHorizontal: 10, paddingVertical: 8,
    marginTop: 10, alignSelf: 'stretch' },
  button: { backgroundColor: C.violet, borderRadius: 12, paddingVertical: 10, alignItems: 'center', marginTop: 10 },
  buttonText: { color: '#fff', fontWeight: '700' },
});
