import { Redirect } from 'expo-router';
import { View } from 'react-native';
import { useApp } from '../lib/app-state';
import { C } from '../lib/theme';
import { GeekLoader } from '../components/geek-loader';

// First run goes to setup; after that, straight to the orbit.
export default function Index() {
  const { ready, settings } = useApp();
  if (!ready) {
    return (
      <View style={{ flex: 1, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center' }}>
        <GeekLoader text="" />
      </View>
    );
  }
  const known = settings && (settings.started || settings.username || settings.orcid || settings.openalex || settings.keywords.length);
  return <Redirect href={known ? '/home' : '/setup'} />;
}
