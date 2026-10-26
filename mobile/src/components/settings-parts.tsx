// Settings, as parts of the Settings main (the desktop's ⚙ panel pages, gui/qt_panel.py): Accounts, Your profile,
// Look, Notifications and Data & privacy (Help is its own page). Accounts' cards and words come from lib/accounts.ts,
// shared with the computer; connecting each one reuses the flows that already exist (sign-in buttons, the data repo
// token, the Signals setup card, the scan).
import Ionicons from '@expo/vector-icons/Ionicons';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Alert, Linking, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { cards, todo, todoText, type AccountCard } from '../lib/accounts';
import { useApp } from '../lib/app-state';
import { connectModel, disconnectModel, modelLink } from '../lib/model-repo';
import { orcidChecksumOk } from '../lib/orcid-login';
import { DOCK_IDLE_CHOICES, DOCK_IDLE_DEFAULT, dockIdleMs, setDockIdleMs } from '../lib/prefs';
import { isSetUp } from '../lib/signals';
import { C, setTheme, THEME, THEME_LABELS, type ThemeName } from '../lib/theme';
import { checkTokens, SETTINGS_URL } from '../lib/tokens';
import { DocSettings } from './doc-drop';
import { NotifySettings } from './notify-settings';
import { PackSettings } from './pack-settings';
import { SetupCard } from './signals-view';
import { OrcidSignInButton, SignInButton } from './signin';
import { TokenGuide } from './token-guide';
import { Card, open, s, Section } from './ui';
import { WhoisSettings } from './whois-find';
import { WisepSettings } from './wisep-settings';

const ORCID = /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/;
const ICONS: Record<AccountCard['key'], string> = { github: 'logo-github', orcid: 'school-outline', data: 'cloud-done-outline',
  beacon: 'radio-outline', device: 'desktop-outline' };

