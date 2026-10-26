import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { AccessibilityInfo, Animated, BackHandler, Easing, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text,
  TextInput, View } from 'react-native';
import Svg, { Path, Rect } from 'react-native-svg';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useApp } from '../lib/app-state';
import { OrcidSignInButton, SignInButton } from '../components/signin';
import { TokenGuide } from '../components/token-guide';
import { orcidChecksumOk } from '../lib/orcid-login';
import { pick, suggest } from '../lib/word-suggest';
import { DEFAULT_SETTINGS } from '../lib/storage';
import { C } from '../lib/theme';
import { WhoisFind } from '../components/whois-find';
import { DocDrop } from '../components/doc-drop';
import { mergeWords } from '../lib/doc-read';
import { GeekMover } from '../components/tour-overlay';

const split = (v: string) => v.split(',').map((x) => x.trim()).filter(Boolean);
const ORCID = /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/;
type Step = 'welcome' | 'github' | 'orcid' | 'field';
const ORDER: Step[] = ['welcome', 'github', 'orcid', 'field'];
// "Tap me" in the five languages the hint cycles through, one after another
const HINTS: [string, 'ltr' | 'rtl'][] = [['Tap me', 'ltr'], ['اضغط عليّ', 'rtl'], ['Touche-moi', 'ltr'], ['Tipp mich an', 'ltr'], ['点我', 'ltr']];

