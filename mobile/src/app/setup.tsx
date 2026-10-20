import { router } from 'expo-router';
import { useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useApp } from '../lib/app-state';
import { DataStep, SignalsStep } from '../components/setup-steps';
import { OrcidSignInButton, SignInButton } from '../components/signin';
import { TokenGuide } from '../components/token-guide';
import { orcidChecksumOk } from '../lib/orcid-login';
import { pick, suggest } from '../lib/word-suggest';
import { DEFAULT_SETTINGS } from '../lib/storage';
import { C } from '../lib/theme';
import { NotifySettings } from '../components/notify-settings';
import { WhoisFind } from '../components/whois-find';
import { DocDrop } from '../components/doc-drop';
import { mergeWords } from '../lib/doc-read';

const split = (v: string) => v.split(',').map((x) => x.trim()).filter(Boolean);

// Who you are. First: sign in with GitHub, sign in with ORCID, or continue as a guest (no account). After a
// GitHub sign-in, two optional steps: your data repo, then Signals (setup-steps.tsx). Last: a few
// keywords for your field. Typing a username or ORCID iD by hand, and pasting a token, wait
// under "More options". Without GitHub, News, Research, AI models and Launches all work; the GitHub
// planets say what adding it would unlock. A token stays on this phone.
export default function Setup() {
  const { settings, save } = useApp();
  const [username, setUsername] = useState(settings?.username ?? '');
  const [orcid, setOrcid] = useState(settings?.orcid ?? '');
  const [keywords, setKeywords] = useState(settings?.keywords.join(', ') ?? '');
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState('');
  const [orcidName, setOrcidName] = useState('');
  const [step, setStep] = useState<'choose' | 'data' | 'signals' | 'papers' | 'doc' | 'keywords'>('choose');
  const [openalex, setOpenalex] = useState(settings?.openalex ?? '');    // "Is this you?": the author you picked
  const [papersNote, setPapersNote] = useState('');
  const [coauthors, setCoauthors] = useState<string[]>(settings?.coauthors ?? []);   // from a dropped CV
  const [more, setMore] = useState(false);

  const submit = async () => {
    const u = username.trim().replace(/^@/, '');
    if (u && !/^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$/.test(u)) return setError('That isn\'t a GitHub username.');
    const o = orcid.trim().replace(/^https?:\/\/orcid\.org\//, '');
    if (o && !/^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(o)) return setError('An ORCID looks like 0000-0002-1825-0097.');
    if (o && !orcidChecksumOk(o)) return setError(`${o} isn't a valid ORCID iD: a digit is probably mistyped.`);
    if (!u && !o && !openalex && !split(keywords).length) {
      return setError('Give a few keywords for your field, for example GWAS, single cell, AI.');
    }
    setBusy(true);
    setError('');
    await save({ ...(settings ?? DEFAULT_SETTINGS), username: u, orcid: o, openalex, keywords: split(keywords), coauthors },
      token.trim() || undefined);
    setBusy(false);
    router.replace('/home');
  };

  return (
    <SafeAreaView style={st.safe}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={st.wrap} keyboardShouldPersistTaps="handled">
          <Image source={require('../../assets/icon.png')} style={st.logo} />
          <Text style={st.brand}>myGeeKy</Text>
          <Text style={st.lead}>{'Find friends, collaborate, away from noise. Research, news and models, picked for your own work.'}</Text>

          {step === 'choose' ? <>
            <Pressable style={({ pressed }) => [st.scan, pressed && { opacity: 0.85 }]} onPress={() => router.push('/scan')}>
              <Text style={st.scanTitle}>📷  Scan from your computer</Text>
              <Text style={st.scanSub}>Already use myGeeKy on your computer? Open ⚙ → Connect your phone there, and
                scan the code: everything is set up at once.</Text>
            </Pressable>

            <SignInButton signedInAs={signedIn} onSignedIn={(login, t) => {
              setToken(t);
              setUsername(login);
              setSignedIn(login);
              setStep('data');
            }} />
            <OrcidSignInButton signedInAs={orcidName} onSignedIn={(me) => {
              setOrcid(me.orcid);
              setOrcidName(me.name || me.orcid);
              setStep('keywords');
            }} />
            <Pressable style={({ pressed }) => [st.papers, pressed && { opacity: 0.85 }]} onPress={() => setStep('papers')}
                       accessibilityLabel="Find my papers, with no ORCID">
              <Text style={st.papersText}>📄  Find my papers</Text>
            </Pressable>
            <Pressable style={({ pressed }) => [st.doc, pressed && { opacity: 0.85 }]} onPress={() => setStep('doc')}
                       accessibilityLabel="Drop a CV, thesis or abstract">
              <Text style={st.papersText}>📝  Drop a CV, thesis or abstract</Text>
            </Pressable>
            <Pressable style={({ pressed }) => [st.just, pressed && { opacity: 0.85 }]} onPress={() => setStep('keywords')}
                       accessibilityLabel="Continue as a guest, with no account">
              <Text style={st.justText}>👤  Continue as guest</Text>
            </Pressable>
            <Text style={st.hint}>As a guest you need no account: give a few keywords and go. Everything is kept on this
              phone; News, Papers, AI models and Launches all work without GitHub, and you can sign in any time later.</Text>
          </> : step === 'data' ? (
            <DataStep login={signedIn} onNext={() => setStep('signals')} />
          ) : step === 'signals' ? (
            <SignalsStep onNext={() => setStep('keywords')} />
          ) : step === 'papers' ? (
            <View>
              <Text style={st.label}>📄 Find your papers</Text>
              <WhoisFind
                onPick={(c) => { setOpenalex(c.id); setPapersNote(`✓ That's you: ${c.name} (${c.works} works). Your papers will shape your profile.`); setStep('keywords'); }}
                onNone={() => { setPapersNote('No match: carry on with a few keywords.'); setStep('keywords'); }}
                onBusy={() => { setPapersNote('OpenAlex is busy right now. Carry on with a few keywords: myGeeKy will look again later by itself and ask "Is this you?" (You → Settings).'); setStep('keywords'); }} />
              <Pressable onPress={() => setStep('choose')} hitSlop={8}><Text style={st.back}>← Other ways to start</Text></Pressable>
            </View>
          ) : step === 'doc' ? (
            <View>
              <Text style={st.label}>📝 Your CV, thesis or abstract</Text>
              <DocDrop ownName={orcidName} keepLabel="Keep these and go on" onKeep={(k) => {
                const words = [...k.keywords, ...k.methods];
                setKeywords(`${mergeWords(split(keywords), words).join(', ')}, `);   // ready for the next word
                setCoauthors(mergeWords(coauthors, k.coauthors));
                setPapersNote(`✓ From your document: ${words.length} words${k.coauthors.length ? ` and ${k.coauthors.length} co-authors`
                  : ''}. Add or remove any above.`);
                setStep('keywords');
              }} />
              <Pressable onPress={() => setStep('choose')} hitSlop={8}><Text style={st.back}>← Other ways to start</Text></Pressable>
            </View>
          ) : <>
            {signedIn || orcidName ? (
              <Text style={st.done}>{[signedIn && `✓ GitHub: ${signedIn}`, orcidName && `✓ ORCID: ${orcidName}`].filter(Boolean).join('   ')}</Text>
            ) : null}
            <Text style={st.ask}>{"What's your field?"}</Text>
            <Text style={st.hint}>{signedIn || orcidName
              ? 'Optional: myGeeKy already reads your field from your sign-in. A few keywords make it sharper.'
              : 'A few words is enough. myGeeKy uses them to pick research, news and models for you.'}</Text>
            <TextInput style={[st.input, { marginTop: 12 }]} value={keywords} onChangeText={setKeywords} autoFocus
                       placeholder="GWAS, single cell, AI" placeholderTextColor={C.muted} multiline
                       submitBehavior="blurAndSubmit" returnKeyType="done" onSubmitEditing={submit} />
            {suggest(keywords).length ? (
              <View style={st.chips}>
                {suggest(keywords).map((w) => (
                  <Pressable key={w} onPress={() => setKeywords(pick(keywords, w))} hitSlop={4}
                             style={({ pressed }) => [st.chip, pressed && { opacity: 0.7 }]} accessibilityLabel={`Add ${w}`}>
                    <Text style={st.chipText}>+ {w}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
            <Text style={st.hint}>Separate them with commas, or tap a suggestion.</Text>

            <Pressable onPress={() => setMore(!more)} hitSlop={8}>
              <Text style={st.more}>{more ? '▾' : '▸'}  More options</Text>
            </Pressable>
            {more ? <>
              {signedIn ? null : <>
                <Text style={st.label}>GitHub username <Text style={st.opt}>(optional)</Text></Text>
                <TextInput style={st.input} value={username} onChangeText={setUsername} autoCapitalize="none"
                           autoCorrect={false} placeholder="e.g. octocat" placeholderTextColor={C.muted} />
              </>}
              {orcidName ? null : <>
                <Text style={st.label}>ORCID iD <Text style={st.opt}>(it finds your research field)</Text></Text>
                <TextInput style={st.input} value={orcid} onChangeText={setOrcid} autoCapitalize="none"
                           placeholder="0000-0002-1825-0097" placeholderTextColor={C.muted} />
              </>}
              {signedIn ? null : <>
                <Text style={st.label}>GitHub token <Text style={st.opt}>(optional: read-only)</Text></Text>
                <TextInput style={st.input} value={token} onChangeText={setToken} autoCapitalize="none" secureTextEntry
                           placeholder="github_pat_…" placeholderTextColor={C.muted} />
                <Text style={st.hint}>{"Only needed later, for People. It stays in this phone's secure storage."}</Text>
                <TokenGuide which="read" />
              </>}
            </> : null}
          </>}

          {error ? <Text style={st.error}>{error}</Text> : null}
          {step === 'keywords' && papersNote ? <Text style={st.hint}>{papersNote}</Text> : null}
          {step === 'keywords' ? <>
            <Text style={st.label}>🔔 Notifications <Text style={st.opt}>(optional)</Text></Text>
            <NotifySettings />
            <Pressable style={({ pressed }) => [st.button, pressed && { opacity: 0.85 }]} onPress={submit} disabled={busy}>
              <Text style={st.buttonText}>{busy ? 'Getting to know your field…' : 'Start'}</Text>
            </Pressable>
            <Pressable onPress={() => { setStep('choose'); setError(''); }} hitSlop={8}>
              <Text style={st.back}>← Other ways to start</Text>
            </Pressable>
          </> : null}
          <Text style={st.hint}>myGeeKy only suggests. It never follows, stars or posts for you.</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  wrap: { padding: 22, paddingBottom: 48 },
  logo: { width: 84, height: 84, alignSelf: 'center', marginTop: 8 },
  brand: { color: C.pink, fontSize: 34, fontWeight: '900', textAlign: 'center', marginTop: 10, letterSpacing: -0.8 },
  lead: { color: C.muted, fontSize: 15, textAlign: 'center', marginTop: 6, marginBottom: 18, lineHeight: 21 },
  label: { color: C.text, fontSize: 14, fontWeight: '700', marginTop: 14, marginBottom: 6 },
  opt: { color: C.muted, fontWeight: '400' },
  input: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 12, color: C.text,
           paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  hint: { color: C.muted, fontSize: 12, marginTop: 8, lineHeight: 17 },
  error: { color: C.red, fontSize: 14, marginTop: 14 },
  scan: { backgroundColor: 'rgba(255,111,216,0.12)', borderColor: 'rgba(255,111,216,0.45)', borderWidth: 1,
          borderRadius: 16, padding: 16 },
  scanTitle: { color: C.text, fontSize: 17, fontWeight: '800' },
  scanSub: { color: C.muted, fontSize: 13, marginTop: 6, lineHeight: 18 },
  papers: { backgroundColor: '#4a92dd', borderRadius: 14, paddingVertical: 15, marginTop: 12, alignItems: 'center' },
  papersText: { color: '#ffffff', fontSize: 16, fontWeight: '800' },
  doc: { backgroundColor: '#8b6cff', borderRadius: 14, paddingVertical: 15, marginTop: 10, alignItems: 'center' },
  just: { backgroundColor: '#ff6fd8', borderRadius: 14, paddingVertical: 14, marginTop: 10, alignItems: 'center' },
  justText: { color: '#3a0a2e', fontSize: 16, fontWeight: '800' },
  done: { color: C.green, fontSize: 14, fontWeight: '700', textAlign: 'center', marginBottom: 14 },
  ask: { color: C.text, fontSize: 22, fontWeight: '800', marginTop: 4 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  chip: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7 },
  chipText: { color: C.text, fontSize: 14 },
  more: { color: C.violet, fontSize: 14, fontWeight: '700', marginTop: 18 },
  back: { color: C.muted, fontSize: 14, textAlign: 'center', marginTop: 16 },
  button: { backgroundColor: C.violet, borderRadius: 14, paddingVertical: 15, marginTop: 22, alignItems: 'center' },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '800' },
});

