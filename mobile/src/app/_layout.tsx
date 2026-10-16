import Ionicons from '@expo/vector-icons/Ionicons';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { LoadingIntro } from '../components/loading-intro';
import { AppProvider } from '../lib/app-state';
import { C } from '../lib/theme';

// the phone's own splash is just the dark background; the opening animation takes over from it
SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  // the planets' icons: loaded up front, so they never flash in as empty boxes
  const [fontsLoaded, fontError] = useFonts(Ionicons.font);
  const [intro, setIntro] = useState(true);
  useEffect(() => {
    SplashScreen.hideAsync().catch(() => {});
  }, []);
  const ready = fontsLoaded || !!fontError;
  return (
    <SafeAreaProvider>
      <View style={{ flex: 1, backgroundColor: C.bg }}>
        {ready ? (
          <AppProvider>
            <StatusBar style={C.dark ? 'light' : 'dark'} />
            <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: C.bg } }} />
          </AppProvider>
        ) : null}
        {intro ? <LoadingIntro onDone={() => setIntro(false)} /> : null}
      </View>
    </SafeAreaProvider>
  );
}
