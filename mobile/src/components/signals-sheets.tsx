// The two sheets of the 📡 planet: invite contributors to one of your repos, and send someone
// a signal. Both slide up over the screen; nothing is sent until you press the button.
import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { CALL_DAYS, CALL_LEVELS, CALL_TIMES, listRepos, MAX_CALL_SKILLS, MAX_CALLS, MAX_NOTE, type Person } from '../lib/signals';
import { C } from '../lib/theme';

function Sheet({ title, iconName, onClose, children }: {
  title: string; iconName: 'person-add-outline' | 'paper-plane-outline'; onClose: () => void; children: React.ReactNode;
}) {
  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={st.backdrop}>
        <Pressable style={{ flex: 1 }} onPress={onClose} accessibilityLabel="Close" />
        <View style={st.sheet}>
          <View style={st.head}>
            <Ionicons name={iconName} size={20} color={C.pink} />
            <Text style={st.title}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={10}><Text style={st.cancel}>Cancel</Text></Pressable>
          </View>
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: 28 }}>{children}</ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const Label = ({ children }: { children: React.ReactNode }) => <Text style={st.label}>{children}</Text>;

function Chips({ options, chosen, onToggle }: { options: [string, string][]; chosen: (k: string) => boolean; onToggle: (k: string) => void }) {
  return (
    <View style={st.chips}>
      {options.map(([k, label]) => (
        <Pressable key={k} onPress={() => onToggle(k)} style={[st.chip, chosen(k) && st.chipOn]}
                   accessibilityState={{ selected: chosen(k) }}>
          <Text style={[st.chipText, chosen(k) && st.chipTextOn]}>{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

// ---- invite contributors
type RepoInfo = { name: string; topics: string[]; language: string };
const poolOf = (r: RepoInfo) => [...new Set([...r.topics, ...(r.language ? [r.language.toLowerCase()] : [])])];

export type CallInput = { repo: string; note: string; skills: string[]; level: string; time: string; days: number };

export function InviteSheet({ me, token, openCalls, onClose, onPublish }: {
  me: string; token: string | null; openCalls: number; onClose: () => void; onPublish: (c: CallInput) => Promise<void>;
}) {
  const [repos, setRepos] = useState<RepoInfo[] | null>(null);
  const [repo, setRepo] = useState('');
  const [pool, setPool] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [extra, setExtra] = useState('');
  const [note, setNote] = useState('');
  const [level, setLevel] = useState('any');
  const [time, setTime] = useState('hours');
  const [days, setDays] = useState(60);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const pick = (r: RepoInfo) => {
    setRepo(r.name);
    setPool(poolOf(r));
    setSkills(poolOf(r).slice(0, 3));
  };
  useEffect(() => {
    listRepos(me, token).then((r) => {
      setRepos(r);
      if (r.length) {
        setRepo(r[0].name);
        setPool(poolOf(r[0]));
        setSkills(poolOf(r[0]).slice(0, 3));
      }
    });
  }, [me, token]);
  const toggle = (k: string) => setSkills((cur) => (cur.includes(k) ? cur.filter((x) => x !== k)
    : cur.length < MAX_CALL_SKILLS ? [...cur, k] : cur));
  const addExtra = () => {
    const t = extra.trim().toLowerCase().replace(/[^\w .+#-]/g, '').slice(0, 40);
    setExtra('');
    if (!t) return;
    setPool((p) => (p.includes(t) ? p : [...p, t]));
    setSkills((cur) => (cur.includes(t) || cur.length >= MAX_CALL_SKILLS ? cur : [...cur, t]));
  };
  const n = [...note.trim()].length;
  const ok = !!repo && n >= 10 && n <= MAX_NOTE && skills.length > 0 && !busy;
  const publish = async () => {
    setBusy(true);
    setMsg('Publishing in your beacon…');
    try {
      await onPublish({ repo, note: note.trim(), skills, level, time, days });
      setMsg('Published. From now on it reaches people whose skills fit.');
      setTimeout(onClose, 1200);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Not published. Try again.');
      setBusy(false);
    }
  };

  return (
    <Sheet title="Invite contributors" iconName="person-add-outline" onClose={onClose}>
      <Text style={st.intro}>{"Your call goes into your beacon. Each person's own myGeeKy decides whether it fits them: "
        + 'nobody is targeted, and you only ever see who says yes.'}</Text>
      <Label>Which project</Label>
      {repos === null ? <Text style={st.muted}>Loading your repos…</Text>
        : !repos.length ? <Text style={st.muted}>No public repos of yours found.</Text>
          : <Chips options={repos.map((r) => [r.name, r.name])} chosen={(k) => k === repo}
                   onToggle={(k) => pick(repos.find((r) => r.name === k)!)} />}
      <Label>{`Skills you need (up to ${MAX_CALL_SKILLS})`}</Label>
      <Chips options={pool.map((p) => [p, p])} chosen={(k) => skills.includes(k)} onToggle={toggle} />
      <TextInput style={st.input} value={extra} onChangeText={setExtra} onSubmitEditing={addExtra} returnKeyType="done"
                 placeholder="Add a skill" placeholderTextColor={C.muted} autoCapitalize="none" maxLength={40} />
      <Label>What you need, in a sentence or two</Label>
      <TextInput style={[st.input, { minHeight: 70, textAlignVertical: 'top' }]} value={note} onChangeText={setNote} multiline
                 maxLength={MAX_NOTE} placeholder="e.g. A second pair of eyes on the LD-pruning step before we publish."
                 placeholderTextColor={C.muted} />
      <Text style={st.count}>{n}/{MAX_NOTE} · no links</Text>
      <Label>Level</Label>
      <Chips options={Object.entries(CALL_LEVELS)} chosen={(k) => k === level} onToggle={setLevel} />
      <Label>Time it takes</Label>
      <Chips options={Object.entries(CALL_TIMES)} chosen={(k) => k === time} onToggle={setTime} />
      <Label>Open for</Label>
      <Chips options={CALL_DAYS.map((d) => [String(d), `${d} days`])} chosen={(k) => Number(k) === days}
             onToggle={(k) => setDays(Number(k))} />
      <Label>How others will see it</Label>
      <View style={st.preview}>
        <Text style={st.repo}>{me}/{repo || 'your-repo'}</Text>
        <Text style={st.muted}>{CALL_LEVELS[level]} · {CALL_TIMES[time]} · {days} days left</Text>
        <Text style={st.note}>{note.trim() || 'Your sentence shows here.'}</Text>
        <Text style={st.muted}>{skills.join(' · ') || 'the skills you need'}</Text>
      </View>
      {msg ? <Text style={[st.msg, msg.startsWith('Published') && { color: C.green }]}>{msg}</Text> : null}
      <Pressable onPress={publish} disabled={!ok} style={[st.cta, !ok && { opacity: 0.45 }]}>
        <Ionicons name="person-add-outline" size={16} color="#fff" />
        <Text style={st.ctaText}>Publish the call</Text>
      </Pressable>
      <Text style={[st.muted, { textAlign: 'center', marginTop: 8 }]}>{openCalls}/{MAX_CALLS} open calls</Text>
    </Sheet>
  );
}

// ---- send a signal
const SIGNALS: [string, string, string][] = [
  ['thanks', '🙏 Thanks', 'for their work'],
  ['learn', '📚 Learned', 'from their work'],
  ['used', '⭐ Used it', 'one of their repos'],
  ['watching', '👀 Following', 'their work'],
  ['collab', '🤝 Collaborate', 'only shown if they choose you too'],
];
const SEES: Record<string, string> = {
  thanks: '🙏 thanked you for your work', learn: '📚 learned from your work', watching: '👀 is following your work',
  collab: '🤝 you both want to collaborate (only if they choose you too)',
};

export function SendSheet({ people, token, to: initialTo, gesture: initialGesture, onClose, onSend }: {
  people: Person[]; token: string | null; to?: string; gesture?: string; onClose: () => void;
  onSend: (to: string, gesture: string, repo?: string) => Promise<void>;
}) {
  const able = people.filter((p) => p.canReceive);
  const [q, setQ] = useState('');
  const [to, setTo] = useState<string | null>(initialTo && able.some((p) => p.login === initialTo) ? initialTo : null);
  const [g, setG] = useState<string | null>(initialGesture ?? null);
  const [repos, setRepos] = useState<string[] | null>(null);
  const [repo, setRepo] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const loadRepos = (login: string) => listRepos(login, token).then((r) => setRepos(r.map((x) => x.fullName)));
  const choose = (login: string | null) => {
    setTo(login);
    setRepos(null);
    setRepo('');
    if (login) loadRepos(login);
  };
  useEffect(() => {
    if (to) loadRepos(to);         // the person you came from: their repos, for ⭐
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const who = able.find((p) => p.login === to);
  const shown = able.filter((p) => !q.trim() || p.login.toLowerCase().includes(q.trim().toLowerCase())
    || p.interests.some((i) => i.includes(q.trim().toLowerCase()))).sort((a, b) => b.fit - a.fit);
  const ok = !!to && !!g && (g !== 'used' || !!repo) && !busy;
  const send = async () => {
    setBusy(true);
    setMsg('Sending…');
    try {
      await onSend(to!, g!, g === 'used' ? repo : undefined);
      setMsg(`Sent privately to ${to}. Only they can read it.`);
      setTimeout(onClose, 1200);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "It didn't send. Try again.");
      setBusy(false);
    }
  };

  return (
    <Sheet title="Send a signal" iconName="paper-plane-outline" onClose={onClose}>
      <Label>To</Label>
      {who ? (
        <View style={st.chosen}>
          <View style={{ flex: 1 }}>
            <Text style={st.name}>{who.login}</Text>
            <Text style={st.muted}>{who.status || 'on Signals'}</Text>
          </View>
          <Pressable onPress={() => choose(null)} style={st.small}><Text style={st.smallText}>Change</Text></Pressable>
        </View>
      ) : (
        <>
          <TextInput style={st.input} value={q} onChangeText={setQ} placeholder="Search people on Signals, or a topic"
                     placeholderTextColor={C.muted} autoCapitalize="none" />
          <View style={{ maxHeight: 220 }}>
            {shown.length ? shown.map((p) => (
              <Pressable key={p.login} onPress={() => choose(p.login)} style={st.person}>
                <View style={{ flex: 1 }}>
                  <Text style={st.name}>{p.login}</Text>
                  {p.shared.length ? <Text style={st.muted}>shares {p.shared.slice(0, 3).join(', ')}</Text> : null}
                </View>
                <Text style={st.fit}>{Math.round(p.fit * 100)}%</Text>
              </Pressable>
            )) : <Text style={st.muted}>{able.length ? 'Nobody on Signals matches that yet.' : 'Nobody on Signals can receive signals yet.'}</Text>}
          </View>
        </>
      )}
      <Label>Signal</Label>
      <View style={st.grid}>
        {SIGNALS.map(([k, label, sub]) => (
          <Pressable key={k} disabled={!to} onPress={() => setG(k)} style={[st.g, g === k && st.gOn, !to && { opacity: 0.45 }]}
                     accessibilityState={{ selected: g === k }}>
            <Text style={st.gLabel}>{label}</Text>
            <Text style={st.gSub}>{sub}</Text>
          </Pressable>
        ))}
      </View>
      {g === 'used' && to ? (
        <>
          <Label>Which of their repos</Label>
          {repos === null ? <Text style={st.muted}>Loading their repos…</Text>
            : <Chips options={repos.map((r) => [r, r.split('/')[1]])} chosen={(k) => k === repo} onToggle={setRepo} />}
        </>
      ) : null}
      {to && g ? (
        <View style={st.preview}>
          <Text style={st.muted}>{to} will see:</Text>
          <Text style={st.note}>you {g === 'used' ? `⭐ used ${repo || 'one of their repos'} in their work` : SEES[g]} · no reply needed</Text>
        </View>
      ) : null}
      <Text style={[st.muted, { marginTop: 10 }]}>🔒 Sealed: only they can read it. One of each kind per person a month.</Text>
      {msg ? <Text style={[st.msg, msg.startsWith('Sent') && { color: C.green }]}>{msg}</Text> : null}
      <Pressable onPress={send} disabled={!ok} style={[st.cta, !ok && { opacity: 0.45 }]}>
        <Ionicons name="paper-plane-outline" size={16} color="#fff" />
        <Text style={st.ctaText}>Send</Text>
      </Pressable>
    </Sheet>
  );
}

const st = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(8,8,12,0.6)' },
  sheet: { backgroundColor: '#17171f', borderTopLeftRadius: 22, borderTopRightRadius: 22, maxHeight: '92%',
           paddingHorizontal: 16, paddingTop: 14, borderTopWidth: 1, borderColor: C.line },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  title: { color: C.text, fontSize: 18, fontWeight: '800', flex: 1 },
  cancel: { color: C.cyan, fontSize: 14, fontWeight: '600' },
  intro: { color: C.muted, fontSize: 13, lineHeight: 19 },
  label: { color: C.muted, fontSize: 11, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 14, marginBottom: 6 },
  muted: { color: C.muted, fontSize: 12.5, lineHeight: 18 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { paddingVertical: 7, paddingHorizontal: 11, borderRadius: 999, backgroundColor: C.cardHi, borderWidth: 1, borderColor: C.line },
  chipOn: { backgroundColor: C.violet, borderColor: C.violet },
  chipText: { color: C.text, fontSize: 13 },
  chipTextOn: { color: '#fff', fontWeight: '700' },
  input: { borderWidth: 1, borderColor: C.line, borderRadius: 10, color: C.text, paddingHorizontal: 10, paddingVertical: 9, marginTop: 8, fontSize: 14 },
  count: { color: C.muted, fontSize: 11, textAlign: 'right', marginTop: 4 },
  preview: { borderWidth: 1, borderStyle: 'dashed', borderColor: 'rgba(240,240,245,0.25)', borderRadius: 12, padding: 10, gap: 3, marginTop: 6 },
  repo: { color: C.cyan, fontSize: 13, fontWeight: '700' },
  note: { color: C.text, fontSize: 13.5, lineHeight: 19 },
  msg: { color: C.amber, fontSize: 13, marginTop: 10 },
  cta: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center', backgroundColor: C.pink, borderRadius: 14,
         paddingVertical: 13, marginTop: 14 },
  ctaText: { color: '#fff', fontWeight: '800', fontSize: 15 },
  chosen: { flexDirection: 'row', alignItems: 'center', padding: 10, borderRadius: 12, borderWidth: 1, borderColor: C.pink, backgroundColor: C.cardHi },
  name: { color: C.text, fontSize: 14.5, fontWeight: '800' },
  small: { paddingVertical: 6, paddingHorizontal: 10, borderRadius: 9, backgroundColor: C.card },
  smallText: { color: C.text, fontSize: 12.5, fontWeight: '600' },
  person: { flexDirection: 'row', alignItems: 'center', paddingVertical: 9, paddingHorizontal: 6, borderBottomWidth: 1, borderColor: C.line },
  fit: { color: C.green, fontSize: 12, fontWeight: '700' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  g: { width: '48.5%', padding: 10, borderRadius: 12, borderWidth: 1, borderColor: C.line, backgroundColor: C.card },
  gOn: { borderColor: C.pink, backgroundColor: 'rgba(255,111,216,0.12)' },
  gLabel: { color: C.text, fontSize: 13.5, fontWeight: '700' },
  gSub: { color: C.muted, fontSize: 11.5, marginTop: 2 },
});
