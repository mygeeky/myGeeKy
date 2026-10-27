// myGeeKy's colours: the desktop panel's three themes (src/mygeeky/gui/app.py THEMES) -- 🌙 Midnight, ❄️ Frosted
// and 🌌 Aurora -- made solid for a phone screen. The choice is read synchronously at start-up, so every
// screen's styles are built in the right colours; changing it restarts the app (setTheme).
import * as SecureStore from 'expo-secure-store';
import { DevSettings, Platform } from 'react-native';

export type ThemeName = 'midnight' | 'frosted' | 'aurora';
export const THEME_LABELS: [ThemeName, string][] = [['midnight', '🌙 Midnight'], ['frosted', '❄️ Frosted'], ['aurora', '🌌 Aurora']];
const THEME_KEY = 'mygeeky.theme';

const THEMES: Record<ThemeName, {
  dark: boolean; deep: string; bg: string; panel: string; sheet: string; raised: string; text: string; ink: string;
  tint: string; pink: string; violet: string; cyan: string; green: string; amber: string; red: string;
}> = {
  midnight: { dark: true, deep: '#0d0d16', bg: '#12121c', panel: '#14141f', sheet: '#1a1a28', raised: '#1c1c2c',
    text: '#f0f0f5', ink: '240,240,245', tint: '255,255,255',
    pink: '#ff6fd8', violet: '#7a5cff', cyan: '#7fd8ff', green: '#34d399', amber: '#ffc457', red: '#f87171' },
  frosted: { dark: false, deep: '#e9e3dc', bg: '#f4efe9', panel: '#fbf8f4', sheet: '#fffdfa', raised: '#ffffff',
    text: '#241f1a', ink: '36,31,26', tint: '0,0,0',
    pink: '#c0367f', violet: '#6d28d9', cyan: '#0b5f8f', green: '#047857', amber: '#a16207', red: '#b91c1c' },
  aurora: { dark: true, deep: '#160f33', bg: '#1d1747', panel: '#272463', sheet: '#2f2a6e', raised: '#33296b',
    text: '#ffffff', ink: '255,255,255', tint: '255,255,255',
    pink: '#ff6fd8', violet: '#8b6dff', cyan: '#a5f3fc', green: '#6ee7b7', amber: '#fde68a', red: '#fca5a5' },
};

function stored(): ThemeName {
  try {
    const v = Platform.OS === 'web' ? globalThis.localStorage?.getItem(THEME_KEY) : SecureStore.getItem(THEME_KEY);
    return v === 'frosted' || v === 'aurora' ? v : 'midnight';
  } catch {
    return 'midnight';
  }
}

export const THEME: ThemeName = stored();
const T = THEMES[THEME];

export const C = {
  dark: T.dark,
  deep: T.deep,            // behind everything (around the panel)
  bg: T.bg,
  panel: T.panel,          // the main panel
  sheet: T.sheet,          // sheets that slide up
  raised: T.raised,        // a planet or dot that is not chosen
  card: `rgba(${T.tint},0.05)`,
  cardHi: `rgba(${T.tint},0.09)`,
  line: `rgba(${T.tint},0.10)`,
  text: T.text,
  muted: `rgba(${T.ink},0.66)`,
  pink: T.pink,
  violet: T.violet,
  cyan: T.cyan,
  green: T.green,
  amber: T.amber,
  red: T.red,
};

const rgb = (hex: string) => [0, 2, 4].map((i) => parseInt(hex.replace('#', '').slice(i, i + 2), 16));
const hexOf = (c: number[]) => '#' + c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
const lum = (c: number[]) => {
  const [r, g, b] = c.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a: number[], b: number[]) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };

/** A colour moved toward black (Frosted) or white (the dark themes) until it reads on the panel, like the
 *  desktop's logic.readable. */
export function readable(hex: string, minRatio = 3.5): string {
  let c = rgb(hex);
  const bg = rgb(T.panel), toward = T.dark ? 255 : 0;
  for (let i = 0; i < 24 && contrast(c, bg) < minRatio; i++) c = c.map((v) => v + (toward - v) * 0.12);
  return hexOf(c);
}

/** A badge's colours from its tier colour (the desktop's qt_panel._badge_icon): on Frosted a solid pastel inside and
 *  a ring and word dark enough to show; on the dark themes the tier's colour glowing through. */
export function medal(hex: string, locked = false): { ring: string; fill: string; text: string } {
  const c = rgb(hex);
  if (T.dark) return { ring: hex, fill: `rgba(${c.join(',')},${locked ? 0.07 : 0.24})`, text: readable(hex) };
  const base = rgb(T.panel), k = locked ? 0.12 : 0.34;
  return { ring: readable(hex, 2.6), fill: hexOf(base.map((v, i) => v + (c[i] - v) * k)), text: readable(hex) };
}

/** A see-through layer over the background: white on the dark themes, black on Frosted. */
export const tint = (a: number) => `rgba(${T.tint},${a})`;
/** The text colour, faded. */
export const ink = (a: number) => `rgba(${T.ink},${a})`;

/** Keep the choice and restart, so every screen is drawn again in the new colours. */
export async function setTheme(name: ThemeName): Promise<boolean> {
  try {
    if (Platform.OS === 'web') globalThis.localStorage?.setItem(THEME_KEY, name);
    else SecureStore.setItem(THEME_KEY, name);
  } catch {
    return false;
  }
  try {
    const Updates = await import('expo-updates');
    await Updates.reloadAsync();
    return true;
  } catch {
    try { DevSettings.reload(); return true; } catch { return false; }
  }
}

// one letter, one meaning (as on the desktop): P paper, N news, D discussion, A announcement
export const BADGES: Record<string, { label: string; color: string; text: string }> = {
  P: { label: 'paper', color: '#22c55e', text: '#ffffff' },
  N: { label: 'news', color: '#eab308', text: '#1a1a1a' },
  D: { label: 'discussion', color: '#38bdf8', text: '#ffffff' },
  A: { label: 'announcement', color: '#a78bfa', text: '#ffffff' },
};