// The start, one question a screen: GeeKOc welcomes you (Start, or scan the code of myGeeKy on your computer); link
// GitHub, or skip; sign in with ORCID (or find your papers by name), or skip; then "Can you give me one of these?":
// three keywords, a CV, or an ORCID iD, each a row that unfolds, or Continue without (myGeeKy then learns your field
// from what you open and like). The data repo and Signals are not asked here: Settings and the Signals page have them,
// and scanning the computer's code brings both at once. A token stays on this phone.
export default function Setup() {
  const { settings, save } = useApp();
  const [step, setStep] = useState<Step>('welcome');
  const [username, setUsername] = useState(settings?.username ?? '');
  const [token, setToken] = useState('');
  const [signedIn, setSignedIn] = useState('');
  const [byHand, setByHand] = useState(false);
  const [orcid, setOrcid] = useState(settings?.orcid ?? '');
  const [orcidName, setOrcidName] = useState('');
  const [finding, setFinding] = useState(false);
  const [openalex, setOpenalex] = useState(settings?.openalex ?? '');    // "Is this you?": the author you picked
  const [papersNote, setPapersNote] = useState('');
  const [keywords, setKeywords] = useState(settings?.keywords.join(', ') ?? '');
  const [coauthors, setCoauthors] = useState<string[]>(settings?.coauthors ?? []);   // from a dropped CV
  const [cvNote, setCvNote] = useState('');
  const [typedOrcid, setTypedOrcid] = useState('');
  const [open, setOpen] = useState<0 | 1 | 2 | 3>(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const at = ORDER.indexOf(step);
  const back = () => { setError(''); setStep(ORDER[Math.max(0, at - 1)]); };
  useEffect(() => {                                       // Android's Back: the step before, not out of the app
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (step === 'welcome') return false;
      back();
      return true;
    });
    return () => sub.remove();
  });

  const typed = typedOrcid.trim().replace(/^https?:\/\/orcid\.org\//, '');
  const orcidOk = !!orcid || (ORCID.test(typed) && orcidChecksumOk(typed));
  const words = split(keywords);
  const kwDone = words.length >= 3, cvDone = !!cvNote;
  const ready = kwDone || cvDone || orcidOk || !!openalex;

  const finish = async () => {
    const u = username.trim().replace(/^@/, '');
    if (u && !/^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$/.test(u)) { setStep('github'); return setError('That isn\'t a GitHub username.'); }
    if (typed && !orcid && !orcidOk) { setOpen(3); return setError(`${typed} isn't a valid ORCID iD: a digit is probably mistyped.`); }
    setBusy(true);
    setError('');
    await save({ ...(settings ?? DEFAULT_SETTINGS), username: u, orcid: orcid || (orcidOk ? typed : ''), openalex, keywords: words, coauthors,
                 started: true }, token.trim() || undefined);
    setBusy(false);
    router.replace('/home');
  };

  return (
    <SafeAreaView style={st.safe}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        {step !== 'welcome' ? (
          <View style={st.top}>
            <Pressable onPress={back} style={st.backBtn} accessibilityRole="button" accessibilityLabel="Back">
              <Svg width={18} height={18} viewBox="0 0 24 24"><Path d="M15 5l-7 7 7 7" stroke={C.text} strokeWidth={2.4} fill="none" strokeLinecap="round" strokeLinejoin="round" /></Svg>
            </Pressable>
            <View style={st.dots}>{[1, 2, 3].map((i) => <View key={i} style={[st.dot, i === at && st.dotOn, i < at && st.dotDone]} />)}</View>
            <Text style={st.of}>{at} of 3</Text>
          </View>
        ) : null}
        <ScrollView contentContainerStyle={[st.wrap, step === 'welcome' && { flexGrow: 1 }]} keyboardShouldPersistTaps="handled">

          {step === 'welcome' ? <Welcome onStart={() => setStep('github')} /> : null}

          {step === 'github' ? <>
            <Text style={st.ask}>Link your GitHub?</Text>
            <Text style={st.body}>It adds what moves around you: who follows you, what your circle pushes, your own repos and Signals.</Text>
            <Text style={st.promise}>✓  Read-only: myGeeKy never posts, stars or follows</Text>
            <Text style={st.promise}>✓  Your token stays on this phone</Text>
            <View style={{ height: 18 }} />
            <SignInButton signedInAs={signedIn} onSignedIn={(login, t) => { setToken(t); setUsername(login); setSignedIn(login); setStep('orcid'); }} />
            {signedIn ? (
              <Pressable style={st.primary} onPress={() => setStep('orcid')} accessibilityRole="button"><Text style={st.primaryText}>Continue</Text></Pressable>
            ) : <SkipButton onPress={() => { setError(''); setStep('orcid'); }} />}
            <Pressable onPress={() => setByHand(!byHand)} hitSlop={8}><Text style={st.more}>{byHand ? '▾' : '▸'}  Type a username or paste a token instead</Text></Pressable>
            {byHand ? <>
              <Text style={st.label}>GitHub username</Text>
              <TextInput style={st.input} value={username} onChangeText={setUsername} autoCapitalize="none" autoCorrect={false}
                         placeholder="e.g. octocat" placeholderTextColor={C.muted} />
              <Text style={st.label}>GitHub token <Text style={st.opt}>(optional: read-only)</Text></Text>
              <TextInput style={st.input} value={token} onChangeText={setToken} autoCapitalize="none" secureTextEntry
                         placeholder="github_pat_…" placeholderTextColor={C.muted} />
              <Text style={st.hint}>{"Only needed for People. It stays in this phone's secure storage."}</Text>
              <TokenGuide which="read" />
            </> : null}
          </> : null}

          {step === 'orcid' ? <>
            <Text style={st.ask}>Sign in with ORCID?</Text>
            <Text style={st.body}>Your papers tell me your field: who cites you, who you work with, and the Leading lights near your work.</Text>
            <Pressable onPress={() => setFinding(!finding)} hitSlop={8}><Text style={st.link}>No ORCID? Find my papers by name</Text></Pressable>
            {finding ? (
              <WhoisFind
                onPick={(c) => { setOpenalex(c.id); setFinding(false); setPapersNote(`✓ That's you: ${c.name} (${c.works} works). Your papers will shape your profile.`); }}
                onNone={() => { setFinding(false); setPapersNote('No match: carry on, keywords or a CV work just as well.'); }}
                onBusy={() => { setFinding(false); setPapersNote('OpenAlex is busy right now. myGeeKy will look again later by itself and ask "Is this you?" (You → Settings).'); }} />
            ) : null}
            {papersNote ? <Text style={st.ok}>{papersNote}</Text> : null}
            <View style={{ height: 18 }} />
            <OrcidSignInButton signedInAs={orcidName} onSignedIn={(me) => { setOrcid(me.orcid); setOrcidName(me.name || me.orcid); setStep('field'); }} />
            {orcidName || openalex ? (
              <Pressable style={st.primary} onPress={() => setStep('field')} accessibilityRole="button"><Text style={st.primaryText}>Continue</Text></Pressable>
            ) : <SkipButton onPress={() => setStep('field')} />}
          </> : null}

          {step === 'field' ? <>
            <Text style={st.ask}>Can you give me one of these?</Text>
            <Text style={st.body}>Any one helps me start right. Tap one to open it. No time now? Continue without, and I&apos;ll learn from what you open and like.</Text>

            <Option n={1} title="Three keywords" done={kwDone} open={open === 1} onToggle={() => setOpen(open === 1 ? 0 : 1)}
                    hint={words.length ? `${Math.min(words.length, 3)} of 3 · ${words.slice(0, 3).join(', ')}` : 'e.g. GWAS, single cell, statistics'}>
              <TextInput style={st.input} value={keywords} onChangeText={setKeywords} autoFocus placeholder="GWAS, single cell, AI"
                         placeholderTextColor={C.muted} accessibilityLabel="Your keywords, separated by commas" />
              {suggest(keywords).length ? (
                <View style={st.chips}>
                  {suggest(keywords).map((w) => (
                    <Pressable key={w} onPress={() => setKeywords(pick(keywords, w))} hitSlop={4} style={({ pressed }) => [st.chip, pressed && { opacity: 0.7 }]}
                               accessibilityLabel={`Add ${w}`}>
                      <Text style={st.chipText}>+ {w}</Text>
                    </Pressable>
                  ))}
                </View>
              ) : null}
              <Text style={st.hint}>Separate them with commas, or tap a suggestion.</Text>
            </Option>

            <Option n={2} title="Your CV, thesis or abstract" done={cvDone} open={open === 2} onToggle={() => setOpen(open === 2 ? 0 : 2)}
                    hint={cvNote || 'read on this phone, never sent anywhere'}>
              <DocDrop ownName={orcidName} keepLabel="Keep these words" onKeep={(k) => {
                const found = [...k.keywords, ...k.methods];
                setKeywords(mergeWords(split(keywords), found).join(', '));
                setCoauthors(mergeWords(coauthors, k.coauthors));
                setCvNote(`${found.length} words found${k.coauthors.length ? ` · ${k.coauthors.length} co-authors` : ''}`);
                setOpen(0);
              }} />
            </Option>

            <Option n={3} title="Your ORCID iD" done={orcidOk} open={open === 3} onToggle={() => setOpen(open === 3 ? 0 : 3)}
                    hint={orcid ? (orcidName ? `signed in: ${orcidName}` : orcid) : orcidOk ? typed : 'looks like 0000-0002-1825-0097'}>
              {orcid ? <Text style={st.ok}>✓ {orcidName ? `Signed in with ORCID as ${orcidName}` : `Your ORCID iD: ${orcid}`}</Text> : (
                <TextInput style={st.input} value={typedOrcid} onChangeText={setTypedOrcid} autoCapitalize="none" keyboardType="numbers-and-punctuation"
                           placeholder="0000-0002-1825-0097" placeholderTextColor={C.muted} accessibilityLabel="Your ORCID iD" />
              )}
            </Option>

            {error ? <Text style={st.error}>{error}</Text> : null}
            <Text style={[st.need, ready && { color: C.green }]}>
              {ready ? 'Great, that is enough to start.'
                : words.length ? `Add ${3 - words.length} more keyword${3 - words.length === 1 ? '' : 's'}, or your CV, or your ORCID iD. Or continue without: myGeeKy learns your field from what you open, like and save.`
                  : 'Pick one of the three, or continue without: myGeeKy learns your field from what you open, like and save.'}
            </Text>
            <Pressable style={({ pressed }) => [ready ? st.primary : st.without, pressed && { opacity: 0.85 }]} onPress={finish} disabled={busy}
                       accessibilityRole="button">
              <Text style={ready ? st.primaryText : st.withoutText}>{busy ? 'Getting ready…' : ready ? 'Continue' : 'Continue without'}</Text>
            </Pressable>
          </> : null}

          {step !== 'welcome' && step !== 'field' && error ? <Text style={st.error}>{error}</Text> : null}
          <Text style={st.foot}>myGeeKy only suggests. It never follows, stars or posts for you.</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

/** GeeKOc jet-swimming (a tap makes him cheer for a moment), "Tap me" in five languages, Start, and scanning the
 *  computer's code. */
function Welcome({ onStart }: { onStart: () => void }) {
  const [cheer, setCheer] = useState(false);
  const [hint, setHint] = useState(0);
  const [still, setStill] = useState(false);
  const [slide] = useState(() => new Animated.Value(0));
  useEffect(() => { AccessibilityInfo.isReduceMotionEnabled().then(setStill).catch(() => undefined); }, []);
  useEffect(() => {
    const t = setInterval(() => setHint((h) => (h + 1) % HINTS.length), 2200);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (still) return;
    slide.setValue(1);
    Animated.timing(slide, { toValue: 0, duration: 320, easing: Easing.out(Easing.quad), useNativeDriver: true }).start();
  }, [hint, still, slide]);
  useEffect(() => {
    if (!cheer) return;
    const t = setTimeout(() => setCheer(false), 2400);
    return () => clearTimeout(t);
  }, [cheer]);
  const [word, dir] = HINTS[hint];
  return (
    <View style={st.welcome}>
      <Text style={st.brand}>MYGEEKY</Text>
      <Pressable onPress={() => setCheer(true)} accessibilityRole="button" accessibilityLabel="Say hi to GeeKOc">
        <GeekMover pose={cheer ? 'cheer' : 'jet'} size={300} />
      </Pressable>
      <View style={st.hintBox}>
        <Animated.Text style={[st.tapHint, { writingDirection: dir, opacity: slide.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }),
                                             transform: [{ translateX: slide.interpolate({ inputRange: [0, 1], outputRange: [0, 40] }) }] }]}>
          {word}
        </Animated.Text>
      </View>
      <Text style={st.hello}>Hi, I&apos;m GeeKOc!</Text>
      <Text style={st.lead}>Your geeky friend who helps you grow, quietly. Three quick questions and I&apos;ll find what fits your work: skills, papers, seasons and jobs.</Text>
      <View style={{ flex: 1, minHeight: 16 }} />
      <Pressable style={({ pressed }) => [st.primary, pressed && { opacity: 0.85 }]} onPress={onStart} accessibilityRole="button">
        <Text style={st.primaryText}>Start</Text>
      </Pressable>
      <Pressable style={({ pressed }) => [st.scan, pressed && { opacity: 0.85 }]} onPress={() => router.push('/scan')} accessibilityRole="button"
                 accessibilityLabel="Scan from your computer">
        <View style={st.scanIcons}>
          <Svg width={26} height={26} viewBox="0 0 24 24" fill="none">
            <Rect x={3} y={4} width={18} height={12} rx={2} stroke={C.cyan} strokeWidth={2} />
            <Path d="M8 20h8M12 16v4" stroke={C.cyan} strokeWidth={2} strokeLinecap="round" />
          </Svg>
          <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
            <Rect x={3} y={3} width={7} height={7} rx={1} stroke={C.cyan} strokeWidth={2} />
            <Rect x={14} y={3} width={7} height={7} rx={1} stroke={C.cyan} strokeWidth={2} />
            <Rect x={3} y={14} width={7} height={7} rx={1} stroke={C.cyan} strokeWidth={2} />
            <Path d="M14 14h3v3h-3zM17 20h4v-3M14 20h.01M20 14h.01" stroke={C.cyan} strokeWidth={2} strokeLinecap="round" />
          </Svg>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={st.scanTitle}>Scan from your computer</Text>
          <Text style={st.scanSub}>Already use myGeeKy there? Scan its code and you are set.</Text>
        </View>
      </Pressable>
    </View>
  );
}

function SkipButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable style={({ pressed }) => [st.skip, pressed && { opacity: 0.8 }]} onPress={onPress} accessibilityRole="button">
      <Text style={st.skipText}>Skip for now  ›</Text>
    </Pressable>
  );
}

/** One of the three ways to say your field: a row that unfolds; a green ✓ once it's given. */
function Option({ n, title, hint, done, open, onToggle, children }: {
  n: number; title: string; hint: string; done: boolean; open: boolean; onToggle: () => void; children: React.ReactNode;
}) {
  return (
    <View style={[st.option, open && { borderColor: C.violet }, done && { borderColor: C.green }]}>
      <Pressable onPress={onToggle} style={st.optionHead} accessibilityRole="button" accessibilityState={{ expanded: open }}>
        <View style={[st.num, done && { backgroundColor: C.green }]}><Text style={[st.numText, done && { color: '#0d1f17' }]}>{done ? '✓' : n}</Text></View>
        <View style={{ flex: 1 }}>
          <Text style={st.optionTitle}>{title}</Text>
          <Text style={st.optionHint} numberOfLines={1}>{hint}</Text>
        </View>
        <Text style={[st.chev, open && { transform: [{ rotate: '180deg' }] }]}>⌄</Text>
      </Pressable>
      {open ? <View style={{ marginTop: 12 }}>{children}</View> : null}
    </View>
  );
}

