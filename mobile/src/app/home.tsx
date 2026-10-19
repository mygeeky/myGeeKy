// The whole app on one screen: what you picked on top, the orbit below (under
// your thumb, clear of the phone's own buttons). Reading folds the orbit into a
// dock of two rows; scrolling back to the top, or double-tapping "Spin the rings", brings it back.
import AsyncStorage from '@react-native-async-storage/async-storage';
import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Image, LayoutAnimation, Linking, NativeScrollEvent, NativeSyntheticEvent, Pressable, RefreshControl, ScrollView, StyleSheet, Text,
         useWindowDimensions, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Polyline } from 'react-native-svg';
import { Orbit, orbitHeight } from '../components/orbit';
import { PersonCard } from '../components/person-card';
import { ChancesView } from '../components/chances-view';
import { GrowView } from '../components/grow-view';
import { MonthView, rankNews } from '../components/month-view';
import { useToast } from '../components/toast';
import { SignalsView } from '../components/signals-view';
import { Empty, open, Segments } from '../components/ui';
import { AdminPart } from '../components/admin-part';
import { IdeaForm } from '../components/idea-sheet';
import { BadgesPart, ModelPart, MorePart } from '../components/you-parts';
import { timeAgo, useApp, useFeed } from '../lib/app-state';
import { fetchHeadlines } from '../lib/headlines';
import { fetchLive } from '../lib/live';
import { fetchLaunches, fetchRepos } from '../lib/market';
import { fetchModels } from '../lib/models';
import { adminLogin } from '../lib/admin';
import { type BoardRow, loadBoard } from '../lib/board';
import { loadContributions } from '../lib/contribute';
import { fetchNews } from '../lib/news';
import { checkTokens, SETTINGS_URL, type TokenState } from '../lib/tokens';
import { recordInterest } from '../lib/model-repo';
import { loadSeen, markSeen } from '../lib/seen';
import { DOCK_IDLE_DEFAULT, dockIdleMs } from '../lib/prefs';
import { fetchPeople } from '../lib/people';
import { fetchResearch } from '../lib/research';
import { INNER, ordered, OUTER, RING_NAME, Row, rowsFor, SECTIONS, SectionId } from '../lib/sections';
import { C, ink, tint } from '../lib/theme';
import { GeekLoader } from '../components/geek-loader';



const HINT_KEY = 'mygeeky.orbitHinted';
type NewsPart = 'headlines' | 'discuss';
const NEWS_PARTS: [NewsPart, string][] = [['headlines', '📰 Headlines'], ['discuss', '💬 Papers & discussions']];
type RepoPart = 'help' | 'rising';
const REPO_PARTS: [RepoPart, string][] = [['help', '🛠 Help out'], ['rising', '📈 Rising']];
type YouPart = 'month' | 'model' | 'badges' | 'more' | 'ideas' | 'admin';
const YOU_PARTS: [YouPart, string][] = [['month', 'My month'], ['model', 'Model'], ['badges', 'Badges'], ['more', 'Settings'], ['ideas', 'Ideas']];

const EMPTY: Partial<Record<SectionId, string>> = {
  live: 'Nothing new around you yet. Pull down to check again.',
  activity: "The people you follow haven't done anything public lately.",
  people: 'No one found for your keywords yet: add a few in You → Your model.',
  news: 'No headlines yet. Pull down to load them.',
  papers: 'No rising papers found yet. Connecting your data repo (You → Model) or adding your ORCID (You → Settings → Start over) finds your exact field.',
  repos: 'No repos yet: your computer finds them (Repos tab there), and they arrive with its next sync.',
  models: 'No trending models yet. Pull down to load them.',
  launches: 'No launches yet. Pull down to load them.',
};

// The planets that live on GitHub, and what adding GitHub would show there (myGeeKy without GitHub).
const NEEDS_GITHUB: Partial<Record<SectionId, string>> = {
  live: 'What the people you follow are building, and who to meet, as it happens.',
  activity: 'What people in your field are building, as it happens.',
  people: "Researchers in your field share their code on GitHub. myGeeKy finds the ones you'd enjoy following. " +
          'Until then, Papers shows the research rising in your field.',
  signals: 'Thank the people whose code you use, and invite collaborators, without words.',
};

