// When a screen throws while drawing, Expo Router shows this instead of closing the app (exported as
// ErrorBoundary from app/_layout.tsx and app/home.tsx). "Try again" redraws; if what was saved last time is what
// breaks it (a list cached by an older version), "Clear saved lists" drops only those caches -- they come back
// on the next refresh -- and starts the app again. Your settings, accounts and what you've learned stay.
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { ErrorBoundaryProps } from 'expo-router';
import { Pressable, Text, View } from 'react-native';
import { C, restartApp } from '../lib/theme';

async function clearCaches() {
  const keys = (await AsyncStorage.getAllKeys()).filter((k) => k.startsWith('mygeeky.cache.'));
  if (keys.length) await AsyncStorage.multiRemove(keys);
}

export function CrashScreen({ error, retry }: ErrorBoundaryProps) {
  const btn = (label: string, onPress: () => void, primary = false) => (
    <Pressable accessibilityRole="button" onPress={onPress}
      style={{ backgroundColor: primary ? C.violet : C.cardHi, borderRadius: 12, paddingVertical: 12, paddingHorizontal: 18, marginTop: 10 }}>
      <Text style={{ color: primary ? '#ffffff' : C.text, fontWeight: '800', fontSize: 15, textAlign: 'center' }}>{label}</Text>
    </Pressable>
  );
  return (
    <View style={{ flex: 1, backgroundColor: C.bg, justifyContent: 'center', padding: 28 }}>
      <Text style={{ fontSize: 44, textAlign: 'center' }}>🐙</Text>
      <Text style={{ color: C.text, fontSize: 20, fontWeight: '800', textAlign: 'center', marginTop: 8 }}>
        Something went wrong on this page
      </Text>
      <Text style={{ color: C.muted, fontSize: 14, textAlign: 'center', marginTop: 8, lineHeight: 20 }}>
        GeeKOc caught it before it closed the app. Try again; if it happens again, clearing the saved lists usually
        fixes it (they come back on the next refresh).
      </Text>
      <Text selectable numberOfLines={4} style={{ color: C.muted, fontSize: 12, textAlign: 'center', marginTop: 12 }}>
        {String(error?.message ?? error)}
      </Text>
      {btn('Try again', () => { retry(); }, true)}
      {btn('Clear saved lists and restart', () => {
        clearCaches().catch(() => undefined)
          .then(() => restartApp())
          .then((ok) => { if (!ok) retry(); });
      })}
    </View>
  );
}
