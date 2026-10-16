// You, in the centre of the orbit: your model (keywords), your badges, and the rest.
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, Image, Linking, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { InterestMap, MAP_EXPLORE, MAP_FIELD, MAP_LEARNED } from './interest-map';
import { AucGauge, aucVerdict, ExploreDonut, StatTiles, TrendChart, WeightBars } from './model-plots';
import { SignInButton } from './signin';
import { Card, Empty, open, s, Section, timeAgo } from './ui';
import { useApp, withRepoProfile } from '../lib/app-state';
import { Achievement, earned, Earned, githubAchievements, TIER_COLORS, TIERS } from '../lib/badges';
import { Dict, lookup } from '../lib/interests';
import { badgeCounts, type Brain, cachedBrain, connectModel, disconnectModel, MODEL_TOKEN_PAGE, modelLink, queuedUsage, syncModel } from '../lib/model-repo';
import { loadDictionary } from '../lib/profile';
import { signalsToken } from '../lib/signals';
import { clearAll } from '../lib/storage';
import { C, setTheme, THEME, THEME_LABELS, type ThemeName } from '../lib/theme';
import { DOCK_IDLE_CHOICES, DOCK_IDLE_DEFAULT, dockIdleMs, setDockIdleMs } from '../lib/prefs';


export function ModelPart() {
  const { settings, profile, save } = useApp();
  const [word, setWord] = useState('');
  const [dict, setDict] = useState<Dict | null>(null);
  useEffect(() => {
    loadDictionary().then(setDict);
  }, []);
  if (!settings) return null;
  const addKeyword = async () => {
    const w = word.trim();
    setWord('');
    if (!w || settings.keywords.some((k) => k.toLowerCase() === w.toLowerCase())) return;
    await save({ ...settings, keywords: [...settings.keywords, w] });
  };
  const removeKeyword = (k: string) => save({ ...settings, keywords: settings.keywords.filter((x) => x !== k) });
  return (
    <>
      <Section>🔤 YOUR KEYWORDS</Section>
      <View style={st.chips}>
        {settings.keywords.map((k) => {
          const known = !dict || !!lookup(dict, k);
          return (
            <Pressable key={k} onPress={() => removeKeyword(k)} style={[st.chip, !known && st.chipNew]}>
              <Text style={[st.chipText, !known && { color: C.red }]}>{k}  ✕</Text>
            </Pressable>
          );
        })}
      </View>
      <View style={st.addRow}>
        <TextInput style={st.input} value={word} onChangeText={setWord} onSubmitEditing={addKeyword}
                   placeholder="Add a keyword: AI, single cell…" placeholderTextColor={C.muted} returnKeyType="done" />
        <Pressable style={st.add} onPress={addKeyword}><Text style={st.addText}>Add</Text></Pressable>
      </View>
      <Text style={s.small}>Green keywords carry their related words with them. Red ones are new to myGeeKy, so
        they only match as written.</Text>

      <Section>🧭 YOUR INTEREST MAP</Section>
      <ModelMap username={settings.username} dict={dict} />

      <Section>🧭 YOUR RESEARCH FIELD</Section>
      <Card>
        <Text style={st.body}>
          {profile?.field.length ? profile.field.join(' · ') :
            settings.orcid ? 'Looking it up from your ORCID…' : 'Add your ORCID (Settings → Start over) to find your exact research field.'}
        </Text>
        {settings.orcid ? <Text style={st.link} onPress={() => open(`https://orcid.org/${settings.orcid}`)}>ORCID {settings.orcid} ↗</Text> : null}
      </Card>

      <Section>🧠 WHAT YOUR FEEDS LOOK FOR</Section>
      <View style={st.chips}>
        {Object.entries(profile?.weights ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 24).map(([t, w]) => (
          <View key={t} style={[st.weight, { opacity: 0.45 + 0.55 * Math.min(w, 1) }]}><Text style={st.weightText}>{t}</Text></View>
        ))}
      </View>
    </>
  );
}

