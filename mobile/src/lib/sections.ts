// The orbit's planets: what each one is, and its list of things, built from the feeds.
import type Ionicons from '@expo/vector-icons/Ionicons';
import { timeAgo } from './app-state';
import type { BoardRow } from './board';
import { NEWS_BADGES, type NewsItem } from './news';
import type { Contribution } from './contribute';
import { Repo } from './github';
import { Headline, kindOf } from './headlines';
import { Event } from './live';
import { Launch } from './market';
import type { Learn } from './model-repo';
import { Model } from './models';
import { Person } from './people';
import { Paper } from './research';
import { C, BADGES, tint } from './theme';

export type IconName = keyof typeof Ionicons.glyphMap;
export type SectionId = 'feed' | 'live' | 'people' | 'researchers' | 'activity' | 'signals' | 'grow' | 'news' | 'papers' | 'repos' | 'models' | 'launches'
  | 'chances' | 'you' | 'market' | 'discuss' | 'help';     // market: Repos → 📈 Rising, discuss: News → Papers & discussions

export type Section = { id: SectionId; label: string; color: string; icon: IconName; about: string };

export const SECTIONS: Record<SectionId, Section> = {
  feed: { id: 'feed', label: 'Home', color: '#a78bfa', icon: 'home-outline', about: 'New things from everywhere, learning what you enjoy.' },
  live: { id: 'live', label: 'Live', color: '#ff6fd8', icon: 'flash-outline', about: 'New faces and the latest moves around you.' },
  people: { id: 'people', label: 'People', color: '#7fd8ff', icon: 'people-outline', about: 'People building the tools of your field, and who follows you.' },
  researchers: { id: 'researchers', label: 'Researchers', color: '#c4b5fd', icon: 'school-outline', about: 'People who publish: new preprints and papers from the people you follow.' },
  activity: { id: 'activity', label: 'Activity', color: '#34d399', icon: 'pulse-outline', about: 'What the people you follow are doing on GitHub.' },
  signals: { id: 'signals', label: 'Signals', color: '#a78bfa', icon: 'radio-outline', about: 'Private thank-yous and collab invites between myGeeKy users.' },
  grow: { id: 'grow', label: 'Grow', color: '#4ade80', icon: 'leaf-outline', about: 'Rising skills to learn, protocols to learn them, your wins and collaborators.' },
  news: { id: 'news', label: 'News', color: '#eab308', icon: 'newspaper-outline', about: 'AI labs, journals and the tech press, ranked by your interests.' },
  papers: { id: 'papers', label: 'Papers', color: '#22c55e', icon: 'document-text-outline', about: 'Rising in your field: papers gaining citations fastest.' },
  repos: { id: 'repos', label: 'Repos', color: '#7fd8ff', icon: 'git-branch-outline', about: 'Repos in your field where your skills would be welcome, with open starter issues.' },
  models: { id: 'models', label: 'AI models', color: '#ffc457', icon: 'hardware-chip-outline', about: 'Trending on Hugging Face: your field first, then everywhere.' },
  launches: { id: 'launches', label: 'Launches', color: '#ff6fd8', icon: 'rocket-outline', about: 'Today on Product Hunt, the ones in your field first.' },
  chances: { id: 'chances', label: 'Chances', color: '#f472b6', icon: 'briefcase-outline', about: 'Verified jobs, funding and conferences, checked by hand.' },
  market: { id: 'market', label: 'Repos', color: '#7fd8ff', icon: 'trending-up-outline', about: 'The popular, active projects your field runs on, ranked by momentum like a market board.' },
  discuss: { id: 'discuss', label: 'News', color: '#eab308', icon: 'chatbubbles-outline', about: 'New preprints and discussions matching your interests: arXiv, bioRxiv and Hacker News.' },
  you: { id: 'you', label: 'You', color: '#ffd24a', icon: 'person-outline', about: 'Your month and rank, your model, your badges and your settings.' },
  help: { id: 'help', label: 'Help', color: '#2dd4bf', icon: 'help-circle-outline', about: 'Tours with GeeKOc, and answers to how and why myGeeKy works.' },
};

export const INNER: SectionId[] = ['live', 'people', 'activity', 'signals', 'grow'];
export const OUTER: SectionId[] = ['news', 'papers', 'repos', 'models', 'launches', 'chances'];
export const RING_NAME = { inner: 'YOUR CIRCLE', outer: 'THE WORLD', you: 'THE CENTRE' };

export { NEEDS_GITHUB_IDS, ordered } from './tab-order';

export type Row = {
  id: string; title: string; sub: string; right?: string; url: string; action: string;
  avatar?: string; letter?: string; letterBg?: string; letterFg?: string; login?: string;
  kind: string; cat?: string; explore?: boolean;      // what opening it counts as, for badges
  more?: { text: string[]; links: [string, string][] };  // shown when the row is open (a summary, a repo's why and starter issues)
  section?: string;                                     // a heading above the first row of each part, as on the desktop
  board?: BoardRow;                                     // a row of the 📈 Rising board: drawn with its rank, movement and sparkline
  learn?: Learn;                                      // what it teaches your model (as the desktop's record_click)
};

