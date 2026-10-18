// Tab and planet order: a port of the desktop's qt_panel.tab_order (tests/test_tab_order.py runs this in Node).
import type { SectionId } from './sections';

// The planets that, without a GitHub account, show nothing but "add GitHub" (home.tsx NEEDS_GITHUB).
export const NEEDS_GITHUB_IDS: SectionId[] = ['live', 'people', 'activity', 'signals'];

/** The usual order, except that without GitHub the planets that would only say "add GitHub" go to the end,
 *  so the first ones are the ones that work. You is always first (the centre, and the dock's first). The
 *  desktop orders its tabs by the same rule (qt_panel.tab_order). */
export function ordered(ids: SectionId[], hasGitHub: boolean): SectionId[] {
  if (hasGitHub) return ids;
  return [...ids.filter((id) => !NEEDS_GITHUB_IDS.includes(id)), ...ids.filter((id) => NEEDS_GITHUB_IDS.includes(id))];
}