function GitHubCard({ why }: { why: string }) {
  return (
    <View style={st.ghCard}>
      <Text style={st.ghTitle}>🔓 Add GitHub to see this</Text>
      <Text style={st.ghWhy}>{why}</Text>
      <View style={st.ghRow}>
        <Pressable onPress={() => router.push('/setup')} style={st.ghAdd} accessibilityLabel="Add GitHub">
          <Text style={st.ghAddText}>Add GitHub</Text>
        </Pressable>
        <Pressable onPress={() => Linking.openURL('https://github.com/signup')}>
          <Text style={st.ghNew}>No account? Create one, free</Text>
        </Pressable>
      </View>
    </View>
  );
}

function RowView({ r, color, isOpen, onPick, isNew = false }: { r: Row; color: string; isOpen: boolean; onPick: () => void; isNew?: boolean }) {
  const [card, setCard] = useState(false);          // an activity's person, unfolded on demand
  return (
    <View style={[st.rowBox, isOpen && st.rowOpen, !isNew && !isOpen && { opacity: 0.72 }]}>
      <Pressable onPress={onPick} style={st.row} accessibilityRole="button" accessibilityLabel={`${r.title}. ${r.sub}`}>
        {r.board ? <BoardRank b={r.board} /> : null}
        {r.avatar ? (
          <Image source={{ uri: `${r.avatar}${r.avatar.includes('?') ? '&' : '?'}s=80` }} style={st.avatar} />
        ) : (
          <View style={[st.letter, { backgroundColor: r.letterBg }]}><Text style={[st.letterText, { color: r.letterFg }]}>{r.letter}</Text></View>
        )}
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={st.title} numberOfLines={isOpen ? undefined : 2}>{isNew ? <Text style={{ color }}>● </Text> : null}{r.title}</Text>
          <Text style={st.sub} numberOfLines={isOpen ? undefined : 1}>{r.sub}</Text>
        </View>
        {r.right ? <Text style={st.right}>{r.right}</Text> : null}
        {r.board ? <Spark values={r.board.spark} trend={r.board.trend} /> : null}
      </Pressable>
      {r.board ? <BoardStats b={r.board} /> : null}
      {isOpen && r.more ? (
        <View style={{ paddingBottom: 8, gap: 6 }}>
          {r.more.text.map((t) => <Text key={t} style={st.sub}>{t}</Text>)}
          {r.more.links.map(([label, url]) => (
            <Pressable key={url} onPress={() => open(url, r.kind)} style={st.issue}><Text style={st.issueText}>{label}</Text></Pressable>
          ))}
        </View>
      ) : null}
      {isOpen && r.kind === 'person' && r.login ? <PersonCard login={r.login} onClose={onPick} /> : null}
      {isOpen && r.kind !== 'person' && card && r.login ? <PersonCard login={r.login} onClose={() => setCard(false)} /> : null}
      {isOpen && r.kind !== 'person' ? (
        <View style={st.actions}>
          <Pressable onPress={() => { if (r.learn) recordInterest(r.learn); open(r.url, r.kind, r.cat, r.explore); }} style={[st.go, { backgroundColor: color }]}>
            <Text style={st.goText}>{r.action}</Text>
          </Pressable>
          {r.login ? (
            <Pressable onPress={() => setCard(!card)} style={st.close} accessibilityLabel={`${r.login} at a glance`}>
              <Ionicons name={card ? 'person' : 'person-outline'} size={18} color={C.text} />
            </Pressable>
          ) : null}
          <Pressable onPress={onPick} style={st.close} accessibilityLabel="Close"><Text style={st.closeText}>×</Text></Pressable>
        </View>
      ) : null}
    </View>
  );
}

const UP = '#34d399';
const DOWN = '#f87171';
const count = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : String(n));

/** The board's rank and movement since the last ranked day (the desktop's MarketRow). */
function BoardRank({ b }: { b: BoardRow }) {
  const [text, color] = b.movement === 'new' ? ['NEW', C.cyan] : typeof b.movement === 'number' && b.movement > 0 ? [`▲${b.movement}`, UP]
    : typeof b.movement === 'number' && b.movement < 0 ? [`▼${-b.movement}`, DOWN] : ['–', C.muted];
  return (
    <View style={{ width: 34, alignItems: 'center' }}>
      <Text style={{ color: C.text, fontWeight: '800', fontSize: 14 }}>#{b.rank}</Text>
      <Text style={{ color, fontWeight: '800', fontSize: 11 }}>{text}</Text>
    </View>
  );
}

