// mygeeky://orcid?... : ORCID's answer opening the app (via https://mygeeky.org/orcid/).
// Hand it to the sign-in that's waiting, then go back to where it started.
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { finishOrcidSignIn } from '../lib/orcid-login';
import { C } from '../lib/theme';
import { GeekLoader } from '../components/geek-loader';

export default function OrcidReturn() {
  const params = useLocalSearchParams<Record<string, string>>();
  const [lost, setLost] = useState(false);

  useEffect(() => {
    const answer: Record<string, string> = {};
    for (const k of ['access_token', 'state', 'error', 'error_description']) {
      const v = params[k];
      if (typeof v === 'string' && v) answer[k] = v;
    }
    if (finishOrcidSignIn(answer)) {
      if (router.canGoBack()) router.back();
      else router.replace('/setup');
    } else {
      void Promise.resolve().then(() => setLost(true));   // e.g. the phone closed myGeeKy while ORCID was open
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <View style={st.wrap}>
      {lost ? (
        <>
          <Text style={st.title}>Sign in with ORCID again</Text>
          <Text style={st.text}>This answer from ORCID came back after myGeeKy had stopped waiting for it.
            Tap below and sign in once more.</Text>
          <Pressable style={st.button} onPress={() => router.replace('/setup')}>
            <Text style={st.buttonText}>Back to setup</Text>
          </Pressable>
        </>
      ) : <GeekLoader text="Signing you in…" />}
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center', padding: 24 },
  title: { color: C.text, fontSize: 20, fontWeight: '800', textAlign: 'center' },
  text: { color: C.muted, fontSize: 14, lineHeight: 20, textAlign: 'center', marginTop: 8 },
  button: { backgroundColor: C.violet, borderRadius: 14, paddingVertical: 13, paddingHorizontal: 22, marginTop: 18 },
  buttonText: { color: '#fff', fontWeight: '800', fontSize: 15 },
});