const fmt = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : String(n));
const profile = (login: string) => `https://github.com/${login}`;

function eventRow(e: Event): Row {
  return {
    id: `e${e.id}`, title: e.actor, sub: `${e.icon} ${e.verb}${e.repo ? ` · ${e.repo.split('/')[1] ?? e.repo}` : ''}`,
    right: timeAgo(e.at), url: e.repo ? `https://github.com/${e.repo}` : profile(e.actor),
    action: e.repo ? `Open ${e.repo.split('/')[1] ?? e.repo} on GitHub` : 'Open profile on GitHub', avatar: e.avatar, kind: 'repo', login: e.actor,
  };
}

function personRow(p: Person, why = p.why): Row {
  return { id: `p${p.login}`, title: p.login, sub: why, url: profile(p.login), action: 'At a glance', avatar: p.avatar, kind: 'person', login: p.login,
    learn: { kind: 'person', text: p.repo?.split('/')[1] ?? '', source: p.login } };   // the repo's own name: never a login
}

export type Feeds = {
  live?: { events: Event[]; following: number } | null;
  people?: { followBack: Person[]; field: Person[] } | null;
  headlines?: { items: Headline[] } | null;
  research?: { rising: Paper[]; tools: Paper[] } | null;
  repos?: { contribute: Contribution[] | null; popular: Repo[] } | null;
  market?: { rows: BoardRow[]; updatedAt: string } | null;
  discuss?: { items: NewsItem[]; errors: string[] } | null;
  models?: { field: Model[]; trending: Model[] } | null;
  launches?: Launch[] | null;
};

