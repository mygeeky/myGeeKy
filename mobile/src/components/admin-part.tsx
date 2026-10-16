// 🛠 Admin, the maker's part of "You" (the desktop's admin tab): adoption, listings to review, quizzes, the
// ideas inbox, people to invite and keywords to teach. Locked behind the phone's own fingerprint, face or PIN
// every time it opens, and again whenever the app goes to the background. What you do here is sent as one
// line each to admin_actions.jsonl and applied by your computers at their next sync; why, and what never
// comes to the phone: lib/admin.ts.
import * as Clipboard from 'expo-clipboard';
import * as LocalAuthentication from 'expo-local-authentication';
import { useCallback, useEffect, useState } from 'react';
import { AppState, Image, Linking, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { StatTiles } from './model-plots';
import { Card, Empty, open, s, Section, timeAgo } from './ui';
import {
  act, type Action, type AdminData, type Candidate, deadlineText, EDIT_FIELDS, funnel, IDEA_KINDS, invite, INVITE_DAILY_LIMIT,
  invitedToday, loadAdmin, loadListings, pendingActions, type Person, prospects, QUIZ_GOOD, QUIZ_READY, quizStatus, withPending,
} from '../lib/admin';
import { loadLists } from '../lib/curated';
import { C, tint } from '../lib/theme';

type Loaded = {
  data: AdminData; pending: Action[];
  listings: Awaited<ReturnType<typeof loadListings>>; quiz: Awaited<ReturnType<typeof quizStatus>>;
};
const KIND_EMOJI: Record<string, string> = { jobs: '💼', funding: '💰', conferences: '🎤' };

export function AdminPart({ me }: { me: string }) {
  const [unlocked, setUnlocked] = useState(false);
  const [note, setNote] = useState('');
  const [got, setGot] = useState<Loaded | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastInvited, setLastInvited] = useState('');

  const unlock = useCallback(async () => {
    setNote('');
    try {
      const level = await LocalAuthentication.getEnrolledLevelAsync();
      if (level === LocalAuthentication.SecurityLevel.NONE) {
        setNote('This phone has no screen lock, so Admin stays closed. Set a PIN, pattern or fingerprint in the phone\'s settings first.');
        return;
      }
      const r = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Open myGeeKy admin', cancelLabel: 'Cancel', disableDeviceFallback: false,   // fingerprint/face, or the PIN
      });
      if (!r.success) { setNote('Not unlocked.'); return; }
      setUnlocked(true);
    } catch {
      setNote('The phone could not check it is you, so Admin stays closed.');
    }
  }, []);

  // locked again the moment the app leaves the screen
  useEffect(() => {
    const sub = AppState.addEventListener('change', (st) => { if (st !== 'active') { setUnlocked(false); setGot(null); } });
    return () => sub.remove();
  }, []);
  useEffect(() => { Promise.resolve().then(unlock); }, [unlock]);             // after this render, not inside it

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [data, pending, lists] = await Promise.all([loadAdmin(), pendingActions(), loadLists().catch(() => null)]);
      if (!data) {
        setGot(null);
        setNote('Nothing to show: admin_prospects.json is not in your data repo yet, or this is not the maker\'s account.');
        return;
      }
      const [listings, quiz] = await Promise.all([loadListings(pending), quizStatus(lists)]);
      setGot({ data, pending, listings, quiz });
    } catch (e) {
      setNote(e instanceof Error ? e.message : 'Could not read your data repo.');
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { if (unlocked) Promise.resolve().then(refresh); }, [unlocked, refresh]);

  /** One action: sent at once, shown as done straight away, applied by your computers at their next sync. */
  const doing = async (a: Omit<Action, 'id' | 'at'>, said = '') => {
    try {
      await act(a);
      setNote(said);
    } catch (e) {
      setNote(`${e instanceof Error ? e.message : 'Not sent.'} It is kept on the phone and goes with the next one.`);
    }
    await refresh();
  };

  if (!unlocked) {
    return (
      <View style={a.locked}>
        <Text style={a.lockIcon}>🔒</Text>
        <Text style={a.lockTitle}>Admin is locked</Text>
        <Text style={s.small}>Only for the maker, and only after the phone checks it is you.</Text>
        <Pressable onPress={unlock} style={a.unlock} accessibilityRole="button"><Text style={a.unlockText}>Unlock</Text></Pressable>
        {note ? <Text style={[s.small, { color: C.red, textAlign: 'center' }]}>{note}</Text> : null}
      </View>
    );
  }
  if (!got) return <Text style={s.small}>{loading ? 'Reading your data repo…' : note}</Text>;

  const { data, pending, listings, quiz } = got;
  const people = withPending(data.people, pending);
  const ad = data.adoption;
  const f = funnel(people);
  const today = invitedToday(people);
  const fmt = (v: number | null) => (v === null ? '–' : String(v));
  const mark = async (p: Person, status: 'invited' | 'declined' | 'new') => {
    if (status === 'invited' && today >= INVITE_DAILY_LIMIT) {
      setNote(`That's ${INVITE_DAILY_LIMIT} invites today. Pace it: try tomorrow.`);
      return false;
    }
    await doing({ kind: 'prospect', login: p.login, status },
      status === 'invited' ? `${p.login} marked as invited. Didn't send it?` : status === 'new' ? `${p.login} is back on the list.` : '');
    setLastInvited(status === 'invited' ? p.login : '');
    return true;
  };
  return (
    <>
      <View style={[s.row, { alignItems: 'center', justifyContent: 'space-between' }]}>
        <Text style={[s.small, { flex: 1 }]}>{data.updatedAt ? `updated ${timeAgo(data.updatedAt)} on your computer` : ''}
          {pending.length ? ` · ${pending.length} waiting for your computer` : ''}</Text>
        {lastInvited ? (
          <Text style={a.link} onPress={() => { const p = people.find((x) => x.login === lastInvited); if (p) mark(p, 'new'); }}>Undo</Text>
        ) : null}
        <Text style={[a.link, { marginLeft: 14 }]} onPress={loading ? undefined : refresh}>{loading ? 'Refreshing…' : 'Refresh'}</Text>
      </View>
      {note ? <Text style={[s.small, { color: C.amber, marginTop: 4 }]}>{note}</Text> : null}

      <Section>📈 ADOPTION</Section>
      <StatTiles tiles={[[fmt(ad.pypi_week), 'PyPI / week'], [fmt(ad.installer_downloads), 'installs (.exe)'],
        [fmt(ad.stars), 'stars'], [fmt(ad.signals_users), 'on Signals']]} />
      <Text style={[s.small, { marginTop: 6 }]}>
        Invites: {f.invited} sent · {f.joined} joined{f.invited ? ` (${Math.round((100 * f.joined) / f.invited)}%)` : ''} · {f.new} to
        consider · {today}/{INVITE_DAILY_LIMIT} today
      </Text>

      <Section>🎯 LISTINGS TO REVIEW</Section>
      <Listings listings={listings} onStatus={(c, status, item) => doing({ kind: 'listing', id_listing: c.id, status, item },
        status === 'accepted' ? `${c.item.title} accepted: it goes online when you press Publish on your computer.` : '')} />

      <Section>📝 QUIZZES</Section>
      <Quizzes quiz={quiz} />

      <Section>📬 IDEAS INBOX</Section>
      {data.inbox.length ? data.inbox.slice(0, 15).map((i) => (
        <Card key={i.number} onPress={i.url ? () => open(i.url) : undefined}>
          <Text style={s.name}>{IDEA_KINDS[i.kind] ?? '💡'} {i.title}</Text>
          <Text style={s.small}>#{i.number} · {i.author} · {i.created_at ? timeAgo(i.created_at) : ''} · 💬 {i.comments} · 👍 {i.reactions}</Text>
        </Card>
      )) : <Empty>No ideas yet. They arrive from the 💡 button in everyone&apos;s panel.</Empty>}

      <Section>🎯 PEOPLE TO INVITE</Section>
      <Text style={s.small}>Ranked by how likely they are to want myGeeKy. Nothing is ever sent from here: Email opens it filled
        in for you to send, at most {INVITE_DAILY_LIMIT} a day.</Text>
      {prospects(people).length ? prospects(people).slice(0, 25).map((p) => (
        <Prospect key={p.login} p={p} me={me} onMark={(st) => mark(p, st)} onNote={setNote} />
      )) : <Empty>No prospects yet: click Refresh on your computer.</Empty>}

      <Section>🔤 KEYWORDS TO TEACH</Section>
      <Text style={s.small}>
        {data.keywordRequests.length
          ? `${data.keywordRequests.slice(0, 30).map((r) => `${r.word}${r.people ? ` (${r.people} on Signals)` : ''}${r.suggested ? ` (${r.suggested} suggested)` : ''}`).join(' · ')}\nTeach them on your computer: mygeeky admin keywords build, then publish a release.`
          : 'No unknown keywords yet. They come from beacons and from the suggest button.'}
      </Text>
      <Text style={[s.small, { marginTop: 12 }]}>On your computer only: finding listings (🔎 Find, 📋 Paste, 📧 alerts), 🚀 Publish, and writing
        or spot-checking quizzes. They need its DeepSeek key, mailbox password or push rights, and those never come to the phone.</Text>
    </>
  );
}

