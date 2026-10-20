// You → Settings → 🧠 How myGeeKy asks the internet: every user's own WISEP in plain words -- what it asked today and
// what it answered from what it kept, GitHub beside it, the pages it learned you open, how far it is from deciding
// alone, the Auto / Always / Never switch, and Forget what it learned. All of it stays on this phone. The desktop's
// gui/wisep_ui.py shows the same.
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { forgetLearned, type Mode, PROVEN_DAYS, PROVEN_LOOKS, PROVEN_SAVED, setMode, stats } from '../lib/wisep';
import { C } from '../lib/theme';

const WORDS: Record<Mode, string> = { auto: 'Auto', on: 'Always', off: 'Never' };
const NEXT: Record<Mode, Mode> = { auto: 'on', on: 'off', off: 'auto' };

/** WISEP on this phone today, in a few plain sentences (gui/wisep_ui.py summary). */
export async function wisepSummary(): Promise<{ text: string; mode: Mode }> {
  const st = await stats();
  const parts = Object.entries(st.today).sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([src, c]) => `${src}: ${c.asked} asked, ${c.saved} from what it kept${c.topup ? `, ${c.topup} in the evening top-up` : ''}`);
  const p = st.proven, pages = st.pages.slice(0, 4).map((x) => x.page).join(', ');
  const alone = p.alone ? `It decides alone${p.mode === 'on' ? ' (you said Always).' : ': it has proven itself.'}`
    : p.mode === 'off' ? 'The old once-a-day timers lead (you said Never).'
      : `It takes over from the old once-a-day timers once it has proven itself: ${p.days} of ${PROVEN_DAYS} days, ${p.looks} of ${PROVEN_LOOKS} answers, ${Math.round(p.saved * 100)}% from what it kept (it needs ${Math.round(PROVEN_SAVED * 100)}%).`;
  const tuned = Object.entries(st.priors).sort(([a], [b]) => (a < b ? -1 : 1)).map(([k, v]) => `${k} about every ${v} hours`).join(', ');
  return { mode: p.mode, text: `Today: ${parts.length ? `${parts.join('; ')}.` : 'nothing asked yet.'} GitHub (with its own cache): ${st.github.asked} asked, ${st.github.saved} free.`
    + `${pages ? ` You open most: ${pages}.` : ''} ${alone}${tuned ? ` It learned how often answers change here: ${tuned}.` : ''}` };
}

export function WisepSettings() {
  const [s, setS] = useState<{ text: string; mode: Mode } | null>(null);
  const [note, setNote] = useState('');
  const again = useCallback(() => { wisepSummary().then(setS).catch(() => undefined); }, []);
  useEffect(() => { again(); }, [again]);
  return (
    <View>
      <Text style={st.text}>Papers, citations and datasets come from open databases (OpenAlex, Zenodo, NCBI…). myGeeKy keeps their answers and asks again only when a fresh one is worth it: when it has probably changed and you&apos;re likely to look, within a daily budget, and kindly to the databases. It learns which pages you open and when, on this phone only, and spends what&apos;s left of the day&apos;s budget in the evening on what you&apos;ll want tomorrow.</Text>
      {s ? <Text style={[st.text, { marginTop: 6 }]}>{s.text}</Text> : null}
      <View style={st.row}>
        {s ? (
          <Pressable onPress={() => setMode(NEXT[s.mode]).then(again)} style={({ pressed }) => [st.btn, pressed && { opacity: 0.7 }]}
                     accessibilityRole="button" accessibilityLabel={`Decides alone: ${WORDS[s.mode]}. Tap to change.`}>
            <Text style={st.btnText}>🧠 Decides alone: {WORDS[s.mode]}</Text>
          </Pressable>
        ) : null}
        <Pressable onPress={() => forgetLearned().then(() => { setNote('Forgotten: it starts learning your day again.'); again(); })}
                   style={({ pressed }) => [st.btn, pressed && { opacity: 0.7 }]} accessibilityRole="button">
          <Text style={st.btnText}>Forget what it learned</Text>
        </Pressable>
      </View>
      <Text style={[st.text, { fontSize: 11.5 }]}>Auto: it decides alone once it has proven itself (14 days, 40% answered from what it kept). What it kept from the databases stays when you forget: it&apos;s public, and only makes the screen faster.</Text>
      {note ? <Text style={[st.text, { color: C.green }]}>{note}</Text> : null}
    </View>
  );
}

const st = StyleSheet.create({
  text: { color: C.muted, fontSize: 12.5, lineHeight: 18 },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginVertical: 8 },
  btn: { backgroundColor: C.cardHi, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 7 },
  btnText: { color: C.text, fontSize: 12.5, fontWeight: '700' },
});
