import { Redirect } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';
import { useApp } from '../lib/app-state';
import { C } from '../lib/theme';

// First run goes to setup; after that, straight to the orbit.
export default function Index() {
  const { ready, settings } = useApp();
  if (!ready) {
    return (
      <View style={{ flex: 1, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={C.pink} />
      </View>
    );
  }
  const known = settings && (settings.username || settings.orcid || settings.keywords.length);
  return <Redirect href={known ? '/home' : '/setup'} />;
}
