// 🏠 Home (the desktop's gui/feed_ui.py): one scrolling feed of what the other pages already found, new first, then
// "You're all caught up" and what you've seen. The cards are Neon -- outlined and glowing in their kind's colour (a
// plain outline in the light theme) -- each with what makes it worth a look: a ring counting down a deadline, a
// repo's stars, a dataset's size, a quiz question answered right there. A milestone sits on top when there is one.
// It learns from taps, ♡ (Home and your Model), 🔖 Save (kept in Saved, teaches like ♡), ✕ (fewer like this, with
// Undo) and -- unless switched off -- time on screen (a quick scroll past counts as "not for me"). Nothing here goes
// online: the cards come from lib/feed-store.ts, ranked by lib/feed.ts.
import { useCallback, useEffect, useRef, useState } from 'react';
import { useIsFocused } from 'expo-router';
import { AppState, Dimensions, Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { GeekLoader } from './geek-loader';
import { Empty, open } from './ui';
import { useApp } from '../lib/app-state';
import { type Card, type Item, type Saved, caughtUp, daysLeft, factsLine, interestKind, interestText, KIND_COLORS, KINDS,
  load as loadFeed, milestone, READ_SECONDS, record, RING_DAYS, setDwell, toggleSave } from '../lib/feed';
import { buildFeed } from '../lib/feed-store';
import { recordInterest } from '../lib/model-repo';
import { C } from '../lib/theme';
import { opened as wisepOpened } from '../lib/wisep';

const FIRST = 20, MORE = 15, TICK_MS = 1000, VISIBLE = 0.6, LIKED = '#ff6f91';
const today = () => new Date().toISOString().slice(0, 10);
type Shown = { card: Card; why: string; seen: boolean };

function learn(it: { card: Card }, what: 'open' | 'up' | 'down' | 'view', secs = 0) {
  record(it.card.kind, it.card.id, what, secs).catch(() => undefined);
  if (what === 'open' && it.card.page) wisepOpened(it.card.page).catch(() => undefined);   // what you enjoy, WISEP keeps fresh
}
const teachModel = (c: Card) =>
  recordInterest({ kind: 'like', text: interestText(c), topics: c.terms ?? [], source: 'home' }).catch(() => undefined);

/** The kind's colour, darkened in the light theme so its words stay readable (gui/feed_ui.py kind_color). */
function kindColor(kind: string): string {
  const hex = KIND_COLORS[kind] ?? '#a78bfa';
  if (C.dark) return hex;
  const n = parseInt(hex.slice(1), 16);
  const ch = (v: number) => Math.round(v * 0.6).toString(16).padStart(2, '0');
  return `#${ch(n >> 16)}${ch((n >> 8) & 255)}${ch(n & 255)}`;
}
const alpha = (hex: string, a: number) => `${hex}${Math.round(a * 255).toString(16).padStart(2, '0')}`;
/** `a` with a share `t` of `b`, solid: a see-through card would let Android draw its glow's shadow inside it. */
function mix(a: string, b: string, t: number): string {
  const x = parseInt(a.slice(1, 7), 16), y = parseInt(b.slice(1, 7), 16);
  const ch = (sh: number) => Math.round(((x >> sh) & 255) * (1 - t) + ((y >> sh) & 255) * t).toString(16).padStart(2, '0');
  return `#${ch(16)}${ch(8)}${ch(0)}`;
}

function Ring({ days, color }: { days: number; color: string }) {
  const r = 20, len = 2 * Math.PI * r, part = Math.max(0.04, Math.min(1, days / RING_DAYS));
  return (
    <View style={st.ring} accessibilityLabel={days === 0 ? 'closes today' : `${days} days left`}>
      <Svg width={50} height={50} style={{ transform: [{ rotate: '-90deg' }] }}>
        <Circle cx={25} cy={25} r={r} stroke={C.line} strokeWidth={4.5} fill="none" />
        <Circle cx={25} cy={25} r={r} stroke={color} strokeWidth={4.5} fill="none" strokeLinecap="round" strokeDasharray={`${len * part} ${len}`} />
      </Svg>
      <View style={st.ringText}><Text style={st.ringNum}>{days === 0 ? '!' : days}</Text><Text style={st.ringUnit}>{days === 0 ? 'today' : 'days'}</Text></View>
    </View>
  );
}

function Quiz({ card, onAnswer }: { card: Card; onAnswer: () => void }) {
  const [picked, setPicked] = useState<number | null>(null);
  const f = card.facts ?? {};
  return (
    <View style={{ gap: 6 }}>
      {(f.options as string[]).map((o, i) => {
        const right = picked !== null && i === f.answer, wrong = picked !== null && i === picked && i !== f.answer;
        return (
          <Pressable key={i} onPress={() => { if (picked === null) { setPicked(i); onAnswer(); } }}
                     style={[st.choice, right && st.right, wrong && st.wrong]} accessibilityRole="button">
            <Text style={st.choiceText}>{o}</Text>
          </Pressable>
        );
      })}
      {picked !== null ? <Text style={st.sub}>{picked === f.answer ? '✓ Right! ' : '✗ Not quite. '}{String(f.why ?? '')}</Text> : null}
    </View>
  );
}

type CardProps = { it: Shown; hero?: boolean; savedAt?: string; liked: boolean; saved: boolean; onLike: () => void; onSave: () => void;
  onDismiss: () => void; onOpen: () => void; onMore: () => void; moreLabel: string; onQuiz: () => void; refFn?: (v: View | null) => void };

function NeonCard({ it, hero, savedAt, liked, saved, onLike, onSave, onDismiss, onOpen, onMore, moreLabel, onQuiz, refFn }: CardProps) {
  const c = it.card, [label, emoji] = KINDS[c.kind] ?? ['', '•'], color = kindColor(c.kind), days = daysLeft(c), chips = factsLine(c);
  const title = <Text style={[st.title, hero && st.heroTitle]}>{c.title}</Text>;
  const sub = c.sub ? <Text style={st.sub}>{c.sub}</Text> : null;
  // a tap anywhere on a card with a link opens it (its buttons and quiz answers take their own taps)
  return (
    <Pressable ref={refFn} collapsable={false} onPress={c.url ? onOpen : undefined} disabled={!c.url}
               accessibilityRole={c.url ? 'link' : undefined}
               style={({ pressed }) => [st.card, { borderColor: alpha(color, C.dark ? 0.8 : 0.65) }, C.dark && { shadowColor: color },
                  { backgroundColor: mix(C.sheet, color, pressed ? 0.12 : hero ? 0.14 : 0.03) }]}>
      <Text style={[st.kind, { color }]}>{emoji}  {label}</Text>
      {days !== null
        ? <View style={st.row}><Ring days={days} color={color} /><View style={{ flex: 1, gap: 2 }}>{title}{sub}</View></View>
        : <>{title}{sub}</>}
      {c.kind === 'quiz' && Array.isArray(c.facts?.options) ? <Quiz card={c} onAnswer={onQuiz} /> : null}
      {chips.length ? <View style={st.chips}>{chips.map((x) => <Text key={x} style={[st.chip, { backgroundColor: alpha(color, 0.18) }]}>{x}</Text>)}</View> : null}
      <Text style={st.why}>{savedAt ? `saved ${savedAt}` : it.why}</Text>
      <View style={st.acts}>
        <Pressable onPress={onLike} style={st.act} accessibilityLabel="More like this (Home and your Model learn)"><Text style={[st.actText, liked && { color: LIKED }]}>{liked ? '♥' : '♡'}</Text></Pressable>
        <Pressable onPress={onSave} style={st.act} accessibilityLabel={saved ? 'Take out of Saved' : 'Save for later'}><Text style={st.actText}>{saved ? '🔖✓' : '🔖'}</Text></Pressable>
        <Pressable onPress={onDismiss} style={st.act} accessibilityLabel="Fewer like this"><Text style={st.actText}>✕</Text></Pressable>
        <View style={{ flex: 1 }} />
        {moreLabel ? <Pressable onPress={onMore} style={st.act} accessibilityLabel={`Go to ${moreLabel}`}><Text style={st.more}>See all in {moreLabel}</Text></Pressable> : null}
        {c.url ? (
          <Pressable onPress={onOpen} style={[st.open, { borderColor: color, backgroundColor: alpha(color, 0.18) }]} accessibilityLabel="Open it">
            <Text style={[st.openText, { color }]}>Open ↗</Text>
          </Pressable>
        ) : null}
      </View>
    </Pressable>
  );
}

export function FeedView({ onGo, labelOf }: { onGo: (page: string) => void; labelOf: (page: string) => string; colorOf?: (page: string) => string }) {
  const { profile } = useApp();
  const [items, setItems] = useState<Item[] | null>(null);
  const [drawn, setDrawn] = useState(FIRST);
  const [dwellOn, setDwellOn] = useState(true);
  const [note, setNote] = useState('');
  const [liked, setLiked] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<Saved[]>([]);
  const [gone, setGone] = useState<Set<string>>(new Set());
  const [showSaved, setShowSaved] = useState(false);
  const refs = useRef<Record<string, View | null>>({});
  const dwell = useRef<Record<string, number>>({});
  const told = useRef<Set<string>>(new Set());
  const pendingDown = useRef<Record<string, Card>>({});        // ✕ waits until you leave, so Undo can take it back
  const end = useRef<View | null>(null);
  const active = useRef(AppState.currentState === 'active');
  const focused = useIsFocused();                       // another screen on top: Home isn't being read
  const byId = useRef<Record<string, Item>>({});

  // leaving Home (or refreshing it) isn't skipping what's on screen: only a card read long enough teaches; a ✕ not
  // undone is learned now
  const flush = useCallback(() => {
    for (const [id, secs] of Object.entries(dwell.current)) {
      if (secs >= READ_SECONDS && byId.current[id] && !told.current.has(id)) { told.current.add(id); learn(byId.current[id], 'view', secs); }
    }
    dwell.current = {};
    for (const c of Object.values(pendingDown.current)) { told.current.add(c.id); learn({ card: c }, 'down'); }
    pendingDown.current = {};
  }, []);

  const rebuild = useCallback(() => {
    buildFeed(profile?.weights ?? {}).then((it) => {
      flush();
      byId.current = Object.fromEntries(it.map((x) => [x.card.id, x]));
      setItems(it); setDrawn(FIRST); setGone(new Set()); setShowSaved(false); told.current = new Set();
    }).catch(() => setItems([]));
  }, [profile?.weights, flush]);
  useEffect(() => { rebuild(); }, [rebuild]);
  useEffect(() => { loadFeed().then((s) => { setDwellOn(s.dwell); setSaved(s.saved); }).catch(() => undefined); }, []);
  useEffect(() => {
    const sub = AppState.addEventListener('change', (s) => { active.current = s === 'active'; if (!active.current) flush(); });
    return () => { sub.remove(); flush(); };
  }, [flush]);
  useEffect(() => { if (!focused) flush(); }, [focused, flush]);

  // time on screen: once a second, how much of each card shows; a card that showed and left teaches once
  useEffect(() => {
    if (!items?.length || !focused || showSaved) return;
    const h = Dimensions.get('window').height;
    const timer = setInterval(() => {
      if (!active.current) return;
      for (const it of items.slice(0, drawn)) {
        const id = it.card.id, ref = refs.current[id];
        if (!ref || told.current.has(id) || pendingDown.current[id]) continue;
        ref.measureInWindow((_x, y, _w, height) => {
          if (!height) return;
          const shown = Math.max(0, Math.min(y + height, h) - Math.max(y, 0));
          // first seen counts 0 s, so a quick pass is a skip
          if (shown / height >= VISIBLE) dwell.current[id] = id in dwell.current ? dwell.current[id] + TICK_MS / 1000 : 0;
          else if (id in dwell.current) {
            told.current.add(id);
            learn(it, 'view', dwell.current[id]);
            delete dwell.current[id];
          }
        });
      }
      end.current?.measureInWindow((_x, y) => { if (y < h + 200 && drawn < items.length) setDrawn((d) => d + MORE); });   // near the end: more
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [items, drawn, focused, showSaved]);

  const savedIds = new Set(saved.map((x) => x.card.id));
  const like = (c: Card) => {
    if (liked.has(c.id)) { setLiked((s) => { const n = new Set(s); n.delete(c.id); return n; }); return; }
    setLiked((s) => new Set(s).add(c.id));
    learn({ card: c }, 'up');
    if (!savedIds.has(c.id)) teachModel(c);
    setNote('thanks: Home and your Model learn from that');
  };
  const save = (c: Card) => {
    toggleSave(c, today()).then((now) => {
      if (now && !liked.has(c.id)) teachModel(c);
      setNote(now ? 'saved for later: 🔖 above' : 'taken out of Saved');
      return loadFeed();
    }).then((s) => setSaved(s.saved)).catch(() => undefined);
  };
  const dismiss = (c: Card) => { pendingDown.current[c.id] = c; setGone((s) => new Set(s).add(c.id)); };
  const undo = (c: Card) => { delete pendingDown.current[c.id]; setGone((s) => { const n = new Set(s); n.delete(c.id); return n; }); };
  const openCard = (it: Shown) => {
    if (it.card.url) open(it.card.url);
    learn(it, 'open');
    recordInterest({ kind: interestKind(it.card), text: interestText(it.card), topics: it.card.terms ?? [], source: 'home' }).catch(() => undefined);
  };
  const cardProps = (it: Shown) => ({
    it, liked: liked.has(it.card.id), saved: savedIds.has(it.card.id), onLike: () => like(it.card), onSave: () => save(it.card),
    onDismiss: () => dismiss(it.card), onOpen: () => openCard(it), onMore: () => onGo(it.card.page ?? ''),
    moreLabel: labelOf(it.card.page ?? ''), onQuiz: () => learn(it, 'open'),
  });

  if (items === null) return <GeekLoader text="Gathering what's new for you…" />;
  const fresh = items.filter((x) => !x.seen);
  const firstSeen = items.findIndex((x) => x.seen);
  const mark = milestone(fresh.map((x) => x.card), today());
  const caught = caughtUp(fresh.length, liked.size, saved.length);
  const head = (
    <View style={st.head}>
      <Text style={st.headText}>{showSaved ? 'saved for later' : `${fresh.length} new${note ? ` · ${note}` : ''}`}</Text>
      <Pressable onPress={() => setShowSaved((v) => !v)} style={[st.pill, showSaved && { backgroundColor: C.violet }]} accessibilityLabel="Saved for later">
        <Text style={st.pillText}>🔖{saved.length ? ` ${saved.length}` : ''}</Text>
      </Pressable>
      <Pressable onPress={() => { const next = !dwellOn; setDwellOn(next); setDwell(next).catch(() => undefined); }} style={st.pill}
                 accessibilityLabel={dwellOn ? 'Learning from time on screen: on. Tap to switch it off.' : 'Learning from time on screen: off. Tap to switch it on.'}>
        <Text style={st.pillText}>⏱ {dwellOn ? 'learning' : 'off'}</Text>
      </Pressable>
      <Pressable onPress={rebuild} style={st.pill} accessibilityLabel="Refresh Home"><Text style={st.pillText}>↻</Text></Pressable>
    </View>
  );
  if (showSaved) {
    return (
      <View>
        {head}
        <Text style={st.caught}>{saved.length ? `🔖 Saved for later · ${saved.length}` : '🔖 Nothing saved yet: tap 🔖 on a card to keep it here.'}</Text>
        {saved.map((x) => <NeonCard key={x.card.id} savedAt={x.at} {...cardProps({ card: x.card, why: '', seen: true })} />)}
      </View>
    );
  }
  if (!items.length) return <Empty>Nothing yet: Home fills itself from the other pages as they update. Pull down on any page to refresh it.</Empty>;
  return (
    <View>
      {head}
      {mark ? (
        <Pressable onPress={() => onGo(mark.page)} style={st.milestone}>
          <Text style={st.markEmoji}>{mark.emoji}</Text>
          <View style={{ flex: 1 }}><Text style={st.markTitle}>{mark.title}</Text><Text style={st.sub}>{mark.sub} ›</Text></View>
        </Pressable>
      ) : null}
      {items.slice(0, drawn).map((it, i) => (
        <View key={it.card.id}>
          {i === firstSeen ? <><Text style={st.caught}>{caught}</Text><Text style={st.below}>Below: seen before, best first</Text></> : null}
          {gone.has(it.card.id) ? (
            <View style={st.gone}>
              <Text style={[st.sub, { flex: 1 }]}>Fewer “{KINDS[it.card.kind]?.[0] ?? 'these'}” cards from now on</Text>
              <Pressable onPress={() => undo(it.card)} accessibilityRole="button"><Text style={st.undo}>Undo</Text></Pressable>
            </View>
          ) : (
            <NeonCard hero={i === 0 && !it.seen} refFn={(r) => { refs.current[it.card.id] = r; }} {...cardProps(it)} />
          )}
        </View>
      ))}
      <View ref={end} collapsable={false} style={{ height: 1 }} />
      {drawn >= items.length && firstSeen === -1 ? <Text style={st.caught}>{caught}</Text> : null}
      {drawn >= items.length ? <Text style={st.below}>New things arrive as the other pages update.</Text> : null}
    </View>
  );
}

const st = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  headText: { color: C.muted, fontSize: 13, flex: 1 },
  pill: { backgroundColor: C.card, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  pillText: { color: C.text, fontSize: 12, fontWeight: '700' },
  card: { borderRadius: 14, borderWidth: 1.5, padding: 12, paddingBottom: 6, marginBottom: 12, gap: 5,
    shadowOpacity: 0.55, shadowRadius: 9, shadowOffset: { width: 0, height: 0 }, elevation: C.dark ? 6 : 0 },
  kind: { fontSize: 11.5, fontWeight: '800' },
  title: { color: C.text, fontSize: 15, fontWeight: '700', lineHeight: 20 },
  heroTitle: { fontSize: 18, fontWeight: '800', lineHeight: 23 },
  sub: { color: C.muted, fontSize: 12.5 },
  row: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  ring: { width: 50, height: 50 },
  ringText: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, alignItems: 'center', justifyContent: 'center' },
  ringNum: { color: C.text, fontSize: 15, fontWeight: '800', lineHeight: 17 },
  ringUnit: { color: C.muted, fontSize: 9 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 5 },
  chip: { color: C.text, fontSize: 11.5, fontWeight: '600', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 2, overflow: 'hidden' },
  choice: { backgroundColor: C.card, borderRadius: 10, borderWidth: 1, borderColor: 'transparent', paddingHorizontal: 10, paddingVertical: 8 },
  choiceText: { color: C.text, fontSize: 13.5 },
  right: { backgroundColor: 'rgba(74,222,128,0.18)', borderColor: C.green },
  wrong: { backgroundColor: 'rgba(248,113,113,0.15)', borderColor: C.red },
  why: { color: C.muted, fontSize: 11.5, fontStyle: 'italic', opacity: 0.85 },
  acts: { flexDirection: 'row', alignItems: 'center', gap: 2, marginTop: 2 },
  act: { paddingHorizontal: 8, paddingVertical: 6, borderRadius: 8 },
  actText: { color: C.muted, fontSize: 16 },
  more: { color: C.muted, fontSize: 12 },
  open: { borderWidth: 1, borderRadius: 9, paddingHorizontal: 12, paddingVertical: 5, marginLeft: 2 },
  openText: { fontSize: 13, fontWeight: '800' },
  milestone: { flexDirection: 'row', gap: 10, alignItems: 'center', borderRadius: 14, padding: 12, marginBottom: 12, backgroundColor: 'rgba(255,111,216,0.18)' },
  markEmoji: { fontSize: 24 },
  markTitle: { color: C.text, fontSize: 14, fontWeight: '800' },
  gone: { flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderStyle: 'dashed', borderColor: C.line, borderRadius: 12, padding: 10, marginBottom: 12 },
  undo: { color: C.violet, fontWeight: '800', fontSize: 13 },
  caught: { color: C.text, fontSize: 13.5, fontWeight: '800', marginTop: 10, textAlign: 'center' },
  below: { color: C.muted, fontSize: 12, marginBottom: 10, textAlign: 'center' },
});
