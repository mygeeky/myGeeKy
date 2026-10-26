// The four signs on the right of the top strip (lib/signs.ts; the desktop's gui/qt_panel.py StatusSigns): GitHub,
// ORCID, saving to your data repo, your Signals beacon. Lit when on, faint when never set up, red when its access
// stopped working. Saving shows Google Drive's logo when your data is saved there. A tap says what the sign means.
import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import type { Sign } from '../lib/signs';
import { C } from '../lib/theme';

const ICON: Record<Sign['key'], string> = { github: 'logo-github', orcid: '', data: 'cloud-done-outline', beacon: 'radio-outline' };
const LIT: Record<Sign['key'], string> = { github: C.text, orcid: '#a6ce39', data: C.cyan, beacon: C.pink };
// Google Drive's logo (the desktop's DRIVE_LOGO in gui/qt_panel.py)
const DRIVE: [string, string][] = [
  ['m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8h-27.5c0 1.55.4 3.1 1.2 4.5z', '#0066da'],
  ['m43.65 25-13.75-23.8c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44a9.06 9.06 0 0 0 -1.2 4.5h27.5z', '#00ac47'],
  ['m73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5h-27.502l5.852 11.5z', '#ea4335'],
  ['m43.65 25 13.75-23.8c-1.35-.8-2.9-1.2-4.5-1.2h-18.5c-1.6 0-3.15.45-4.5 1.2z', '#00832d'],
  ['m59.8 53h-32.3l-13.75 23.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z', '#2684fc'],
  ['m73.4 26.5-12.7-22c-.8-1.4-1.95-2.5-3.3-3.3l-13.75 23.8 16.15 28h27.45c0-1.55-.4-3.1-1.2-4.5z', '#ffba00'],
];

function DriveLogo() {
  return <Svg width={13} height={12} viewBox="0 0 87.3 78">{DRIVE.map(([d, fill]) => <Path key={fill} d={d} fill={fill} />)}</Svg>;
}

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
              : s.icon === 'drive' ? <DriveLogo />
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
