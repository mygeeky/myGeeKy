// Small preferences kept on this phone only.
import AsyncStorage from '@react-native-async-storage/async-storage';

const DOCK_KEY = 'mygeeky.dockIdle';
export const DOCK_IDLE_DEFAULT = 6000;
export const DOCK_IDLE_CHOICES: [number, string][] = [[3000, '3 s'], [6000, '6 s'], [12000, '12 s'], [0, 'Never']];

/** How long the dock stays up untouched before it folds to a handle; 0 = never. */
export async function dockIdleMs(): Promise<number> {
  try {
    const raw = await AsyncStorage.getItem(DOCK_KEY);
    const v = Number(raw);
    return raw !== null && DOCK_IDLE_CHOICES.some(([ms]) => ms === v) ? v : DOCK_IDLE_DEFAULT;
  } catch {
    return DOCK_IDLE_DEFAULT;
  }
}

export async function setDockIdleMs(ms: number): Promise<void> {
  try { await AsyncStorage.setItem(DOCK_KEY, String(ms)); } catch { /* the default stays */ }
}
