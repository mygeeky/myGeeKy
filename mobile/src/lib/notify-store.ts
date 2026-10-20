// Notifications on the phone: your choices (all off until you switch a kind on), Android's permission (asked only
// when you switch the first one on), the background check, and the one notification a summary becomes. What's worth
// telling is decided by lib/notify.ts (the same rule as the desktop's notify.py). With no myGeeKy server, the phone
// can only look when Android lets it run in the background (BackgroundTask, at most every CHECK_MINUTES), and each
// time myGeeKy opens; nothing is ever pushed to it from outside.
import { loadRadar } from './datasets';
import { loadCitedBy } from './cited-by';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as BackgroundTask from 'expo-background-task';
import * as Notifications from 'expo-notifications';
import * as TaskManager from 'expo-task-manager';
import { quickProfile } from './app-state';
import { loadLists, ranked } from './curated';
import * as N from './notify';
import * as seasons from './seasons';
import { loadSettings, readCache } from './storage';

const SETTINGS_KEY = 'mygeeky.notify';
const STATE_KEY = 'mygeeky.notify.state';
const ASKED_KEY = 'mygeeky.notify.asked';     // Android can't tell "never asked" from "refused for good": we remember
const TASK = 'mygeeky-notify-check';
const CHECK_MINUTES = 6 * 60;

Notifications.setNotificationHandler({          // shown even when myGeeKy is open (it's rare and you asked for it)
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false }),
});

export async function loadNotify(): Promise<N.Settings> {
  try {
    return N.cleanSettings(JSON.parse((await AsyncStorage.getItem(SETTINGS_KEY)) ?? 'null'));
  } catch {
    return N.defaults();
  }
}

/** 'granted'; 'blocked' (asked before, refused, and Android won't ask again: only its settings can change it);
 *  or 'askable'. Before the first request Android also says "can't ask again", so myGeeKy remembers asking. */
export async function permission(): Promise<'granted' | 'blocked' | 'askable'> {
  try {
    const p = await Notifications.getPermissionsAsync();
    if (p.granted) return 'granted';
    return !p.canAskAgain && (await AsyncStorage.getItem(ASKED_KEY)) ? 'blocked' : 'askable';
  } catch {
    return 'askable';
  }
}

async function ask(): Promise<boolean> {
  const now = await Notifications.getPermissionsAsync();
  if (now.granted) return true;
  if (!now.canAskAgain && (await AsyncStorage.getItem(ASKED_KEY))) return false;      // refused for good
  await AsyncStorage.setItem(ASKED_KEY, '1');
  return (await Notifications.requestPermissionsAsync()).granted;
}

/** Save your choices. Switching the first kind on asks Android first; refused, everything stays off.
 *  {saved, denied}: denied = Android said no (you can allow it in Android's settings). */
export async function saveNotify(next: N.Settings): Promise<{ saved: N.Settings; denied: boolean }> {
  let s = N.cleanSettings(next);
  let denied = false;
  if (s.kinds.length && !(await ask().catch(() => false))) {
    s = { ...s, kinds: [] };
    denied = true;
  }
  await AsyncStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  try {
    if (s.kinds.length) await BackgroundTask.registerTaskAsync(TASK, { minimumInterval: CHECK_MINUTES });
    else if (await TaskManager.isTaskRegisteredAsync(TASK)) await BackgroundTask.unregisterTaskAsync(TASK);
  } catch { /* the check still runs whenever myGeeKy opens */ }
  return { saved: s, denied };
}

/** Look now: if a summary is due and something is worth it, show it (and remember it as told). */
export async function checkNow(now = new Date()): Promise<N.Summary | null> {
  const s = await loadNotify();
  if (!s.kinds.length) return null;
  const raw = JSON.parse((await AsyncStorage.getItem(STATE_KEY)) ?? '{}') ?? {};
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  if (!N.due(s, String(raw.lastSent ?? ''), local, now.getHours())) return null;
  const settings = await loadSettings();
  const lists = await loadLists();
  const weights = settings ? quickProfile(settings).weights : {};
  const byKind: Record<string, unknown[]> = {};
  for (const kind of ['jobs', 'funding', 'conferences'] as const) {
    try {
      byKind[kind] = (await ranked(kind, lists, weights)).items;
    } catch {
      byKind[kind] = [];
    }
  }
  const research = await readCache<{ rising: unknown[] }>('research');
  const cands = N.candidates(local.slice(0, 10), seasons.ranked(seasons.seasonsOf(lists), local.slice(0, 10)), byKind as Record<string, any[]>,
    research?.data?.rising ?? [], lists.highlights ?? [], (await loadCitedBy()).citing ?? [], (await loadRadar()).items ?? []);
  const told: string[] = Array.isArray(raw.told) ? raw.told : [];
  const chosen = N.pick(cands, told, s);
  const out = N.summary(chosen);
  if (!out) return null;
  await Notifications.scheduleNotificationAsync({ content: { title: out.title, body: out.body, data: { sel: out.tab } }, trigger: null });
  await AsyncStorage.setItem(STATE_KEY, JSON.stringify({ lastSent: local, told: N.remember(told, chosen) }));
  return out;
}

// the background look (Android runs it now and then, when it suits the battery)
TaskManager.defineTask(TASK, async () => {
  try {
    await checkNow();
    return BackgroundTask.BackgroundTaskResult.Success;
  } catch {
    return BackgroundTask.BackgroundTaskResult.Failed;
  }
});
