// You, in the centre of the orbit: your model (keywords), your badges, and the rest.
import { useEffect, useState } from 'react';
import { Alert, Image, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { InterestMap, MAP_EXPLORE, MAP_FIELD, MAP_LEARNED } from './interest-map';
import { AucGauge, aucVerdict, ExploreDonut, StatTiles, TrendChart, WeightBars } from './model-plots';

import { Card, Empty, open, s, Section, timeAgo } from './ui';
import { useApp, withRepoProfile } from '../lib/app-state';
import { Achievement, earned, Earned, githubAchievements, TIER_COLORS, TIERS } from '../lib/badges';
import { Dict, lookup } from '../lib/interests';
import { badgeCounts, type Brain, cachedBrain, disconnectModel, localEvents, queuedUsage, savingLink, syncModel } from '../lib/model-repo';
import { loadDictionary } from '../lib/profile';
import { C } from '../lib/theme';


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
      const link = await savingLink();
      setLinked(!!link);
      if (!link) return;
      const cached = await cachedBrain();
      if (cached?.data) setBrain(cached.data);
      if (dict) refresh();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dict]);

  const [kept, setKept] = useState(0);                       // what this phone learned with no repo yet
  useEffect(() => { if (linked === false) localEvents().then((e) => setKept(e.length)).catch(() => undefined); }, [linked]);

  const disconnect = () => Alert.alert('Stop saving from this phone?', 'The phone forgets where your data is saved, and the map. Nothing saved there is touched.', [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Disconnect', style: 'destructive', onPress: async () => { await disconnectModel(); setBrain(null); setLinked(false); setNote(''); } },
  ]);

  if (linked === null) return null;
  if (!linked) {
    return (
      <View style={st.scan}>
        <Text style={st.scanTitle}>Your map lives where your data is saved</Text>
        <Text style={[st.scanSub, { color: C.amber }]}>
          📱 Learning on this phone only{kept ? `: ${kept} thing${kept === 1 ? '' : 's'} you opened so far` : ''}. Save your
          data to keep it and share it with your computer: what this phone learned goes there too.
        </Text>
        <Text style={st.scanSub}>
          Choose Google Drive (recommended) or a private GitHub repo in Settings → Accounts → Saving your data. Either works
          the same, encrypted on your devices: your computers&apos; map comes here, and what you open here teaches them too.
        </Text>
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
      if (await savingLink()) {                         // then fresh from where your data is saved
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