// Your interest map, from your private data repo -- the same map as the desktop's Model tab.
function ModelMap({ username, dict }: { username: string; dict: Dict | null }) {
  const { settings, save } = useApp();
  const [brain, setBrain] = useState<Brain | null>(null);
  const [linked, setLinked] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [repo, setRepo] = useState(username ? `${username}/mygeeky-data` : '');
  const [token, setToken] = useState('');

  const refresh = async () => {
    setBusy(true);
    try {
      const r = await syncModel(dict);
      if (r && settings) {                              // every list is ranked by you, as your computers know you
        const next = withRepoProfile(settings, r.brain);
        if (next) await save(next);
      }
      if (r) { setBrain(r.brain); setNote(r.sent ? `Sent ${r.sent} thing${r.sent === 1 ? '' : 's'} you opened here to your computers.` : ''); }
    } catch (e) {
      setNote(e instanceof Error ? e.message : 'Couldn\'t reach your data repo. Showing the last copy.');
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    (async () => {
      const link = await modelLink();
      setLinked(!!link);
      if (!link) return;
      setRepo(link.repo);
      const cached = await cachedBrain();
      if (cached?.data) setBrain(cached.data);
      if (dict) refresh();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dict]);

  const connect = async () => {
    setBusy(true);
    setNote('Checking the token…');
    try {
      await connectModel(repo, token);
      setToken('');
      setLinked(true);
      setNote('');
      await refresh();
    } catch (e) {
      setNote(e instanceof Error ? e.message : 'That didn\'t work. Try again.');
    } finally {
      setBusy(false);
    }
  };
  const disconnect = () => Alert.alert('Disconnect your data repo?', 'The phone forgets its token and the map. Your repo is not touched.', [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Disconnect', style: 'destructive', onPress: async () => { await disconnectModel(); setBrain(null); setLinked(false); setNote(''); } },
  ]);

  if (linked === null) return null;
  if (!linked) {
    return (
      <View style={st.scan}>
        <Text style={st.scanTitle}>Your map lives in your private data repo</Text>
        <Text style={st.scanSub}>
          It&apos;s what myGeeKy learned on your computers (every click, follow, star and fork), kept in the private repo
          they sync to. Give this phone its own token for it:{'\n'}
          1. On GitHub: Fine-grained token → Only select repositories → your data repo → Permissions → Contents → Read and
          write.{'\n'}
          2. Paste it here and tap Connect. What you open on the phone then teaches your computers too.
        </Text>
        <Pressable onPress={() => Linking.openURL(MODEL_TOKEN_PAGE)} style={[st.add, st.tokenButton]}>
          <Text style={st.addText}>Make the token on GitHub ↗</Text>
        </Pressable>
        <TextInput style={[st.input, st.field]} value={repo} onChangeText={setRepo} autoCapitalize="none" autoCorrect={false}
                   placeholder="you/mygeeky-data" placeholderTextColor={C.muted} />
        <TextInput style={[st.input, st.field]} value={token} onChangeText={setToken} autoCapitalize="none" autoCorrect={false}
                   secureTextEntry placeholder="github_pat_…" placeholderTextColor={C.muted} />
        <Pressable onPress={connect} disabled={busy || !token.trim()} style={[st.add, st.tokenButton, (busy || !token.trim()) && { opacity: 0.5 }]}>
          <Text style={st.addText}>{busy ? 'Connecting…' : 'Connect'}</Text>
        </Pressable>
        {note ? <Text style={[st.scanSub, { color: C.red }]}>{note}</Text> : null}
      </View>
    );
  }
  if (!brain) return <Text style={s.small}>{busy ? 'Reading your data repo…' : note || 'No map yet.'}</Text>;
  const t = brain.taught;
  const history = brain.history ?? [];
  const latest = history.at(-1);
  const prev = history.at(-2);
  const auc = latest?.auc ?? null;
  const [grade, explanation] = aucVerdict(auc);
  const diff = auc !== null && prev?.auc != null ? auc - prev.auc : null;
  const delta = diff === null ? '' : `${diff > 0.001 ? '▲' : diff < -0.001 ? '▼' : '●'} ${diff >= 0 ? '+' : ''}${diff.toFixed(3)} since the previous retrain`;
  const nTrain = latest?.n_train ?? 0;
  const nPos = latest?.n_pos ?? 0;
  return (
    <>
      <InterestMap center={brain.user || username} field={brain.field} learned={brain.learned} explore={brain.explore} />
      <Text style={s.small}>
        <Text style={{ color: MAP_FIELD }}>●</Text> your research field   <Text style={{ color: MAP_LEARNED }}>●</Text> what
        you&apos;re into lately (bigger = stronger)   <Text style={{ color: MAP_EXPLORE }}>◌</Text> new territory today. Tap a
        point for more.
        {brain.learned.length ? '' : '\nNothing learned yet: click people, repos and news, or follow, star and fork on GitHub, and your map grows.'}
      </Text>

      <Section>🧠 WHAT TEACHES IT (LAST 30 DAYS)</Section>
      <StatTiles tiles={[[String(t.clicks), 'clicks'], [String(t.follows), 'follows'], [String(t.stars), 'stars'], [String(t.forks), 'forks']]} />
      <Text style={[s.small, { marginTop: 6 }]}>
        {brain.learning
          ? `Each action fades to half after ${brain.halfLife} days, so your map follows where your work is going. Forks count most, then follows and stars, then clicks.`
          : 'Learning is off (mygeeky config set interest_learning true).'}
      </Text>

      <Section>🔭 ROOM TO EXPLORE</Section>
      <View style={st.hero}>
        <ExploreDonut share={brain.exploreShare} />
        <Text style={[s.small, { flex: 1 }]}>
          {brain.exploreShare > 0
            ? `${Math.round(brain.exploreShare * 100)}% of every list (People, Repos, News, Research) is kept for things outside your usual interests, marked 🔭.${brain.explore.length ? ` Today: ${brain.explore.join(', ')}.` : ''}`
            : 'Exploration is off (mygeeky config set explore_share 0.2 turns it on).'}
        </Text>
      </View>

      <Section>👥 WHO FOLLOWS YOU BACK</Section>
      <View style={st.hero}>
        <AucGauge auc={auc} />
        <View style={{ flex: 1 }}>
          <Text style={st.grade}>{grade}</Text>
          <Text style={s.small}>{explanation}</Text>
          {delta ? <Text style={[s.small, { marginTop: 4 }]}>{delta}</Text> : null}
        </View>
      </View>
      <StatTiles tiles={[[String(nTrain), 'examples'], [String(nPos), 'follow-backs'],
        [`${nTrain ? Math.round((100 * nPos) / nTrain) : 0}%`, 'follow-back rate'], [String(brain.history.length), 'retrains']]} />
      <Text style={st.sub}>WHAT IT HAS LEARNED</Text>
      <WeightBars weights={brain.weights} />
      <Text style={s.small}>Right = makes a follow-back more likely; left = less likely.</Text>
      <Text style={st.sub}>GETTING SHARPER?</Text>
      <TrendChart history={brain.history} />
      <Text style={[s.small, { marginTop: 4 }]}>
        {latest ? `Last retrained ${timeAgo(latest.timestamp)}. Follow people you like, then run mygeeky learn -- every follow-back you get teaches it more. Tap the chart for details.`
          : 'No retrains yet -- run mygeeky bootstrap, then mygeeky learn.'}
      </Text>

      <Text style={[s.small, { marginTop: 6 }]}>
        From {brain.repo}{brain.syncedAt ? ` · your computers synced ${timeAgo(brain.syncedAt)}` : ''}.{' '}
        <Text style={st.link} onPress={busy ? undefined : refresh}>{busy ? 'Refreshing…' : 'Refresh'}</Text>{'   '}
        <Text style={[st.link, { color: C.muted }]} onPress={disconnect}>Disconnect</Text>
      </Text>
      {note ? <Text style={[s.small, { marginTop: 4 }]}>{note}</Text> : null}
    </>
  );
}

export function BadgesPart() {
  const { settings } = useApp();
  const [mine, setMine] = useState<Earned[]>([]);
  const [gh, setGh] = useState<Achievement[]>([]);
  useEffect(() => {
    (async () => {
      const show = async (brain: Brain | null | undefined) => {
        // connected: the desktop's own counts (achievements.counts), your computers and this phone together
        const fromRepo = brain?.usage ? badgeCounts(brain, await queuedUsage()) : undefined;
        setMine(await earned(settings?.keywords.length ?? 0, settings?.desktopBadges ?? [], fromRepo));
      };
      const cached = await cachedBrain();
      await show(cached?.data);
      if (await modelLink()) {                          // then fresh from your data repo
        try {
          const r = await syncModel(await loadDictionary());
          if (r) await show(r.brain);
        } catch { /* offline: the saved copy stays */ }
      }
    })();
    if (settings?.username) githubAchievements(settings.username).then(setGh);
  }, [settings]);
  // by score: gold, silver, bronze, not yet -- and within each, closest to the next tier first
  const level = (b: Earned) => (b.tier ? TIERS.indexOf(b.tier as typeof TIERS[number]) + 1 : 0);
  const progress = (b: Earned) => (b.next ? b.count / b.next : 1);
  const ranked = [...mine].sort((x, y) => level(y) - level(x) || progress(y) - progress(x) || x.name.localeCompare(y.name));
  return (
    <>
      <Section>🐙 ON GITHUB</Section>
      {gh.length ? (
        <View style={st.chips}>
          {gh.map((a) => (
            <View key={a.name} style={{ alignItems: 'center', width: 76 }}>
              <Image source={{ uri: a.image }} style={{ width: 56, height: 56 }} />
              <Text style={[s.small, { textAlign: 'center' }]} numberOfLines={2}>{a.name}</Text>
            </View>
          ))}
        </View>
      ) : <Empty>No GitHub achievements found on your profile yet.</Empty>}

      <Section>🏅 MYGEEKY BADGES</Section>
      {ranked.map((b) => (
        <Card key={b.id}>
          <View style={[s.row, { alignItems: 'center' }]}>
            <View style={[st.medal, { borderColor: b.tier ? TIER_COLORS[b.tier] : C.line, opacity: b.tier ? 1 : 0.45 }]}>
              <Text style={{ fontSize: 20 }}>{b.emoji}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.name}>{b.name}{b.tier ? <Text style={{ color: TIER_COLORS[b.tier] }}>  {b.tier}</Text> : null}</Text>
              <Text style={s.small}>{b.count} {b.what}{b.next ? ` · next at ${b.next}` : ''}</Text>
            </View>
          </View>
        </Card>
      ))}
    </>
  );
}

// ⚙ Settings: what the desktop's ⚙ holds that means something on a phone -- your setup, sync with your data
// repo, Signals, the 💡 -- and none of its window controls (transparency, panel height, place on screen).
export function MorePart() {
  const { settings, token, save } = useApp();
  const [repo, setRepo] = useState<string | null>(null);
  const [signals, setSignals] = useState(false);
  useEffect(() => {
    modelLink().then((l) => setRepo(l?.repo ?? null)).catch(() => setRepo(null));
    signalsToken().then((t) => setSignals(!!t)).catch(() => setSignals(false));
  }, []);
  const [dockIdle, setDockIdle] = useState(DOCK_IDLE_DEFAULT);
  useEffect(() => { dockIdleMs().then(setDockIdle); }, []);
  if (!settings) return null;
  const pickTheme = (name: ThemeName) => {
    if (name === THEME) return;
    Alert.alert('Change the theme?', 'myGeeKy restarts to draw every screen in the new colours.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Change it', onPress: async () => { if (!(await setTheme(name))) Alert.alert('Theme', 'Saved: close and open myGeeKy to see it.'); } },
    ]);
  };
  const pickDock = async (ms: number) => { setDockIdle(ms); await setDockIdleMs(ms); };
  const reset = async () => {
    const go = async () => {
      await clearAll();
      router.replace('/setup');
    };
    if (Platform.OS === 'web') return go();
    Alert.alert('Start over?', 'This forgets your settings and sign-in on this phone.', [
      { text: 'Cancel', style: 'cancel' }, { text: 'Start over', style: 'destructive', onPress: go },
    ]);
  };
  const rows: [string, string, boolean][] = [
    ['GitHub', settings.username, true],
    ['Signed in', token ? 'yes: Live and People refresh freely' : 'no (sign in below)', !!token],
    ['ORCID', settings.orcid || 'not set', !!settings.orcid],
    ['Keywords', settings.keywords.length ? settings.keywords.join(', ') : 'none yet (add them in Your model)', settings.keywords.length > 0],
    ['From computer', Object.keys(settings.interests ?? {}).length
      ? `${Object.keys(settings.interests).length} interests, ${settings.field?.length ?? 0} research topics, ${settings.desktopBadges?.length ?? 0} badges`
      : 'nothing yet: scan the code above', Object.keys(settings.interests ?? {}).length > 0],
    ['Sync', repo ? `✓ on: ${repo} (your model, badges and clicks)` : 'off: connect your data repo in Your model', !!repo],
    ['Signals', signals ? '✓ on: you send and receive on this phone' : 'off (turn it on in the 📡 Signals planet)', signals],
    ['App version', Constants.expoConfig?.version ?? '', true],
  ];
  return (
    <>
      <Pressable onPress={() => router.push('/scan')} style={st.scan}>
        <Text style={st.scanTitle}>📷  Scan from your computer</Text>
        <Text style={st.scanSub}>On your computer: ⚙ → Connect your phone. One scan brings over your profile, your
          interests and your badges (do it again any time to refresh them).</Text>
      </Pressable>

      <Section>🎨 LOOK</Section>
      <Card>
        <Text style={st.setupKey}>Theme</Text>
        <View style={st.choices}>
          {THEME_LABELS.map(([name, label]) => (
            <Pressable key={name} onPress={() => pickTheme(name)} accessibilityRole="radio" accessibilityState={{ selected: THEME === name }}
                       style={[st.choice, THEME === name && st.choiceOn]}>
              <Text style={[st.choiceText, THEME === name && { color: '#fff' }]}>{label}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={[st.setupKey, { marginTop: 12, width: undefined }]}>The dock folds away after</Text>
        <View style={st.choices}>
          {DOCK_IDLE_CHOICES.map(([ms, label]) => (
            <Pressable key={ms} onPress={() => pickDock(ms)} accessibilityRole="radio" accessibilityState={{ selected: dockIdle === ms }}
                       style={[st.choice, dockIdle === ms && st.choiceOn]}>
              <Text style={[st.choiceText, dockIdle === ms && { color: '#fff' }]}>{label}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={[s.small, { marginTop: 10 }]}>The same three themes as on your computer. The computer&apos;s window settings
          (transparency, panel height, place on screen, stay on top, floating hearts) belong to its floating panel and have no
          phone equivalent; Start over below is the phone&apos;s uninstall.</Text>
      </Card>

      <Section>⚙️ YOUR SETUP</Section>
      <Card>
        {rows.map(([k, v, on]) => (
          <View key={k} style={st.setupRow}>
            <Text style={st.setupKey}>{k}</Text>
            <Text style={[st.setupVal, !on && { color: C.muted }]}>{v}</Text>
          </View>
        ))}
      </Card>

      <Section>🔑 GITHUB</Section>
      <Card>
        <Text style={st.body}>{token ? 'Signed in: Live and People refresh freely. Read-only: myGeeKy can never follow, star or post.'
          : 'Sign in so Live and People can refresh freely. Read-only: myGeeKy can never follow, star or post.'}</Text>
        {!token ? (
          <SignInButton onSignedIn={async (login, t) => {
            if (login.toLowerCase() !== settings.username.toLowerCase()) {
              throw new Error(`You signed in as ${login}, but this phone is set up for ${settings.username}.`);
            }
            await save(settings, t);
          }} />
        ) : null}
      </Card>

      <Section>☁️ SYNC WITH YOUR COMPUTERS</Section>
      <Card>
        <Text style={st.body}>{repo
          ? `Your model, badges and what you open here travel through your private repo ${repo}, like one more computer in sync. Its token is only on this phone, in the secure store.`
          : 'Connect your private data repo (the one `mygeeky sync` uses) in Your model: the phone then shows your real model and badges, and teaches your computers too.'}</Text>
      </Card>

      <Section>📡 SIGNALS</Section>
      <Card>
        <Text style={st.body}>Private thank-yous and collab invites between myGeeKy users. Open the 📡 Signals planet
          to turn them on for this phone: it gets its own key, kept only here.</Text>
      </Card>

      <Section>🔒 PRIVACY</Section>
      <Card>
        <Text style={st.body}>{repo ? 'Your data stays on this phone and in your own private repo.' : 'Everything stays on this phone.'} myGeeKy
          reads public data (news feeds, OpenAlex, Hugging Face, Product Hunt, GitHub) and never posts, follows or stars anything for you.</Text>
      </Card>

      <Pressable onPress={() => open('https://mygeeky.org')}>
        <Text style={[st.link, { marginTop: 18 }]}>myGeeKy for your computer ↗</Text>
      </Pressable>
      <Pressable onPress={() => Linking.openURL('mailto:support@mygeeky.org')}>
        <Text style={st.link}>Questions or problems? support@mygeeky.org</Text>
      </Pressable>
      <Pressable onPress={reset}><Text style={[st.link, { color: C.red, marginTop: 14 }]}>Start over</Text></Pressable>
    </>
  );
}

const st = StyleSheet.create({
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { backgroundColor: 'rgba(52,211,153,0.14)', borderColor: 'rgba(52,211,153,0.5)', borderWidth: 1, borderRadius: 999,
          paddingHorizontal: 12, paddingVertical: 7 },
  chipNew: { backgroundColor: 'rgba(248,113,113,0.12)', borderColor: 'rgba(248,113,113,0.5)' },
  chipText: { color: C.green, fontWeight: '700', fontSize: 14 },
  weight: { backgroundColor: 'rgba(122,92,255,0.18)', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  weightText: { color: C.text, fontSize: 12 },
  addRow: { flexDirection: 'row', gap: 8, marginTop: 10, marginBottom: 6 },
  input: { flex: 1, backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 12, color: C.text,
           paddingHorizontal: 12, paddingVertical: 10, fontSize: 15 },
  add: { backgroundColor: C.violet, borderRadius: 12, paddingHorizontal: 16, justifyContent: 'center' },
  addText: { color: '#fff', fontWeight: '800' },
  body: { color: C.text, fontSize: 14, lineHeight: 20 },
  link: { color: C.cyan, fontSize: 14, marginTop: 8 },
  scan: { backgroundColor: 'rgba(255,111,216,0.12)', borderColor: 'rgba(255,111,216,0.45)', borderWidth: 1,
          borderRadius: 16, padding: 14, marginTop: 6 },
  scanTitle: { color: C.text, fontSize: 16, fontWeight: '800' },
  scanSub: { color: C.muted, fontSize: 12.5, marginTop: 5, lineHeight: 17 },
  setupRow: { flexDirection: 'row', paddingVertical: 4, gap: 10 },
  setupKey: { color: C.muted, fontSize: 13, width: 92 },
  setupVal: { color: C.text, fontSize: 13, flex: 1 },
  hero: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 4 },
  grade: { color: C.text, fontSize: 18, fontWeight: '800', marginBottom: 2 },
  sub: { color: C.muted, fontSize: 11, fontWeight: '700', letterSpacing: 0.5, marginTop: 14, marginBottom: 4 },
  tokenButton: { alignSelf: 'flex-start', paddingVertical: 10, marginTop: 10 },
  field: { marginTop: 10, flex: 0 },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 6 },
  choice: { paddingHorizontal: 12, paddingVertical: 9, borderRadius: 12, backgroundColor: C.cardHi, minHeight: 40, justifyContent: 'center' },
  choiceOn: { backgroundColor: C.violet },
  choiceText: { color: C.text, fontSize: 14, fontWeight: '700' },
  medal: { width: 42, height: 42, borderRadius: 21, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
});
