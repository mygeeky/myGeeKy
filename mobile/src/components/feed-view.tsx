// 🏠 Home (the desktop's gui/feed_ui.py): one scrolling feed of what the other pages already found, new first, then
// "You're all caught up" and what you've seen. Every card says why it's there and leads to its page. It learns from
// taps, 👍/👎 and -- unless switched off -- time on screen (a quick scroll past counts as "not for me"). Nothing here
// goes online: the cards come from lib/feed-store.ts, ranked by lib/feed.ts.
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, Dimensions, Pressable, StyleSheet, Text, View } from 'react-native';
import { GeekLoader } from './geek-loader';
import { Empty, open } from './ui';
import { useApp } from '../lib/app-state';
import { type Item, KINDS, load as loadFeed, record, setDwell } from '../lib/feed';
import { buildFeed } from '../lib/feed-store';
import { recordInterest } from '../lib/model-repo';
import { C } from '../lib/theme';
import { opened as wisepOpened } from '../lib/wisep';

const FIRST = 20, MORE = 15, TICK_MS = 1000, VISIBLE = 0.6;

export function FeedView({ onGo, labelOf, colorOf }: { onGo: (page: string) => void; labelOf: (page: string) => string; colorOf: (page: string) => string }) {
  const { profile } = useApp();
  const [items, setItems] = useState<Item[] | null>(null);
  const [drawn, setDrawn] = useState(FIRST);
  const [dwellOn, setDwellOn] = useState(true);
  const [note, setNote] = useState('');
  const refs = useRef<Record<string, View | null>>({});
  const dwell = useRef<Record<string, number>>({});
  const told = useRef<Set<string>>(new Set());
  const end = useRef<View | null>(null);
  const active = useRef(AppState.currentState === 'active');

  const rebuild = useCallback(() => {
    buildFeed(profile?.weights ?? {}).then((it) => { setItems(it); setDrawn(FIRST); dwell.current = {}; told.current = new Set(); }).catch(() => setItems([]));
  }, [profile?.weights]);
  useEffect(() => { rebuild(); }, [rebuild]);
  useEffect(() => { loadFeed().then((s) => setDwellOn(s.dwell)).catch(() => undefined); }, []);
  useEffect(() => {
    const sub = AppState.addEventListener('change', (s) => { active.current = s === 'active'; });
    return () => sub.remove();
  }, []);

  const learn = (it: Item, what: 'open' | 'up' | 'down' | 'view', secs = 0) => {
    record(it.card.kind, it.card.id, what, secs).catch(() => undefined);
    if (what === 'open' && it.card.page) wisepOpened(it.card.page).catch(() => undefined);   // what you enjoy, WISEP keeps fresh
  };
  // time on screen: once a second, how much of each card shows; a card that showed and left teaches once
  useEffect(() => {
    if (!items?.length) return;
    const h = Dimensions.get('window').height;
    const timer = setInterval(() => {
      if (!active.current) return;
      for (const it of items.slice(0, drawn)) {
        const id = it.card.id, ref = refs.current[id];
        if (!ref || told.current.has(id)) continue;
        ref.measureInWindow((_x, y, _w, height) => {
          if (!height) return;
          const shown = Math.max(0, Math.min(y + height, h) - Math.max(y, 0));
          if (shown / height >= VISIBLE) dwell.current[id] = (dwell.current[id] ?? 0) + TICK_MS / 1000;
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
  }, [items, drawn]);

  if (items === null) return <GeekLoader text="Gathering what's new for you…" />;
  if (!items.length) return <Empty>Nothing yet: Home fills itself from the other pages as they update. Pull down on any page to refresh it.</Empty>;
  const fresh = items.filter((x) => !x.seen).length;
  const firstSeen = items.findIndex((x) => x.seen);
  return (
    <View>
      <View style={st.head}>
        <Text style={st.headText}>{fresh} new{note ? ` · ${note}` : ''}</Text>
        <Pressable onPress={() => { const next = !dwellOn; setDwellOn(next); setDwell(next).catch(() => undefined); }} style={st.pill}
                   accessibilityLabel={dwellOn ? 'Learning from time on screen: on. Tap to switch it off.' : 'Learning from time on screen: off. Tap to switch it on.'}>
          <Text style={st.pillText}>⏱ {dwellOn ? 'learning' : 'off'}</Text>
        </Pressable>
        <Pressable onPress={rebuild} style={st.pill} accessibilityLabel="Refresh Home"><Text style={st.pillText}>↻</Text></Pressable>
      </View>
      {items.slice(0, drawn).map((it, i) => {
        const [label, emoji] = KINDS[it.card.kind] ?? ['', '•'];
        const color = colorOf(it.card.page ?? '');
        const more = labelOf(it.card.page ?? '');
        return (
          <View key={it.card.id}>
            {i === firstSeen ? <Text style={st.caught}>✓ You&apos;re all caught up · seen before, best first</Text> : null}
            <View ref={(r) => { refs.current[it.card.id] = r; }} style={st.card} collapsable={false}>
              <Text style={[st.kind, { color }]}>{emoji}  {label}</Text>
              <Pressable onPress={() => {
                if (it.card.url) open(it.card.url);
                learn(it, 'open');
                recordInterest({ kind: ['repo', 'rising'].includes(it.card.kind) ? 'repo' : it.card.kind === 'person' ? 'person' : 'news',
                  text: `${it.card.title} ${it.card.sub ?? ''}`, topics: it.card.terms ?? [], source: 'home' }).catch(() => undefined);
              }}>
                <Text style={st.title}>{it.card.title}</Text>
              </Pressable>
              {it.card.sub ? <Text style={st.sub}>{it.card.sub}</Text> : null}
              <Text style={st.why}>{it.why}</Text>
              <View style={st.row}>
                {more ? <Pressable onPress={() => onGo(it.card.page ?? '')} style={st.btn}><Text style={st.btnText}>More in {more} ›</Text></Pressable> : null}
                <Pressable onPress={() => { learn(it, 'up'); setNote('thanks: Home learns from that'); }} style={st.btn} accessibilityLabel="More like this"><Text style={st.btnText}>👍</Text></Pressable>
                <Pressable onPress={() => { learn(it, 'down'); setNote('fewer like that from now on'); }} style={st.btn} accessibilityLabel="Fewer like this"><Text style={st.btnText}>👎</Text></Pressable>
              </View>
            </View>
          </View>
        );
      })}
      <View ref={end} collapsable={false} style={{ height: 1 }} />
      {drawn >= items.length ? <Text style={st.caught}>That&apos;s everything for now. New things arrive as the other pages update.</Text> : null}
    </View>
  );
}

const st = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  headText: { color: C.muted, fontSize: 13, flex: 1 },
  pill: { backgroundColor: C.card, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  pillText: { color: C.text, fontSize: 12, fontWeight: '700' },
  card: { backgroundColor: C.card, borderRadius: 14, padding: 12, marginBottom: 10, gap: 3 },
  kind: { fontSize: 11.5, fontWeight: '800' },
  title: { color: C.text, fontSize: 15, fontWeight: '700', lineHeight: 20 },
  sub: { color: C.muted, fontSize: 12.5 },
  why: { color: C.muted, fontSize: 11.5, fontStyle: 'italic', opacity: 0.85 },
  row: { flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap' },
  btn: { backgroundColor: C.card, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5 },
  btnText: { color: C.text, fontSize: 12, fontWeight: '600' },
  caught: { color: C.muted, fontSize: 12.5, fontWeight: '700', marginVertical: 10, textAlign: 'center' },
});