export function rowsFor(id: SectionId, f: Feeds): Row[] {
  switch (id) {
    case 'live': {
      const faces = (f.people?.followBack ?? []).slice(0, 4).map((p) => personRow(p, "follows you · you don't follow back yet"));
      return [...faces, ...(f.live?.events ?? []).slice(0, 6).map(eventRow)];
    }
    case 'activity':
      return (f.live?.events ?? []).map(eventRow);
    case 'people':
      return [...(f.people?.field ?? []).map((p) => personRow(p)), ...(f.people?.followBack ?? []).map((p) => personRow(p, 'follows you'))];
    case 'news':
      return (f.headlines?.items ?? []).map((h) => {
        const l = kindOf(h);
        return {
          id: `h${h.id}`, title: h.title, sub: `${h.explore ? '🌍 ' : ''}${h.source}${h.match.length && !h.explore ? ` · ${h.match.slice(0, 2).join(', ')}` : ''}`,
          right: timeAgo(h.published), url: h.link, action: `Read on ${h.source}`,
          letter: l, letterBg: BADGES[l].color, letterFg: BADGES[l].text,
          kind: l === 'P' ? 'paper' : 'headline', cat: h.category, explore: h.explore,
          section: h.explore ? '🌍 THE BIG PICTURE' : 'FOR YOUR WORK',
          more: h.summary ? { text: [h.summary], links: [] } : undefined,
          learn: { kind: 'news', text: h.title, topics: h.match, source: h.id },
        };
      });
    case 'papers':
      return [...(f.research?.rising ?? []).map((p) => [p, false] as const), ...(f.research?.tools ?? []).map((p) => [p, true] as const)].map(([p, tool], i) => ({
        id: `r${i}${p.id}`, title: p.title,
        sub: tool ? `cited ${p.cited} · ${p.venue || 'preprint'}${p.repos[0] ? ` · code: ${p.repos[0]}` : ''}` : `🔥 ${p.velocity}/month · ${p.venue || 'preprint'} · cited ${p.cited}`,
        section: tool ? '🛠️ TOOLS WITH PAPERS' : '🔥 RISING IN YOUR FIELD',
        more: { text: [p.authors.length ? `by ${p.authors.slice(0, 3).join(', ')}${p.authors.length > 3 ? ' et al.' : ''}` : '', p.summary ?? ''].filter(Boolean),
          links: p.repos.slice(0, 2).map((r) => [`💻 Code: ${r}`, `https://github.com/${r}`] as [string, string]) },
        right: p.date ? p.date.slice(0, 4) : '', url: p.url, action: 'Read the paper',
        letter: 'P', letterBg: BADGES.P.color, letterFg: BADGES.P.text, kind: 'paper', cat: 'science',
        learn: { kind: 'news', text: p.title, topics: p.match, source: p.id },
      }));
    case 'repos':
      if (f.repos?.contribute) {          // the desktop's Repos: where your skills would be welcome
        return f.repos.contribute.map((r) => ({
          id: `c${r.full_name}`, title: r.full_name, sub: [r.explore ? '🔭' : '', r.language, `★${fmt(r.stars)}`,
            r.starter_issues.length ? `${r.starter_issues.length} starter issue${r.starter_issues.length === 1 ? '' : 's'}` : ''].filter(Boolean).join(' · '),
          right: r.score ? r.score.toFixed(2) : '', url: r.repo_url, action: 'Open on GitHub', avatar: r.owner_avatar_url || undefined,
          letter: '📦', letterBg: tint(0.10), letterFg: C.text, kind: 'repo', explore: r.explore,
          more: { text: [r.description.slice(0, 160), r.reasons.length ? `why: ${r.reasons.join('; ')}` : ''].filter(Boolean),
            links: [...r.starter_issues.slice(0, 2).map((i) => [`→ ${i.title.length > 100 ? `${i.title.slice(0, 97)}…` : i.title}`, i.url] as [string, string]),
              ['🍴 Fork it on GitHub', r.fork_url]] },
          learn: { kind: 'repo', text: `${r.full_name.replace('/', ' ')} ${r.description} ${r.language}`, topics: r.topics, source: r.full_name },
        }));
      }
      return (f.repos?.popular ?? []).map((r, i) => ({
        id: `g${r.full_name}`, title: r.full_name.split('/')[1], sub: [r.full_name.split('/')[0], r.language, `pushed ${timeAgo(r.pushed_at)}`].filter(Boolean).join(' · '),
        right: `★ ${fmt(r.stargazers_count)}`, url: r.html_url, action: 'Open on GitHub',
        letter: String(i + 1), letterBg: tint(0.10), letterFg: C.text, kind: 'repo',
        learn: { kind: 'repo', text: `${r.full_name.replace('/', ' ')} ${r.description ?? ''} ${r.language ?? ''}`, topics: r.topics ?? [], source: r.full_name },
      }));
    case 'discuss':
      return (f.discuss?.items ?? []).map((n) => {
        const [badge, color] = NEWS_BADGES[n.source];
        return {
          id: `d${n.id}`, title: n.title, url: n.url, right: timeAgo(n.published),
          sub: [n.explore ? '🔭' : '', badge, n.category ?? '', n.source === 'hackernews' ? n.summary : n.match.slice(0, 2).join(', ')].filter(Boolean).join(' · '),
          action: n.source === 'hackernews' ? 'Read the discussion' : `Read on ${badge}`,
          letter: ({ arxiv: 'aX', biorxiv: 'bR', hackernews: 'HN' } as const)[n.source], letterBg: color, letterFg: '#ffffff', kind: n.source === 'hackernews' ? 'news' : 'paper', explore: n.explore,
          section: n.explore ? '🔭 NEW TERRITORY' : 'FOR YOUR WORK',
          more: { text: n.source === 'hackernews' ? [] : [n.summary].filter(Boolean),
            links: n.story_url ? [['🔗 The story itself', n.story_url] as [string, string]] : [] },
          learn: { kind: 'news', text: n.title, topics: n.match, source: n.id },
        };
      });
    case 'market':
      return (f.market?.rows ?? []).map((b) => {
        const [owner, name] = b.repo.split('/');
        return {
          id: `b${b.repo}`, title: name, sub: owner, url: b.url, action: 'Open on GitHub', avatar: b.avatar || undefined,
          letter: '📈', letterBg: tint(0.10), letterFg: C.text, kind: 'repo', board: b,
          more: b.description ? { text: [b.description, b.pypi ? `on PyPI as ${b.pypi}` : ''].filter(Boolean), links: [] } : undefined,
          learn: { kind: 'repo', text: `${b.repo.replace('/', ' ')} ${b.description} ${b.language}`, source: b.repo },
        };
      });
    case 'models': {
      const seen = new Set<string>();
      return [...(f.models?.field ?? []).map((m) => [m, true] as const), ...(f.models?.trending ?? []).map((m) => [m, false] as const)]
        .filter(([m]) => !seen.has(m.id) && seen.add(m.id)).map(([m, mine]) => ({
        id: `m${m.id}`, title: m.id.split('/')[1] ?? m.id,
        sub: [m.id.split('/')[0], m.pipeline.replace(/-/g, ' '), `↓ ${fmt(m.downloads)}`, m.trending ? `🔥 ${fmt(m.trending)}` : ''].filter(Boolean).join(' · '),
        section: mine ? 'IN YOUR FIELD' : '🌍 TRENDING EVERYWHERE',
        more: { text: [m.match.length ? `matches ${m.match.slice(0, 4).join(', ')}` : '', m.tags.length ? `tags: ${m.tags.slice(0, 8).join(', ')}` : ''].filter(Boolean), links: [] },
        right: `♥ ${fmt(m.likes)}`, url: m.url, action: 'Open on Hugging Face',
        letter: 'M', letterBg: '#ffc457', letterFg: '#1a1a1a', kind: 'model', cat: 'ai',
        learn: { kind: 'repo', text: `${m.id.replace('/', ' ')} ${m.pipeline}`, topics: m.tags, source: m.id },
      }));
    }
    case 'launches':
      return (f.launches ?? []).map((l) => ({
        id: `l${l.id}`, title: l.name, sub: l.match.length ? `${l.tagline} · your field: ${l.match.slice(0, 2).join(', ')}` : l.tagline,
        url: l.url, action: 'Open on Product Hunt', letter: 'L', letterBg: '#ff6fd8', letterFg: '#1a1a1a', kind: 'launch',
      }));
    default:
      return [];
  }
}
