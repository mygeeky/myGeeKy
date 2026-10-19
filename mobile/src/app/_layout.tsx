import Ionicons from '@expo/vector-icons/Ionicons';
import { useFonts } from 'expo-font';
import { router, Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { LoadingIntro } from '../components/loading-intro';
import { ToastProvider } from '../components/toast';
import { AppProvider } from '../lib/app-state';
import '../lib/notify-store';                      // defines the background notification check (notify-store.ts)
import * as Notifications from 'expo-notifications';
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
  // a tapped notification opens the place it is about (Chances, Papers or Grow)
  useEffect(() => {
    const open = (r: Notifications.NotificationResponse | null) => {
      const sel = r?.notification.request.content.data?.sel;
      if (typeof sel === 'string') router.push({ pathname: '/home', params: { sel } });
    };
    Notifications.getLastNotificationResponseAsync().then(open).catch(() => undefined);
    const sub = Notifications.addNotificationResponseReceivedListener(open);
    return () => sub.remove();
  }, []);
  const ready = fontsLoaded || !!fontError;
  return (
    <SafeAreaProvider>
      <View style={{ flex: 1, backgroundColor: C.bg }}>
        {ready ? (
          <AppProvider>
            <ToastProvider>
              <StatusBar style={C.dark ? 'light' : 'dark'} />
              <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: C.bg } }} />
            </ToastProvider>
          </AppProvider>
        ) : null}
        {intro ? <LoadingIntro onDone={() => setIntro(false)} /> : null}
      </View>
    </SafeAreaProvider>
  );
}