/** Settings → Accounts: GitHub and ORCID, then saving your data and Signals, then your computer. `go` opens a page. */
export function AccountsPart({ go }: { go: (id: string) => void }) {
  const { settings, token, save } = useApp();
  const [repo, setRepo] = useState<string | null>(null);
  const [beacon, setBeacon] = useState(false);
  const [warn, setWarn] = useState<{ data: boolean; signals: boolean }>({ data: false, signals: false });
  const [openKey, setOpenKey] = useState<string | null>(null);
  const reload = useCallback(() => {
    modelLink().then((l) => setRepo(l?.repo ?? null)).catch(() => setRepo(null));
    isSetUp().then(setBeacon).catch(() => setBeacon(false));
    checkTokens().then((t) => setWarn({ data: t.some((x) => x.name === 'data' && x.warn), signals: t.some((x) => x.name === 'signals' && x.warn) }))
      .catch(() => undefined);
  }, []);
  useEffect(reload, [reload]);
  if (!settings) return null;
  const items = cards({
    github: token ? 'on' : 'off', orcid: settings.orcid ? 'on' : 'off',
    data: repo ? (warn.data ? 'bad' : 'on') : 'off', beacon: beacon ? (warn.signals ? 'bad' : 'on') : 'off',
    device: Object.keys(settings.interests ?? {}).length ? 'on' : 'off',
  }, 'phone', { user: settings.username, orcid: settings.orcid, repo: repo ?? '' });
  const n = todo(items);
  return (
    <>
      {n ? (
        <View style={st.todo}>
          <Ionicons name="warning-outline" size={18} color={C.amber} />
          <Text style={st.todoText}>{todoText(n)}</Text>
        </View>
      ) : null}
      {items.map((c) => (
        <View key={c.key}>
          {c.heading ? <Section tour={c.key === 'github' ? 'settings:setup' : c.key === 'data' ? 'settings:sync' : undefined}>{c.heading}</Section> : null}
          <AccountCardView c={c} unfolded={!c.folded || openKey === c.key} onToggle={() => c.folded && setOpenKey(openKey === c.key ? null : c.key)}>
            {c.key === 'github' && c.state !== 'on' ? (
              <SignInButton onSignedIn={async (login, t) => {
                if (settings.username && login.toLowerCase() !== settings.username.toLowerCase()) {
                  throw new Error(`You signed in as ${login}, but this phone is set up for ${settings.username}.`);
                }
                await save({ ...settings, username: settings.username || login }, t);
              }} />
            ) : null}
            {c.key === 'orcid' && c.state !== 'on' ? <OrcidLink onLinked={(id) => save({ ...settings, orcid: id })} /> : null}
            {c.key === 'orcid' && c.state === 'on' ? (
              <Pressable onPress={() => Alert.alert('Unlink ORCID?', 'myGeeKy forgets your iD on this phone. Your ORCID record is not touched.', [
                { text: 'Cancel', style: 'cancel' }, { text: 'Unlink', style: 'destructive', onPress: () => save({ ...settings, orcid: '' }) }])}
                         style={st.ghost}><Text style={st.ghostText}>Unlink</Text></Pressable>
            ) : null}
            {c.key === 'data' && c.state === 'off' ? <DataConnect onConnected={reload} /> : null}
            {c.key === 'data' && c.state === 'bad' ? (
              <>
                <Pressable onPress={() => Linking.openURL(SETTINGS_URL)} style={[st.primary, st.bad]}><Text style={st.badText}>Renew on GitHub ↗</Text></Pressable>
                <DataConnect initialRepo={repo ?? ''} onConnected={reload} renewing />
              </>
            ) : null}
            {c.key === 'data' && c.state === 'on' ? (
              <Pressable onPress={() => Alert.alert('Stop saving to your data repo?', 'The phone forgets its token. Your repo is not touched.', [
                { text: 'Cancel', style: 'cancel' }, { text: 'Disconnect', style: 'destructive', onPress: async () => { await disconnectModel(); reload(); } }])}
                         style={st.ghost}><Text style={st.ghostText}>Disconnect</Text></Pressable>
            ) : null}
            {c.key === 'beacon' && c.state !== 'on' ? (
              settings.username ? <SetupCard me={settings.username} onDone={reload} />
                : <Text style={st.note}>Signals goes through GitHub: link GitHub above first.</Text>
            ) : null}
            {c.key === 'beacon' && c.state === 'on' ? (
              <Pressable onPress={() => go('signals')} style={st.ghost}><Text style={st.ghostText}>Open Signals</Text></Pressable>
            ) : null}
            {c.key === 'device' ? (
              <Pressable onPress={() => router.push('/scan')} style={c.state === 'on' ? st.ghost : st.primary}>
                <Text style={c.state === 'on' ? st.ghostText : st.primaryText}>{c.state === 'on' ? 'Scan again' : 'Scan from your computer'}</Text>
              </Pressable>
            ) : null}
          </AccountCardView>
        </View>
      ))}
    </>
  );
}

function AccountCardView({ c, unfolded, onToggle, children }: { c: AccountCard; unfolded: boolean; onToggle: () => void; children: React.ReactNode }) {
  const on = c.state === 'on', bad = c.state === 'bad';
  const tint = bad ? C.red : on ? C.green : C.muted;
  return (
    <View style={[st.card, on && st.cardOn, bad && st.cardBad, c.state === 'off' && !c.optional && st.cardTodo, on && !unfolded && { paddingVertical: 8 }]}>
      <Pressable onPress={onToggle} disabled={!on} style={st.head} accessibilityRole={on ? 'button' : undefined}
                 accessibilityState={on ? { expanded: unfolded } : undefined}>
        <View style={[st.icon, on && { backgroundColor: 'rgba(52,211,153,0.16)' }]}>
          <Ionicons name={(c.key === 'data' && bad ? 'cloud-offline-outline' : ICONS[c.key]) as never} size={17} color={tint} />
        </View>
        <Text style={st.title}>{c.title}</Text>
        <Text style={[st.pill, on && st.pillOn, bad && st.pillBad]}>{c.pill}</Text>
        {on ? <Ionicons name={unfolded ? 'chevron-up' : 'chevron-down'} size={16} color={C.green} /> : null}
      </Pressable>
      {unfolded ? (
        <>
          <Text style={st.why}>{c.why}</Text>
          <View style={{ marginTop: 8 }}>{children}</View>
        </>
      ) : null}
    </View>
  );
}