function Listings({ listings, onStatus }: {
  listings: Loaded['listings']; onStatus: (c: Candidate, status: 'accepted' | 'rejected' | 'new', item?: Record<string, unknown>) => void;
}) {
  const [editing, setEditing] = useState<Candidate | null>(null);
  if (!listings) return <Empty>No listings to review yet: find some on your computer (🔎 Find new listings), and they arrive here after its next sync.</Empty>;
  return (
    <>
      {listings.accepted.length ? (
        <Text style={s.small}>{listings.accepted.length} accepted, waiting for 🚀 Publish on your computer:</Text>
      ) : null}
      {listings.accepted.map((c) => (
        <View key={c.id} style={[s.row, { alignItems: 'center', marginTop: 4 }]}>
          <Text style={[s.small, { flex: 1, color: C.text }]} numberOfLines={1}>✅ {KIND_EMOJI[c.kind]} {String(c.item.title ?? '')}</Text>
          <Text style={a.link} onPress={() => onStatus(c, 'new')}>Undo</Text>
        </View>
      ))}
      {listings.toReview.length ? listings.toReview.map((c) => {
        const sure = Math.round(100 * c.score);
        const color = sure >= 70 ? C.green : sure >= 45 ? C.amber : C.red;
        const it = c.item;
        const facts = [it.org, it.place, deadlineText(c.daysLeft), it.deadline ? `deadline ${it.deadline}` : '', it.amount, it.who]
          .filter((x) => typeof x === 'string' && x).join(' · ');
        return (
          <Card key={c.id}>
            <View style={[s.row, { alignItems: 'flex-start' }]}>
              <Text style={[s.name, { flex: 1 }]} onPress={() => typeof it.url === 'string' && open(it.url)}>{KIND_EMOJI[c.kind]} {String(it.title ?? '')}</Text>
              <Text style={[a.sure, { color, backgroundColor: `${color}22` }]}>{sure}% sure</Text>
            </View>
            {facts ? <Text style={s.small}>{facts}</Text> : null}
            {it.summary ? <Text style={[s.small, { color: C.text }]}>{String(it.summary)}</Text> : null}
            {c.quote ? <Text style={[s.small, { fontStyle: 'italic' }]}>“{c.quote}”</Text> : null}
            <Text style={[s.small, { fontSize: 11 }]}>{c.checks.map(([ok, t]) => `${ok ? '✓' : '✗'} ${t}`).join('   ')}{c.source ? `   · from ${c.source}` : ''}</Text>
            <View style={a.actions}>
              <Pressable onPress={() => onStatus(c, 'accepted')} style={[a.btn, a.accent]}><Text style={a.btnText}>✓ Accept</Text></Pressable>
              <Pressable onPress={() => setEditing(c)} style={a.btn}><Text style={a.btnText}>✏️ Edit</Text></Pressable>
              <Pressable onPress={() => onStatus(c, 'rejected')} style={a.btn}><Text style={a.btnText}>✕ Reject</Text></Pressable>
            </View>
          </Card>
        );
      }) : <Empty>Nothing new to review.</Empty>}
      {editing ? <EditListing c={editing} onClose={() => setEditing(null)} onAccept={(item) => { onStatus(editing, 'accepted', item); setEditing(null); }} /> : null}
    </>
  );
}

