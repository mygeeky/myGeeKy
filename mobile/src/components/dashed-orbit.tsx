// The dotted ring around a planet that opens into more parts (the orbit and the folded dock), so you can expect more
// inside. A planet that opened, now in the orbit's centre, is drawn without it. The ring holds still: it used to
// turn, and seven turning rings kept the phone redrawing 60 times a second (16% CPU with the dock open, 2% still).
// Desktop: still the old mark under the planet (PARITY.md).
import Svg, { Circle } from 'react-native-svg';
import { View } from 'react-native';

export const RING_GAP = 6;                 // from the planet's edge to the ring

/** The ring for a planet of `size` (place it inside the planet's view: it reaches RING_GAP beyond the edge). */
export function DashedOrbit({ size, color }: { size: number; color: string }) {
  const d = size + 2 * RING_GAP, r = size / 2 + RING_GAP - 2;
  return (
    <View pointerEvents="none" style={{ position: 'absolute', left: -RING_GAP - 2, top: -RING_GAP - 2, width: d, height: d }}>
      <Svg width={d} height={d}>
        <Circle cx={d / 2} cy={d / 2} r={r} fill="none" stroke={color} strokeWidth={2} strokeDasharray="3 4" strokeLinecap="round" />
      </Svg>
    </View>
  );
}
