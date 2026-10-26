// The four signs on the right of the top strip (lib/signs.ts; the desktop's gui/qt_panel.py StatusSigns): GitHub,
// ORCID, saving to your data repo, your Signals beacon. Lit when on, faint when never set up, red when its access
// stopped working. A tap says what the sign means.
import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { Sign } from '../lib/signs';
import { C } from '../lib/theme';

const ICON: Record<Sign['key'], string> = { github: 'logo-github', orcid: '', data: 'cloud-done-outline', beacon: 'radio-outline' };
const LIT: Record<Sign['key'], string> = { github: C.text, orcid: '#a6ce39', data: C.cyan, beacon: C.pink };

export function StatusSigns({ items, onTip }: { items: Sign[]; onTip: (tip: string) => void }) {
  return (
    <View style={st.row}>
      {items.map((s) => {
        const color = s.state === 'bad' ? C.red : LIT[s.key];
        return (
          <Pressable key={s.key} onPress={() => onTip(s.tip)} hitSlop={6} accessibilityRole="button"
                     accessibilityLabel={`${s.label}: ${s.tip}`}
                     style={[st.sign, { borderColor: color, opacity: s.state === 'off' ? 0.3 : 1 },
                             s.state === 'bad' && { backgroundColor: 'rgba(248,113,113,0.16)' }]}>
            {s.key === 'orcid' ? <Text style={[st.id, { color }]}>iD</Text>
              : <Ionicons name={(s.key === 'data' && s.state === 'bad' ? 'cloud-offline-outline' : ICON[s.key]) as never} size={13} color={color} />}
          </Pressable>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', gap: 5, marginLeft: 'auto', alignSelf: 'center' },
  sign: { width: 24, height: 24, borderRadius: 12, borderWidth: 1.4, alignItems: 'center', justifyContent: 'center' },
  id: { fontSize: 10, fontWeight: '900' },
});