/** The desktop's "Edit, then accept": the same fields; your computer checks them again before they count. */
function EditListing({ c, onClose, onAccept }: { c: Candidate; onClose: () => void; onAccept: (item: Record<string, unknown>) => void }) {
  const fields = EDIT_FIELDS[c.kind];
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(fields.map((f) =>
    [f, f === 'keywords' ? (Array.isArray(c.item.keywords) ? c.item.keywords.join(', ') : '') : String(c.item[f] ?? '')])));
  const [problem, setProblem] = useState('');
  const accept = () => {
    const bad = (['deadline', 'starts', 'ends'] as const).find((f) => values[f] && !/^\d{4}-\d{2}-\d{2}$/.test(values[f].trim()));
    if (!values.url?.trim().startsWith('https://') || bad) {
      setProblem("Something isn't right: the link must start with https:// and dates look like 2026-12-31.");
      return;
    }
    const item: Record<string, unknown> = Object.fromEntries(fields.map((f) => [f, values[f].trim()]));
    item.keywords = values.keywords.split(',').map((k) => k.trim()).filter(Boolean);
    onAccept(item);
  };
  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={a.backdrop} onPress={onClose} />
      <View style={a.sheet}>
        <Text style={a.sheetTitle}>Edit, then accept</Text>
        <ScrollView keyboardShouldPersistTaps="handled">
          {fields.map((f) => (
            <View key={f} style={{ marginBottom: 8 }}>
              <Text style={s.small}>{f.charAt(0).toUpperCase() + f.slice(1)}{['deadline', 'starts', 'ends'].includes(f) ? ' (YYYY-MM-DD)' : f === 'keywords' ? ' (comma separated)' : ''}</Text>
              <TextInput style={a.input} value={values[f]} onChangeText={(v) => setValues({ ...values, [f]: v })} autoCapitalize="none"
                         autoCorrect={false} multiline={f === 'summary'} placeholderTextColor={C.muted} />
            </View>
          ))}
          {problem ? <Text style={[s.small, { color: C.red }]}>{problem}</Text> : null}
          <View style={[a.actions, { justifyContent: 'flex-end', marginBottom: 20 }]}>
            <Pressable onPress={onClose} style={a.btn}><Text style={a.btnText}>Cancel</Text></Pressable>
            <Pressable onPress={accept} style={[a.btn, a.accent]}><Text style={a.btnText}>Accept</Text></Pressable>
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
}