/** ★ stars (+ this week) · ↓ downloads/wk (▲ change) · commits/4wk -- coloured as on the desktop. */
function BoardStats({ b }: { b: BoardRow }) {
  return (
    <Text style={[st.sub, { marginTop: -6, marginBottom: 10, marginLeft: 46 }]}>
      ★ {count(b.stars)}{b.stars_week ? <Text style={{ color: b.stars_week > 0 ? UP : DOWN }}> {b.stars_week > 0 ? '+' : ''}{b.stars_week}</Text> : null}
      {b.downloads_week !== null ? <Text> · ↓ {count(b.downloads_week)}/wk{b.downloads_change !== null
        ? <Text style={{ color: b.downloads_change >= 0 ? UP : DOWN }}> {b.downloads_change >= 0 ? '▲' : '▼'}{Math.round(Math.abs(b.downloads_change) * 100)}%</Text> : null}</Text> : null}
      {b.commits_4w !== null ? ` · ${b.commits_4w} commits/4wk` : ''}
    </Text>
  );
}

/** Twelve weeks of downloads (or commits) as a small line, green going up and red going down. */
function Spark({ values, trend }: { values: number[]; trend: 'up' | 'down' | null }) {
  if (values.length < 2) return null;
  const [w, h] = [54, 22];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - 2 - ((v - lo) / (hi - lo || 1)) * (h - 4)}`).join(' ');
  return (
    <Svg width={w} height={h}><Polyline points={pts} fill="none" stroke={trend === 'up' ? UP : trend === 'down' ? DOWN : C.muted} strokeWidth={1.8} /></Svg>
  );
}

export default function Home() {
  const toast = useToast();
  const { settings, token } = useApp();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const user = settings?.username ?? '';
  // You first; without GitHub the planets that would only say "add GitHub" go last (sections.ts ordered)
  const inner = useMemo(() => ordered(INNER, !!user), [user]);
  const DOCK: SectionId[] = useMemo(() => ['you', ...inner, ...OUTER], [inner]);
  const keywords = [...(settings?.keywords ?? []), ...(settings?.topics ?? [])];

  const live = useFeed('live', 0.25, () => user ? fetchLive(user, token) : Promise.resolve({ events: [], following: 0 }));
  const people = useFeed('people', 12, (p) => user ? fetchPeople(user, token, p.weights)
    : Promise.resolve({ followBack: [], field: [] }));
  const headlines = useFeed('headlines', 3, (p) => fetchHeadlines(p.weights));
  const research = useFeed('research', 12, (p) => fetchResearch(p));
  const discuss = useFeed('news-discuss', 3, (p) => fetchNews(p.weights, settings?.exploreShare ?? 0.2));
  const market = useFeed('market-board', 6, async () => (await loadBoard().catch(() => null)) ?? { rows: [], updatedAt: '' });
  const repos = useFeed('repos-contribute', 3, async (p) => {   // from your computers' runs; else popular in your field
    const contribute = await loadContributions().catch(() => null);
    return { contribute, popular: contribute ? [] : await fetchRepos(p.weights, token) };
  });
  const models = useFeed('models', 6, (p) => fetchModels(p.weights, keywords));
  const launches = useFeed('launches', 6, (p) => fetchLaunches(p.weights));
  const feedsOf: Record<SectionId, { loading: boolean; error: string | null; at: string | null; refresh: () => Promise<void> }[]> = {
    live: [live, people], activity: [live], people: [people], signals: [], news: [headlines, discuss], papers: [research],
    repos: [repos, market], models: [models], launches: [launches], you: [], grow: [], chances: [], market: [market], discuss: [discuss],
  };

  // a link can open a planet directly: mygeeky:///home?sel=news&fold=1&open=first
  const params = useLocalSearchParams<{ sel?: string; fold?: string; open?: string; part?: string }>();
  const [sel, setSel] = useState<SectionId>(params.sel && params.sel in SECTIONS ? params.sel as SectionId
    : user ? 'live' : 'papers');                          // without GitHub, start where your field is
  const [collapsed, setCollapsed] = useState(params.fold === '1');
  const [openId, setOpenId] = useState<string | null>(params.open === 'first' ? 'first' : null);
  const [tokenWarn, setTokenWarn] = useState<TokenState | null>(null);   // a token about to stop working
  useEffect(() => { checkTokens().then((t) => setTokenWarn(t.find((x) => x.warn) ?? null)).catch(() => undefined); }, []);
  const [newsPart, setNewsPart] = useState<NewsPart>('headlines');
  const [repoPart, setRepoPart] = useState<RepoPart>('help');
  const [youPart, setYouPart] = useState<YouPart>(params.part === 'badges' || params.part === 'more' || params.part === 'model' ? params.part : 'month');
  // the maker's Admin part: only for the account GitHub says owns the connected data repo (lib/admin.ts)
  const [admin, setAdmin] = useState<string | null>(null);
  useEffect(() => {
    if (sel === 'you') adminLogin().then(setAdmin).catch(() => setAdmin(null));
  }, [sel]);
  const [hint, setHint] = useState(false);
  const [viewH, setViewH] = useState(0);

  useEffect(() => {
    AsyncStorage.getItem(HINT_KEY).then((v) => setHint(!v)).catch(() => undefined);
  }, []);
  const touched = () => {
    if (hint) {
      setHint(false);
      AsyncStorage.setItem(HINT_KEY, '1').catch(() => undefined);
    }
  };

  const data = {
    live: live.data, people: people.data, headlines: headlines.data, research: research.data,
    repos: repos.data, models: models.data, launches: launches.data, market: market.data, discuss: discuss.data,
  };
  // what is new to you (lib/seen.ts): the planets count only those
  const [seen, setSeen] = useState<Set<string> | null>(null);
  const [newHere, setNewHere] = useState<Set<string>>(new Set());   // new when you opened this list: their dots stay
  const shownFor = useRef<SectionId | null>(null);
  useEffect(() => { loadSeen().then(setSeen); }, []);
  useEffect(() => {                  // a promotion since you were last told: said once, a little after opening
    const t = setTimeout(() => rankNews().then((name) => name && toast(`🎖  Promoted to ${name}! See it in You → My month.`)).catch(() => undefined), 6000);
    return () => clearTimeout(t);
  }, [toast]);
  const counts = useMemo(() => {
    const c: Partial<Record<SectionId, number>> = {};
    for (const id of [...INNER, ...OUTER]) c[id] = rowsFor(id, data).filter((r) => !seen?.has(r.id)).length;
    c.repos = (c.repos ?? 0) + rowsFor('market', data).filter((r) => !seen?.has(r.id)).length;
    c.news = (c.news ?? 0) + rowsFor('discuss', data).filter((r) => !seen?.has(r.id)).length;
    return c;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live.data, people.data, headlines.data, research.data, repos.data, models.data, launches.data, market.data, discuss.data, seen]);
  const view: SectionId = sel === 'repos' && repoPart === 'rising' ? 'market' : sel === 'news' && newsPart === 'discuss' ? 'discuss' : sel;
  const listed = rowsFor(view, data);
  // opening a list marks what is in it as seen; what was new keeps its dot until you leave
  const listedKey = listed.map((r) => r.id).join('|');
  useEffect(() => {
    if (!seen || !listed.length) return;
    const fresh = listed.filter((r) => !seen.has(r.id)).map((r) => r.id);
    const same = shownFor.current === view;           // the same list refreshed: keep this visit's dots
    shownFor.current = view;
    Promise.resolve().then(async () => {
      setNewHere((prev) => new Set([...(same ? [...prev] : []), ...fresh]));
      if (fresh.length) setSeen(await markSeen(seen, fresh));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, listedKey, seen === null]);
  const fresh = (r: Row) => newHere.has(r.id);
  // new ones first -- within each part, so the parts (Rising, Tools…) keep their order and headings
  const parts = [...new Set(listed.map((r) => r.section ?? ''))];
  const rows = parts.flatMap((p) => {
    const inPart = listed.filter((r) => (r.section ?? '') === p);
    return [...inPart.filter(fresh), ...inPart.filter((r) => !fresh(r))];
  });
  const firstSeen = parts.length > 1 ? -1 : rows.findIndex((r) => !fresh(r));
  const section = SECTIONS[view];
  const ring = INNER.includes(sel) ? RING_NAME.inner : OUTER.includes(sel) ? RING_NAME.outer : RING_NAME.you;
  const fs = feedsOf[view];
  const loading = fs.some((f) => f.loading);
  const error = fs.map((f) => f.error).find(Boolean) ?? null;
  const at = fs.map((f) => f.at).filter(Boolean).sort()[0] ?? null;

  // the icon dock folds down to a thin handle when you leave it alone; one tap brings it back
  const [dockOpen, setDockOpen] = useState(true);
  const [dockTouched, setDockTouched] = useState(0);
  const fold = () => {                                    // the rings fold away: the dock first, then idle
    if (!collapsed) setDockOpen(true);
    setCollapsed(true);
  };
  const dockUsed = () => setDockTouched((n) => n + 1);
  const [dockIdle, setDockIdle] = useState(DOCK_IDLE_DEFAULT);       // ⚙ Settings → Look
  useEffect(() => { dockIdleMs().then(setDockIdle); }, [sel]);
  useEffect(() => {
    if (!collapsed || !dockOpen || !dockIdle) return;
    const t = setTimeout(() => {
      LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
      setDockOpen(false);
    }, dockIdle);
    return () => clearTimeout(t);
  }, [collapsed, dockOpen, dockTouched, dockIdle]);
  const showDock = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setDockOpen(true);
    dockUsed();
  };

  const pick = (id: SectionId) => {
    dockUsed();
    setSel(id);
    setOpenId(null);
    touched();
  };
  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const y = e.nativeEvent.contentOffset.y;
    if (y > 24 && !collapsed) fold();
    else if (y <= 0 && collapsed) setCollapsed(false);
  };
  const ringsH = collapsed ? 0 : orbitHeight(width);
  const perRow = Math.ceil(DOCK.length / 2);                                   // two rows, so each is a finger wide
  const dot = Math.min(46, Math.floor((width - 12) / perRow) - 14);
  // the rings open on a double tap, so a near miss on a dock button doesn't spin them
  const lastTap = useRef(0);
  const [tapAgain, setTapAgain] = useState(false);
  const spinTap = () => {
    dockUsed();
    const now = Date.now();
    if (now - lastTap.current < 400) {
      lastTap.current = 0;
      setTapAgain(false);
      setCollapsed(false);
    } else {
      lastTap.current = now;
      setTapAgain(true);
      setTimeout(() => setTapAgain(false), 1500);
    }
  };

  return (
    <SafeAreaView style={st.safe} edges={['top']}>
      <View style={st.panel}>
        <View style={st.head}>
          <Text style={st.h1}>{section.label}</Text>
          <Text style={[st.ring, { color: section.color }]}>{ring}</Text>
        </View>
        <Text style={st.about}>{section.about}</Text>
        {tokenWarn ? (
          <Pressable onPress={() => open(SETTINGS_URL)} style={st.warn} accessibilityRole="button">
            <Text style={st.warnText}>⚠ {tokenWarn.message}</Text>
            <Text style={[st.warnText, { fontWeight: '800', marginTop: 2 }]}>Open your GitHub tokens ↗</Text>
          </Pressable>
        ) : null}
        {fs.length ? (
          <Text style={st.meta}>{loading ? 'updating…' : at ? `updated ${timeAgo(at)} · pull down to refresh` : ''}</Text>
        ) : null}
        {error ? <Text style={st.error}>{error}</Text> : null}
        {sel === 'news' ? <View style={{ marginTop: 10 }}><Segments value={newsPart} options={NEWS_PARTS} onChange={setNewsPart} /></View> : null}
        {sel === 'repos' ? <View style={{ marginTop: 10 }}><Segments value={repoPart} options={REPO_PARTS} onChange={setRepoPart} /></View> : null}
        {sel === 'you' ? <View style={{ marginTop: 10 }}><Segments value={youPart} options={admin ? [...YOU_PARTS, ['admin', 'Admin'] as [YouPart, string]] : YOU_PARTS} onChange={setYouPart} /></View> : null}

        <ScrollView
          onLayout={(e) => setViewH(e.nativeEvent.layout.height)}
          onScroll={onScroll} scrollEventThrottle={32}
          contentContainerStyle={[st.list, { minHeight: viewH + (collapsed ? 0 : 60) }]}
          refreshControl={fs.length ? (
            <RefreshControl refreshing={loading} onRefresh={() => fs.forEach((f) => f.refresh())} tintColor={C.pink} colors={[C.pink]} />
          ) : undefined}
        >
          {sel === 'you' ? (
            <View style={{ marginHorizontal: -4 }}>
              {youPart === 'month' ? <MonthView /> : youPart === 'model' ? <ModelPart /> : youPart === 'badges' ? <BadgesPart /> : youPart === 'admin' && admin ? <AdminPart me={admin} /> : youPart === 'ideas' ? <IdeaForm /> : <MorePart />}
            </View>
          ) : !user && NEEDS_GITHUB[sel] ? (
            <GitHubCard why={NEEDS_GITHUB[sel] as string} />
          ) : sel === 'signals' ? (
            <SignalsView />
          ) : sel === 'grow' ? (
            <GrowView />
          ) : sel === 'chances' ? (
            <ChancesView />
          ) : rows.length ? rows.map((r, i) => (<View key={r.id}>
            {r.section && r.section !== rows[i - 1]?.section ? <Text style={st.part}>{r.section}</Text> : null}
            {i === firstSeen ? (
              <Text style={st.seenLine}>{firstSeen === 0 ? '✔ You\'re all caught up · seen earlier' : 'Seen earlier'}</Text>
            ) : null}
            <RowView isNew={fresh(r)} r={r} color={section.color} isOpen={openId === r.id || (openId === 'first' && i === 0)}
                     onPick={() => {
                       setOpenId(openId === r.id ? null : r.id);
                       fold();                            // reading: the rings make room
                       touched();
                     }} />
          </View>)) : (
            loading ? <GeekLoader /> : <Empty>{error ? 'Pull down to try again.' : EMPTY[sel]}</Empty>
          )}
        </ScrollView>
      </View>

      {collapsed && !dockOpen ? (
        <Pressable onPress={showDock} style={st.handle} accessibilityRole="button" accessibilityLabel="Show the sections">
          <View style={st.handleBar} />
          <Ionicons name="chevron-up" size={14} color={C.muted} />
        </Pressable>
      ) : collapsed ? (
        <View style={st.dock}>
          <Pressable onPress={spinTap} style={st.unfold} accessibilityLabel="Show the rings" accessibilityHint="Double-tap"
                     onAccessibilityTap={() => setCollapsed(false)}>
            <Ionicons name="chevron-up" size={16} color={C.muted} />
            <Text style={st.unfoldText}>{tapAgain ? 'Tap again to spin the rings' : 'Double-tap to spin the rings'}</Text>
          </Pressable>
          {[DOCK.slice(0, perRow), DOCK.slice(perRow)].map((row, r) => (
            <View key={r} style={st.dockRow}>
              {row.map((id) => {
                const s = SECTIONS[id];
                const on = sel === id;
                return (
                  <Pressable key={id} onPress={() => pick(id)} style={({ pressed }) => [st.dockBtn, pressed && { opacity: 0.6 }]}
                             accessibilityRole="button" accessibilityLabel={`${s.label}${counts[id] ? `, ${counts[id]} new` : ''}`}>
                    <View style={[st.dockDot, { width: dot, height: dot, borderRadius: dot / 2, borderColor: s.color, backgroundColor: on ? s.color : C.raised }]}>
                      <Ionicons name={s.icon} size={Math.round(dot * 0.46)} color={on ? '#0d0d16' : s.color} />
                    </View>
                    <Text style={[st.dockLabel, on && { color: s.color }]} numberOfLines={1}>{s.label}</Text>
                  </Pressable>
                );
              })}
            </View>
          ))}
        </View>
      ) : (
        <View style={{ height: ringsH }}>
          <Orbit width={width} sel={sel} counts={counts} onSelect={pick} hint={hint} onTouched={touched} inner={inner}
                 youLetter={(user[0] ?? '?').toUpperCase()} />
          <Pressable onPress={() => fold()} style={[st.fold, { top: ringsH - 50 }]} accessibilityLabel="Fold the rings away">
            <Ionicons name="chevron-down" size={20} color={C.muted} />
          </Pressable>
        </View>
      )}
      <View style={{ height: Math.max(insets.bottom, 12) + 8 }} />
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  ghCard: { borderWidth: 1, borderStyle: 'dashed', borderColor: C.violet, borderRadius: 16, padding: 16, marginTop: 8,
            backgroundColor: 'rgba(122,92,255,0.08)' },
  ghTitle: { color: C.text, fontSize: 16, fontWeight: '800' },
  ghWhy: { color: C.muted, fontSize: 14, lineHeight: 20, marginTop: 6 },
  ghRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 14, marginTop: 12 },
  ghAdd: { backgroundColor: '#24292f', borderRadius: 12, paddingHorizontal: 16, paddingVertical: 10 },
  ghAddText: { color: '#fff', fontWeight: '800', fontSize: 14 },
  ghNew: { color: C.cyan, fontSize: 13 },
  safe: { flex: 1, backgroundColor: C.deep },
  panel: { flex: 1, backgroundColor: C.panel, borderBottomLeftRadius: 26, borderBottomRightRadius: 26,
           borderBottomWidth: 1, borderColor: tint(0.10), paddingTop: 12, overflow: 'hidden' },
  head: { flexDirection: 'row', alignItems: 'baseline', gap: 10, paddingHorizontal: 20 },
  h1: { color: C.text, fontSize: 26, fontWeight: '800', letterSpacing: -0.4 },
  ring: { fontSize: 11, fontWeight: '800', letterSpacing: 0.8 },
  about: { color: C.muted, fontSize: 13, lineHeight: 18, paddingHorizontal: 20, marginTop: 2 },
  meta: { color: C.muted, fontSize: 11, paddingHorizontal: 20, marginTop: 4 },
  error: { color: C.red, fontSize: 13, paddingHorizontal: 20, marginTop: 6 },
  list: { paddingHorizontal: 20, paddingTop: 6, paddingBottom: 16 },
  warn: { backgroundColor: 'rgba(248,113,113,0.14)', borderColor: 'rgba(248,113,113,0.5)', borderWidth: 1, borderRadius: 12, padding: 10, marginHorizontal: 20, marginTop: 8 },
  warnText: { color: C.text, fontSize: 13, lineHeight: 18 },
  part: { color: C.muted, fontSize: 11, fontWeight: '800', letterSpacing: 0.8, marginTop: 14, marginBottom: 2 },
  seenLine: { color: C.muted, fontSize: 12, fontWeight: '700', textAlign: 'center', marginTop: 14, marginBottom: 4 },
  rowBox: { borderBottomWidth: 1, borderColor: tint(0.07) },
  rowOpen: { backgroundColor: tint(0.04), marginHorizontal: -12, paddingHorizontal: 12, borderRadius: 14 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 },
  avatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: C.cardHi, alignItems: 'center', justifyContent: 'center' },
  letter: { width: 24, height: 24, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  letterText: { fontSize: 12, fontWeight: '900' },
  title: { color: C.text, fontSize: 15, fontWeight: '700', lineHeight: 20 },
  sub: { color: C.muted, fontSize: 12, marginTop: 3 },
  right: { color: C.muted, fontSize: 12 },
  issue: { backgroundColor: tint(0.07), borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8 },
  issueText: { color: C.text, fontSize: 13 },
  actions: { flexDirection: 'row', gap: 8, paddingBottom: 12 },
  go: { flex: 1, minHeight: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 10 },
  goText: { color: '#0d0d16', fontSize: 14, fontWeight: '800' },
  close: { width: 44, minHeight: 44, borderRadius: 12, backgroundColor: tint(0.08), alignItems: 'center', justifyContent: 'center' },
  closeText: { color: C.text, fontSize: 20 },
  dock: { paddingHorizontal: 6, paddingTop: 2 },
  handle: { height: 34, alignItems: 'center', justifyContent: 'center', gap: 2 },
  handleBar: { width: 44, height: 4, borderRadius: 2, backgroundColor: ink(0.28) },
  unfold: { height: 30, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  unfoldText: { color: C.muted, fontSize: 12, fontWeight: '700' },
  dockRow: { flexDirection: 'row', justifyContent: 'space-between' },
  dockBtn: { flex: 1, minHeight: 64, alignItems: 'center', justifyContent: 'center', paddingVertical: 4 },
  dockLabel: { color: C.muted, fontSize: 10, fontWeight: '600', marginTop: 3 },
  dockDot: { width: 34, height: 34, borderRadius: 17, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  fold: { position: 'absolute', right: 10, width: 44, height: 44, borderRadius: 22, backgroundColor: tint(0.06),
          alignItems: 'center', justifyContent: 'center' },
});
