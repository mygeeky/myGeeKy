// After "Sign in with GitHub" in setup: two optional steps, your data repo first, then Signals.
// The phone never creates either repo (its sign-in can only read public data). It joins what
// myGeeKy on a computer made, by scanning the pairing code or with a token of its own.
import { router } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { connectModel, MODEL_TOKEN_PAGE } from '../lib/model-repo';
import { TokenGuide } from './token-guide';

import { C } from '../lib/theme';

export function DataStep({ login, onNext }: { login: string; onNext: () => void }) {
  const [own, setOwn] = useState(false);
  const [repo, setRepo] = useState(`${login}/mygeeky-data`);
  const [token, setToken] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const connect = async () => {
    setBusy(true);
    setNote('Checking the token…');
    try {
      await connectModel(repo, token);
      setToken('');
      setNote('');
      onNext();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View>
      <Text style={st.step}>STEP 1 OF 2 · OPTIONAL</Text>
      <Text style={st.ask}>Your myGeeKy data</Text>
      <Text style={st.body}>
        A private GitHub repo (mygeeky-data) keeps what myGeeKy learns about you: your model, history and settings. Your
        computer and this phone both read and add to it, so they stay one myGeeKy.
      </Text>
      <View style={st.warn}>
        <Text style={st.warnText}>
          Without it, everything stays only on this phone, kept separately: your computer and this phone won&apos;t share
          anything, and if you lose the phone, what it learned is gone.
        </Text>
      </View>

      <Pressable style={({ pressed }) => [st.primary, pressed && { opacity: 0.85 }]} onPress={() => router.push('/scan')}>
        <Text style={st.primaryText}>📷  Scan from my computer</Text>
      </Pressable>
      <Text style={st.hint}>
        Recommended. On your computer, myGeeKy setup creates the repo for you; then open ⚙ → Connect your phone there.
        The code brings your data repo and Signals at once.
      </Text>

      <Pressable onPress={() => setOwn(!own)} hitSlop={8}>
        <Text style={st.more}>{own ? '▾' : '▸'}  I already have a data repo: connect it with a token</Text>
      </Pressable>
      {own ? <>
        <Text style={st.body}>
          1. Tap below. On GitHub choose Fine-grained token → Only select repositories → your data repo → Permissions →
          Contents → Read and write.{'\n'}2. Copy it, paste it here and tap Connect.
        </Text>
        <Pressable onPress={() => Linking.openURL(MODEL_TOKEN_PAGE)} style={st.secondary}>
          <Text style={st.secondaryText}>Make the token on GitHub ↗</Text>
        </Pressable>
        <TokenGuide which="data" />
        <TextInput style={st.input} value={repo} onChangeText={setRepo} autoCapitalize="none" autoCorrect={false}
                   placeholder="you/mygeeky-data" placeholderTextColor={C.muted} />
        <TextInput style={st.input} value={token} onChangeText={setToken} autoCapitalize="none" autoCorrect={false}
                   secureTextEntry placeholder="github_pat_…" placeholderTextColor={C.muted} />
        <Pressable onPress={connect} disabled={busy || !token.trim()}
                   style={[st.secondary, (busy || !token.trim()) && { opacity: 0.5 }]}>
          <Text style={st.secondaryText}>{busy ? 'Connecting…' : 'Connect'}</Text>
        </Pressable>
        {note ? <Text style={st.note}>{note}</Text> : null}
      </> : null}

      <Pressable onPress={onNext} hitSlop={8}>
        <Text style={st.skip}>Skip: keep everything on this phone only</Text>
      </Pressable>
    </View>
  );
}

export function SignalsStep({ onNext }: { onNext: () => void }) {
  return (
    <View>
      <Text style={st.step}>STEP 2 OF 2 · OPTIONAL</Text>
      <Text style={st.ask}>Signals</Text>
      <Text style={st.body}>
        Private thank-yous and collaboration invites between myGeeKy users, through your beacon (a small public repo,
        mygeeky-beacon). Nothing is ever sent unless you send it.
      </Text>
      <Text style={st.body}>
        Signals starts on your computer: turn it on in myGeeKy setup there, then scan the code from ⚙ → Connect your
        phone. You can also add this phone later from the Signals tab.
      </Text>
      <Pressable style={({ pressed }) => [st.primary, pressed && { opacity: 0.85 }]} onPress={() => router.push('/scan')}>
        <Text style={st.primaryText}>📷  Scan from my computer</Text>
      </Pressable>
      <Pressable onPress={onNext} hitSlop={8}>
        <Text style={st.skip}>Skip for now</Text>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  step: { color: C.muted, fontSize: 11, fontWeight: '800', letterSpacing: 0.8 },
  ask: { color: C.text, fontSize: 22, fontWeight: '800', marginTop: 4 },
  body: { color: C.muted, fontSize: 14, lineHeight: 20, marginTop: 10 },
  warn: { backgroundColor: 'rgba(255,196,87,0.12)', borderColor: 'rgba(255,196,87,0.45)', borderWidth: 1,
          borderRadius: 12, padding: 12, marginTop: 14 },
  warnText: { color: C.text, fontSize: 13, lineHeight: 19 },
  primary: { backgroundColor: C.violet, borderRadius: 14, paddingVertical: 15, marginTop: 18, alignItems: 'center' },
  primaryText: { color: '#fff', fontSize: 16, fontWeight: '800' },
  secondary: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 12, paddingVertical: 12,
               marginTop: 10, alignItems: 'center' },
  secondaryText: { color: C.text, fontSize: 15, fontWeight: '700' },
  input: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 12, color: C.text,
           paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, marginTop: 10 },
  hint: { color: C.muted, fontSize: 12, marginTop: 8, lineHeight: 17 },
  more: { color: C.violet, fontSize: 14, fontWeight: '700', marginTop: 20 },
  note: { color: C.red, fontSize: 13, marginTop: 8, lineHeight: 18 },
  skip: { color: C.muted, fontSize: 14, textAlign: 'center', marginTop: 22, textDecorationLine: 'underline' },
});