function Quizzes({ quiz }: { quiz: Loaded['quiz'] }) {
  const [showAll, setShowAll] = useState(false);
  if (!quiz) return <Empty>Loading the protocols…</Empty>;
  const missing = quiz.rows.filter((r) => r.count < QUIZ_READY).length;
  const settled = quiz.rows.filter((r) => r.count >= QUIZ_READY && !r.spotCheck);
  const shown = showAll ? quiz.rows : quiz.rows.filter((r) => r.count < QUIZ_READY || r.spotCheck);
  return (
    <>
      <Text style={[s.small, { color: missing ? C.text : C.green }]}>
        {missing ? `${quiz.withQuiz} of ${quiz.rows.length} protocols have a quiz (${quiz.bank} questions). ${missing} still to write.`
          : `✅ All ${quiz.rows.length} reviewed protocols have a quiz — ${quiz.bank} questions in all. Nothing to do here unless you want more.`}
      </Text>
      {shown.map((r) => (
        <Text key={r.id} style={[s.small, { color: C.text, marginTop: 3 }]}>
          {r.count >= QUIZ_GOOD ? '✦' : r.count >= QUIZ_READY ? '✓' : '○'} {r.title} · {r.count} question{r.count === 1 ? '' : 's'}
          {r.spotCheck ? '  👀 spot-check waiting on your computer' : ''}
        </Text>
      ))}
      {settled.length ? (
        <Text style={[a.link, { marginTop: 4 }]} onPress={() => setShowAll(!showAll)}>
          {showAll ? 'Hide them' : `✅ ${settled.length} already have enough · Show them`}
        </Text>
      ) : null}
    </>
  );
}