const st = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  wrap: { padding: 22, paddingBottom: 40 },
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 18, paddingTop: 8 },
  backBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: C.card, alignItems: 'center', justifyContent: 'center' },
  dots: { flexDirection: 'row', gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.line },
  dotOn: { width: 26, backgroundColor: C.pink },
  dotDone: { backgroundColor: C.pink },
  of: { width: 44, color: C.muted, fontSize: 12, textAlign: 'right' },
  welcome: { flex: 1, alignItems: 'center' },
  brand: { color: C.pink, fontSize: 13, fontWeight: '900', letterSpacing: 2, marginTop: 4 },
  hintBox: { height: 22, overflow: 'hidden', marginTop: -6, alignItems: 'center' },
  tapHint: { color: C.pink, fontSize: 14, fontWeight: '700', letterSpacing: 0.3 },
  hello: { color: C.text, fontSize: 28, fontWeight: '800', marginTop: 8, textAlign: 'center' },
  lead: { color: C.muted, fontSize: 15, textAlign: 'center', marginTop: 8, lineHeight: 22 },
  ask: { color: C.text, fontSize: 24, fontWeight: '800', marginTop: 12, lineHeight: 30 },
  body: { color: C.muted, fontSize: 15, marginTop: 10, lineHeight: 22 },
  promise: { color: C.muted, fontSize: 14, marginTop: 8 },
  link: { color: C.cyan, fontSize: 14, fontWeight: '700', marginTop: 14 },
  ok: { color: C.green, fontSize: 13.5, marginTop: 10, lineHeight: 19 },
  label: { color: C.text, fontSize: 14, fontWeight: '700', marginTop: 14, marginBottom: 6 },
  opt: { color: C.muted, fontWeight: '400' },
  input: { backgroundColor: C.bg, borderColor: C.line, borderWidth: 1, borderRadius: 12, color: C.text, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  hint: { color: C.muted, fontSize: 12, marginTop: 8, lineHeight: 17 },
  more: { color: C.violet, fontSize: 14, fontWeight: '700', marginTop: 18 },
  error: { color: C.red, fontSize: 14, marginTop: 14 },
  primary: { backgroundColor: C.violet, borderRadius: 16, height: 54, marginTop: 12, alignItems: 'center', justifyContent: 'center', alignSelf: 'stretch' },
  primaryText: { color: '#fff', fontSize: 17, fontWeight: '800' },
  skip: { borderWidth: 1.5, borderColor: C.muted, backgroundColor: C.card, borderRadius: 16, height: 52, marginTop: 10, alignItems: 'center', justifyContent: 'center' },
  skipText: { color: C.text, fontSize: 16, fontWeight: '800' },
  without: { backgroundColor: '#fca5a5', borderRadius: 16, height: 54, marginTop: 12, alignItems: 'center', justifyContent: 'center' },
  withoutText: { color: '#1a1013', fontSize: 17, fontWeight: '800' },
  need: { color: C.muted, fontSize: 13, lineHeight: 19, textAlign: 'center', marginTop: 18 },
  scan: { flexDirection: 'row', alignItems: 'center', gap: 12, alignSelf: 'stretch', borderWidth: 1.5, borderColor: C.line, backgroundColor: C.card,
          borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10, marginTop: 10 },
  scanIcons: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  scanTitle: { color: C.text, fontSize: 15, fontWeight: '800' },
  scanSub: { color: C.muted, fontSize: 12.5, marginTop: 2, lineHeight: 17 },
  option: { backgroundColor: C.card, borderRadius: 16, borderWidth: 1.5, borderColor: C.line, padding: 14, marginTop: 12 },
  optionHead: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  num: { width: 26, height: 26, borderRadius: 13, backgroundColor: C.cardHi, alignItems: 'center', justifyContent: 'center' },
  numText: { color: C.text, fontSize: 13, fontWeight: '800' },
  optionTitle: { color: C.text, fontSize: 15.5, fontWeight: '800' },
  optionHint: { color: C.muted, fontSize: 12.5, marginTop: 2 },
  chev: { color: C.muted, fontSize: 20, fontWeight: '800', marginTop: -6 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  chip: { backgroundColor: C.bg, borderColor: C.line, borderWidth: 1, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7 },
  chipText: { color: C.text, fontSize: 14 },
  foot: { color: C.muted, fontSize: 12, textAlign: 'center', marginTop: 22 },
});
