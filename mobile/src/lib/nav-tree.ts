// How you move around: six groups, their sections, and a section's parts -- the orbit zoom and the folded dock.
// A port of the desktop's navtree.py (tests/test_navtree.py checks both agree): tap a group and its sections take
// its place, with a back planet first; tap a section with parts and its parts appear; tap a part to open it.
// The tree below hangs the phone's own pages under the shared groups.
import type { SectionId } from './sections';

export type Node = { id: string; label: string; color: string; icon: string; tab: string; part: string; children: Node[]; parent: Node | null };
type Raw = { id: string; label: string; color?: string; icon?: string; tab?: string; part?: string; children?: Raw[] };

export const GROUPS = [
  { id: 'you', label: 'You', color: '#ffd24a' },
  { id: 'grow', label: 'Grow', color: '#4ade80' },
  { id: 'world', label: 'World', color: '#eab308' },
  { id: 'circle', label: 'Circle', color: '#ff6fd8' },
  { id: 'repos', label: 'Repos', color: '#7fd8ff' },
  { id: 'chances', label: 'Chances', color: '#f472b6' },
];
export const ROOT_LABEL = 'All';
export const MAX_PER_ROW = 6;

export function finish(raw: Raw, parent: Node | null = null): Node {
  const n: Node = { id: raw.id, label: raw.label, color: raw.color || parent?.color || '#ff6fd8', icon: raw.icon ?? '', tab: raw.tab ?? '',
    part: raw.part ?? '', children: [], parent };
  n.children = (raw.children ?? []).map((c) => finish(c, n));
  return n;
}

export function walk(root: Node): Node[] {
  return [root, ...root.children.flatMap(walk)];
}

export const find = (root: Node, id: string): Node | null => walk(root).find((n) => n.id === id) ?? null;

export function path(n: Node | null): Node[] {
  const out: Node[] = [];
  for (let x = n; x; x = x.parent) out.unshift(x);
  return out;
}

export const firstLeaf = (n: Node): Node => (n.children.length ? firstLeaf(n.children[0]) : n);

/** The page you're on: the node for this tab and part; else the tab's own node (its first page, if it has parts);
 *  else the first page of that tab anywhere. */
export function leafFor(root: Node, tab: string, part = ''): Node | null {
  const nodes = walk(root);
  const exact = nodes.find((n) => n.tab === tab && n.part === part && !n.children.length);
  if (exact) return exact;
  const own = nodes.find((n) => n.tab === tab && !n.part);
  if (own) return own.children.length ? firstLeaf(own) : own;
  return nodes.find((n) => n.tab === tab && !n.children.length) ?? null;
}

/** What a level shows: a back planet (where it goes, and what it says) unless at the top, then the children. */
export function level(at: Node) {
  const p = at.parent;
  return { back: p ? { to: p.id, label: p.parent ? p.label : ROOT_LABEL, color: p.color } : null, items: at.children.map((c) => c.id) };
}

/** How many planets go in each row of the folded dock. */
export function rows(count: number): number[] {
  if (count <= MAX_PER_ROW) return [count];
  const first = Math.floor((count + 1) / 2);
  return [first, count - first];
}

/** A planet was tapped at a level: where the level goes and which page is open now (see navtree.tap). */
export function tap(root: Node, atId: string, pickedId: string, openId: string): { at: string; open: string } {
  const at = find(root, atId) ?? root, opened = find(root, openId);
  if (pickedId === 'back') return { at: (at.parent ?? root).id, open: openId };
  const picked = find(root, pickedId);
  if (!picked) return { at: at.id, open: openId };
  if (picked.children.length) {
    const keep = !!opened && path(opened).includes(picked);
    return { at: picked.id, open: keep ? openId : firstLeaf(picked).id };
  }
  return { at: at.id, open: picked.id };
}

export function ordered(ids: string[], hasGitHub: boolean, needsGitHub: readonly string[]): string[] {
  if (hasGitHub) return [...ids];
  return [...ids.filter((i) => !needsGitHub.includes(i)), ...ids.filter((i) => needsGitHub.includes(i))];
}

// --------------------------------------------------------------------------- the phone's tree
// A node's `tab` is the section it opens (SectionId), `part` the part within it; `icon` an Ionicons name.
export const PHONE_NEEDS_GITHUB = ['live', 'people', 'activity', 'signals'];
const G = Object.fromEntries(GROUPS.map((g) => [g.id, g]));
const leaf = (tab: SectionId, part: string, label: string, icon: string): Raw => ({ id: `${tab}:${part}`, label, icon, tab, part });

export function phoneTree(hasGitHub: boolean, admin: boolean): Node {
  const circle: Record<string, Raw> = {
    live: { id: 'live', label: 'Live', icon: 'flash-outline', tab: 'live' },
    people: { id: 'people', label: 'People', icon: 'people-outline', tab: 'people' },
    activity: { id: 'activity', label: 'Activity', icon: 'pulse-outline', tab: 'activity' },
    signals: { id: 'signals', label: 'Signals', icon: 'radio-outline', tab: 'signals' },
  };
  return finish({ id: 'home', label: 'Home', icon: 'planet-outline', children: [
    { ...G.you, icon: 'person-outline', children: [
      leaf('you', 'month', 'My month', 'ribbon-outline'), leaf('you', 'model', 'Model', 'analytics-outline'),
      leaf('you', 'badges', 'Badges', 'medal-outline'), leaf('you', 'more', 'Settings', 'settings-outline'),
      leaf('you', 'ideas', 'Ideas', 'bulb-outline'), ...(admin ? [leaf('you', 'admin', 'Admin', 'shield-outline')] : [])] },
    { ...G.grow, icon: 'leaf-outline', children: [
      leaf('grow', 'highlights', 'Highlights', 'sparkles-outline'), leaf('grow', 'skills', 'Skills', 'trending-up-outline'),
      leaf('grow', 'paths', 'Protocols', 'compass-outline'), leaf('grow', 'quiz', 'Quiz', 'trophy-outline'),
      leaf('grow', 'learn', 'Learn', 'library-outline'), leaf('grow', 'wins', 'Wins', 'happy-outline'),
      leaf('grow', 'collab', 'People', 'hand-left-outline')] },
    { ...G.world, icon: 'earth-outline', children: [
      { id: 'news', label: 'News', icon: 'newspaper-outline', tab: 'news', children: [
        leaf('news', 'airace', 'AI race', 'flag-outline'), leaf('news', 'headlines', 'Headlines', 'reader-outline'),
        leaf('news', 'discuss', 'Papers & talk', 'chatbubbles-outline')] },
      { id: 'papers', label: 'Papers', icon: 'document-text-outline', tab: 'papers' },
      { id: 'models', label: 'AI models', icon: 'hardware-chip-outline', tab: 'models' },
      { id: 'launches', label: 'Launches', icon: 'rocket-outline', tab: 'launches' }] },
    { ...G.circle, icon: 'people-circle-outline', children: ordered(Object.keys(circle), hasGitHub, PHONE_NEEDS_GITHUB).map((k) => circle[k]) },
    { ...G.repos, icon: 'git-branch-outline', children: [leaf('repos', 'help', 'Help out', 'construct-outline'), leaf('repos', 'rising', 'Rising', 'stats-chart-outline')] },
    { ...G.chances, icon: 'briefcase-outline', children: [
      leaf('chances', 'seasons', 'Seasons', 'calendar-outline'), leaf('chances', 'jobs', 'Jobs', 'briefcase-outline'),
      leaf('chances', 'funding', 'Funding', 'cash-outline'), leaf('chances', 'conferences', 'Conferences', 'mic-outline')] },
  ] });
}