/** Link an ORCID iD: sign in with ORCID, or type it (checked with its checksum). */
function OrcidLink({ onLinked }: { onLinked: (orcid: string) => void }) {
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState('');
  const ok = ORCID.test(typed) && orcidChecksumOk(typed);
  return (
    <>
      <OrcidSignInButton onSignedIn={(me) => onLinked(me.orcid)} />
      {typing ? (
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
          <TextInput style={st.input} value={typed} onChangeText={(t) => setTyped(t.trim().toUpperCase())} autoCapitalize="characters"
                     autoCorrect={false} placeholder="0000-0002-1825-0097" placeholderTextColor={C.muted} />
          <Pressable onPress={() => ok && onLinked(typed)} disabled={!ok} style={[st.primary, { marginTop: 0 }, !ok && { opacity: 0.5 }]}>
            <Text style={st.primaryText}>Link</Text>
          </Pressable>
        </View>
      ) : (
        <Pressable onPress={() => setTyping(true)} style={st.ghost}><Text style={st.ghostText}>Type my iD</Text></Pressable>
      )}
      {typing && typed && !ok ? <Text style={st.note}>That isn&apos;t a valid ORCID iD yet: it looks like 0000-0002-1825-0097.</Text> : null}
    </>
  );
}

/** The data repo and its token: the picture steps, then repo + token, checked before it's kept. */
function DataConnect({ initialRepo = '', onConnected, renewing = false }: { initialRepo?: string; onConnected: () => void; renewing?: boolean }) {
  const [repo, setRepo] = useState(initialRepo);
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const connect = async () => {
    setBusy(true);
    setNote('Checking the token…');
    try {
      await connectModel(repo, token);
      setToken('');
      setNote('');
      onConnected();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      {renewing ? null : (
        <>
          <Text style={st.note}>First create a private repo named mygeeky-data on GitHub, then make a token for it:</Text>
          <TokenGuide which="data" />
        </>
      )}
      <TextInput style={[st.input, st.field]} value={repo} onChangeText={setRepo} autoCapitalize="none" autoCorrect={false}
                 placeholder="you/mygeeky-data" placeholderTextColor={C.muted} accessibilityLabel="Your data repo" />
      <TextInput style={[st.input, st.field]} value={token} onChangeText={setToken} autoCapitalize="none" autoCorrect={false}
                 secureTextEntry placeholder="github_pat_…" placeholderTextColor={C.muted} accessibilityLabel="Paste the token" />
      <Pressable onPress={connect} disabled={busy || !token.trim()} style={[st.primary, (busy || !token.trim()) && { opacity: 0.5 }]}>
        <Text style={st.primaryText}>{busy ? 'Connecting…' : renewing ? 'Use the new token' : 'Connect'}</Text>
      </Pressable>
      {note ? <Text style={[st.note, { color: C.red }]}>{note}</Text> : null}
    </>
  );
}

/** Settings → Your profile: your papers, a CV, your keywords. */
export function ProfilePart({ go }: { go: (id: string) => void }) {
  const { settings } = useApp();
  return (
    <>
      <Section tour="settings:papers">📄 YOUR PAPERS (OPENALEX)</Section>
      <View style={{ marginBottom: 6 }}><WhoisSettings /></View>
      <Section tour="settings:cv">📝 FROM A CV, THESIS OR ABSTRACT</Section>
      <View style={{ marginBottom: 6 }}><DocSettings /></View>
      <Section>🔤 YOUR KEYWORDS</Section>
      <Card>
        <Text style={st.body}>{settings?.keywords.length ? settings.keywords.join(', ') : 'None yet.'}</Text>
        <Pressable onPress={() => go('you:model')}><Text style={st.link}>Change them in You → Your model</Text></Pressable>
      </Card>
    </>
  );
}

/** Settings → Look: the theme, and how long the dock stays up. */
export function LookPart() {
  const [dockIdle, setDockIdle] = useState(DOCK_IDLE_DEFAULT);
  useEffect(() => { dockIdleMs().then(setDockIdle); }, []);
  const pickTheme = (name: ThemeName) => {
    if (name === THEME) return;
    Alert.alert('Change the theme?', 'myGeeKy restarts to draw every screen in the new colours.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Change it', onPress: async () => { if (!(await setTheme(name))) Alert.alert('Theme', 'Saved: close and open myGeeKy to see it.'); } },
    ]);
  };
  const pickDock = async (ms: number) => { setDockIdle(ms); await setDockIdleMs(ms); };
  return (
    <>
      <Section tour="settings:look">🎨 THEME</Section>
      <Card>
        <View style={st.choices}>
          {THEME_LABELS.map(([name, label]) => (
            <Pressable key={name} onPress={() => pickTheme(name)} accessibilityRole="radio" accessibilityState={{ selected: THEME === name }}
                       style={[st.choice, THEME === name && st.choiceOn]}>
              <Text style={[st.choiceText, THEME === name && { color: '#fff' }]}>{label}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={[st.key, { marginTop: 14 }]}>The dock folds away after</Text>
        <View style={st.choices}>
          {DOCK_IDLE_CHOICES.map(([ms, label]) => (
            <Pressable key={ms} onPress={() => pickDock(ms)} accessibilityRole="radio" accessibilityState={{ selected: dockIdle === ms }}
                       style={[st.choice, dockIdle === ms && st.choiceOn]}>
              <Text style={[st.choiceText, dockIdle === ms && { color: '#fff' }]}>{label}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={[s.small, { marginTop: 10 }]}>The same three themes as on your computer. The computer&apos;s window settings
          (transparency, panel size, place on screen, stay on top, floating hearts) belong to its floating panel.</Text>
      </Card>
    </>
  );
}

/** Settings → Notifications. */
export function NotifyPart() {
  return <NotifySettings full />;
}

/** Settings → Data & privacy: how myGeeKy asks the internet, packs, privacy, and Start over. */
export function DataPart() {
  const { forget } = useApp();
  const reset = async () => {
    const run = async () => {
      router.replace('/setup');                    // first leave Home (it needs settings to draw)...
      await forget();                              // ...then forget what's stored and the running app's copy
    };
    if (Platform.OS === 'web') return run();
    Alert.alert('Start over?', 'This erases everything myGeeKy keeps on this phone: settings, sign-in, tokens and keys. '
      + 'Your GitHub repos stay (mygeeky.org/delete.html says how to remove them).', [
      { text: 'Cancel', style: 'cancel' }, { text: 'Start over', style: 'destructive', onPress: run },
    ]);
  };
  return (
    <>
      <Section tour="settings:wisep">🧠 HOW MYGEEKY ASKS THE INTERNET</Section>
      <View style={{ marginBottom: 6 }}><WisepSettings /></View>
      <Section tour="settings:packs">📦 PACKS</Section>
      <View style={{ marginBottom: 6 }}><PackSettings /></View>
      <Section>🔒 PRIVACY</Section>
      <Card>
        <Text style={st.body}>Your data stays on this phone, and in your own private repo if you save it there. myGeeKy reads public
          data (news feeds, OpenAlex, Hugging Face, Product Hunt, GitHub) and never posts, follows or stars anything for you.</Text>
        <Pressable onPress={() => open('https://mygeeky.org/privacy.html')}><Text style={st.link}>Privacy policy ↗</Text></Pressable>
        <Pressable onPress={() => open('https://mygeeky.org/terms.html')}><Text style={st.link}>Signals terms ↗</Text></Pressable>
        <Pressable onPress={() => open('https://mygeeky.org')}><Text style={st.link}>myGeeKy for your computer ↗</Text></Pressable>
        <Pressable onPress={() => Linking.openURL('mailto:support@mygeeky.org')}><Text style={st.link}>Questions or problems? support@mygeeky.org</Text></Pressable>
        <Text style={[s.small, { marginTop: 10 }]}>myGeeKy {Constants.expoConfig?.version ?? ''}</Text>
      </Card>
      <Section>↺ START OVER</Section>
      <Card>
        <Text style={st.body}>Erases everything myGeeKy keeps on this phone. Your GitHub repos stay.</Text>
        <Pressable onPress={reset} style={st.danger}><Text style={st.dangerText}>Start over…</Text></Pressable>
      </Card>
    </>
  );
}

const st = StyleSheet.create({
  todo: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, marginBottom: 6, borderRadius: 14, backgroundColor: 'rgba(251,191,36,0.14)' },
  todoText: { flex: 1, color: C.text, fontSize: 13.5, fontWeight: '700' },
  card: { padding: 12, marginTop: 8, borderRadius: 16, backgroundColor: C.card, borderWidth: 1.5, borderColor: C.line },
  cardOn: { backgroundColor: 'rgba(52,211,153,0.10)', borderColor: 'rgba(52,211,153,0.55)' },
  cardBad: { backgroundColor: 'rgba(248,113,113,0.12)', borderColor: C.red },
  cardTodo: { borderColor: 'rgba(45,212,191,0.6)' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 36 },
  icon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: C.cardHi },
  title: { flex: 1, color: C.text, fontSize: 15, fontWeight: '800' },
  pill: { paddingHorizontal: 9, paddingVertical: 3, borderRadius: 11, overflow: 'hidden', fontSize: 11.5, fontWeight: '800', color: C.muted, backgroundColor: C.cardHi },
  pillOn: { color: C.green, backgroundColor: 'rgba(52,211,153,0.18)' },
  pillBad: { color: C.red, backgroundColor: 'rgba(248,113,113,0.2)' },
  why: { color: C.text, fontSize: 13, lineHeight: 19, marginTop: 8 },
  note: { color: C.muted, fontSize: 12.5, lineHeight: 18, marginTop: 6 },
  primary: { alignSelf: 'flex-start', marginTop: 10, paddingHorizontal: 16, minHeight: 40, borderRadius: 20, justifyContent: 'center', backgroundColor: C.violet },
  primaryText: { color: '#fff', fontSize: 13.5, fontWeight: '800' },
  bad: { backgroundColor: C.red },
  badText: { color: '#1a1013', fontSize: 13.5, fontWeight: '800' },
  ghost: { alignSelf: 'flex-start', marginTop: 8, paddingHorizontal: 14, minHeight: 38, borderRadius: 19, justifyContent: 'center', borderWidth: 1, borderColor: C.line },
  ghostText: { color: C.text, fontSize: 13, fontWeight: '700' },
  danger: { alignSelf: 'flex-start', marginTop: 10, paddingHorizontal: 16, minHeight: 40, borderRadius: 20, justifyContent: 'center', borderWidth: 1.5, borderColor: C.red },
  dangerText: { color: C.red, fontSize: 13.5, fontWeight: '800' },
  input: { flex: 1, backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 12, color: C.text, paddingHorizontal: 12, minHeight: 44, fontSize: 15 },
  field: { marginTop: 10, flex: 0 },
  body: { color: C.text, fontSize: 14, lineHeight: 20 },
  link: { color: C.cyan, fontSize: 14, marginTop: 8 },
  key: { color: C.muted, fontSize: 13 },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 6 },
  choice: { paddingHorizontal: 12, paddingVertical: 9, borderRadius: 12, backgroundColor: C.cardHi, minHeight: 40, justifyContent: 'center' },
  choiceOn: { backgroundColor: C.violet },
  choiceText: { color: C.text, fontSize: 14, fontWeight: '700' },
});