function Prospect({ p, me, onMark, onNote }: {
  p: Person; me: string; onMark: (status: 'invited' | 'declined') => Promise<boolean>; onNote: (t: string) => void;
}) {
  const draft = invite(p, me);
  const email = async () => {                    // opening the email is inviting them: marked now, as on the desktop
    if (await onMark('invited')) Linking.openURL(draft.mailto!);
  };
  const copy = async () => {
    await Clipboard.setStringAsync(`${draft.subject}\n\n${draft.body}`);
    onNote(`Invite for ${p.login} copied: paste it wherever you reach them.`);
    open(`https://github.com/${p.login}`);
  };
  return (
    <Card>
      <View style={[s.row, { alignItems: 'center' }]}>
        {p.avatar ? <Image source={{ uri: p.avatar }} style={a.avatar} /> : null}
        <View style={{ flex: 1 }}>
          <Text style={s.name}>{p.name || p.login}</Text>
          <Text style={s.small}>@{p.login} · {p.why.slice(0, 2).join('; ')}</Text>
        </View>
        <Text style={a.score}>{p.score.toFixed(1)}</Text>
      </View>
      {p.last_active ? (
        <Text style={[s.small, p.events_30d >= 5 && { color: C.green }]}>
          🔥 {p.events_30d} public event{p.events_30d === 1 ? '' : 's'} in 30 days · last active {timeAgo(p.last_active)}
        </Text>
      ) : null}
      {p.bio ? <Text style={[s.small, { fontStyle: 'italic' }]}>{p.bio.slice(0, 110)}</Text> : null}
      <View style={a.actions}>
        <Pressable onPress={() => open(`https://github.com/${p.login}`)} style={a.btn}><Text style={a.btnText}>Profile ↗</Text></Pressable>
        {draft.mailto ? (
          <Pressable onPress={email} style={a.btn}><Text style={a.btnText}>✉ Email</Text></Pressable>
        ) : (
          <Pressable onPress={copy} style={a.btn}><Text style={a.btnText}>⧉ Copy invite</Text></Pressable>
        )}
        <Pressable onPress={() => onMark('invited')} style={a.btn}><Text style={a.btnText}>Invited ✓</Text></Pressable>
        <Pressable onPress={() => onMark('declined')} style={a.btn}><Text style={a.btnText}>Not now</Text></Pressable>
      </View>
    </Card>
  );
}

const a = StyleSheet.create({
  locked: { alignItems: 'center', gap: 8, paddingVertical: 30 },
  lockIcon: { fontSize: 40 },
  lockTitle: { color: C.text, fontSize: 18, fontWeight: '800' },
  unlock: { backgroundColor: C.violet, borderRadius: 12, paddingHorizontal: 22, paddingVertical: 11, marginTop: 6 },
  unlockText: { color: '#fff', fontWeight: '800', fontSize: 15 },
  link: { color: C.cyan, fontSize: 14 },
  avatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: C.cardHi },
  score: { color: C.amber, fontSize: 15, fontWeight: '800' },
  sure: { fontSize: 11, fontWeight: '800', borderRadius: 7, paddingHorizontal: 7, paddingVertical: 2, overflow: 'hidden' },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 },
  btn: { backgroundColor: tint(0.08), borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, minHeight: 38, justifyContent: 'center' },
  accent: { backgroundColor: 'rgba(122,92,255,0.55)' },
  btnText: { color: C.text, fontSize: 13, fontWeight: '700' },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  sheet: { maxHeight: '85%', backgroundColor: C.sheet, borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: 16 },
  sheetTitle: { color: C.text, fontSize: 17, fontWeight: '800', marginBottom: 10 },
  input: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 10, color: C.text, paddingHorizontal: 10,
    paddingVertical: 8, fontSize: 14, marginTop: 3 },
});
