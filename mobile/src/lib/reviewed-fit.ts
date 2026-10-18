// The Protocols tab shows only the few reviewed protocols that fit your field best, then "See all".
// A port of the desktop's protocols.by_fit and qt_panel.reviewed_heading / see_all_text, so both apps pick
// the same ones and say the same words (tests/test_phone_reviewed_match_desktop.py runs this file in Node).
import { match, type Weights } from './interests';

export const REVIEWED_SHOWN = 3;

type Fittable = { skill?: string; goal?: string; title?: string; summary?: string;
  stages?: { title?: string; skills?: string[] }[] };

function fitText(p: Fittable): string {
  const stages = p.stages ?? [];
  return [p.skill ?? '', p.goal ?? '', p.title ?? '', p.summary ?? '', ...stages.map((s) => s.title ?? ''),
    ...stages.flatMap((s) => s.skills ?? [])].join(' ');
}

/** Best fit to your field first; equal fits keep the maker's order. */
export function byFit<T extends Fittable>(protocols: T[], weights: Weights): T[] {
  return protocols.map((p, i) => ({ p, i, fit: match(fitText(p), weights)[0] }))
    .sort((a, b) => b.fit - a.fit || a.i - b.i).map((x) => x.p);
}

export const reviewedHeading = (some: boolean) => (some ? '✓ REVIEWED FOR YOUR FIELD' : '✓ REVIEWED PROTOCOLS');
export const seeAllText = (n: number, showingAll: boolean) => (showingAll ? 'Show fewer' : `See all ${n} reviewed protocols ›`);
