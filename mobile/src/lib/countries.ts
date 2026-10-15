// The country a listing is in, read off the place it names: a port of curated.py's `country_of`.
//
// Boards write a place every way there is -- "Lyon, France", "Cambridge, Cambridgeshire, UK",
// "Dortmund, Nordrhein-Westfalen (DE)", and American ones name only the state and leave the country off
// entirely. All of those are common enough to be worth reading rather than losing. A place that names no
// country gives "" rather than inventing one, and a filter is built from what the listings actually say,
// so it can never offer a country with nothing behind it.
const ALIAS: Record<string, string> = {
  uk: 'United Kingdom', 'u.k.': 'United Kingdom', england: 'United Kingdom', scotland: 'United Kingdom',
  wales: 'United Kingdom', britain: 'United Kingdom', 'great britain': 'United Kingdom',
  'northern ireland': 'United Kingdom',
  usa: 'United States', 'u.s.a.': 'United States', us: 'United States', 'u.s.': 'United States',
  america: 'United States', 'united states of america': 'United States',
  uae: 'United Arab Emirates', ksa: 'Saudi Arabia', korea: 'South Korea',
  'republic of korea': 'South Korea', czechia: 'Czech Republic', holland: 'Netherlands',
  'the netherlands': 'Netherlands', deutschland: 'Germany', espana: 'Spain', turkey: 'Türkiye',
  turkiye: 'Türkiye', swiss: 'Switzerland', russia: 'Russian Federation', 'ivory coast': "Côte d'Ivoire",
};
export const COUNTRIES = [
  'Algeria', 'Argentina', 'Australia', 'Austria', 'Bahrain', 'Bangladesh', 'Belgium', 'Brazil', 'Bulgaria',
  'Canada', 'Chile', 'China', 'Colombia', 'Croatia', 'Cyprus', 'Czech Republic', "Côte d'Ivoire",
  'Denmark', 'Egypt', 'Estonia', 'Ethiopia', 'Finland', 'France', 'Germany', 'Ghana', 'Greece', 'Hong Kong',
  'Hungary', 'Iceland', 'India', 'Indonesia', 'Iran', 'Iraq', 'Ireland', 'Israel', 'Italy', 'Japan',
  'Jordan', 'Kenya', 'Kuwait', 'Latvia', 'Lebanon', 'Libya', 'Lithuania', 'Luxembourg', 'Malaysia',
  'Mexico', 'Morocco', 'Netherlands', 'New Zealand', 'Nigeria', 'Norway', 'Oman', 'Pakistan', 'Palestine',
  'Peru', 'Philippines', 'Poland', 'Portugal', 'Qatar', 'Romania', 'Russian Federation', 'Rwanda',
  'Saudi Arabia', 'Senegal', 'Serbia', 'Singapore', 'Slovakia', 'Slovenia', 'South Africa', 'South Korea',
  'Spain', 'Sudan', 'Sweden', 'Switzerland', 'Syria', 'Taiwan', 'Tanzania', 'Thailand', 'Tunisia',
  'Türkiye', 'Uganda', 'Ukraine', 'United Arab Emirates', 'United Kingdom', 'United States', 'Uruguay',
  'Uzbekistan', 'Vietnam', 'Yemen', 'Zambia', 'Zimbabwe',
];
const BY_NAME: Record<string, string> = Object.fromEntries(COUNTRIES.map((c) => [c.toLowerCase(), c]));
const NOWHERE = new Set(['remote', 'online', 'anywhere', 'worldwide', 'virtual', 'hybrid', 'europe', 'eu', 'global']);
const CODES: Record<string, string> = {
  de: 'Germany', us: 'United States', gb: 'United Kingdom', uk: 'United Kingdom', fr: 'France',
  nl: 'Netherlands', ch: 'Switzerland', se: 'Sweden', no: 'Norway', dk: 'Denmark', fi: 'Finland',
  at: 'Austria', be: 'Belgium', es: 'Spain', it: 'Italy', pt: 'Portugal', ie: 'Ireland', pl: 'Poland',
  cz: 'Czech Republic', cn: 'China', jp: 'Japan', kr: 'South Korea', sg: 'Singapore', au: 'Australia',
  nz: 'New Zealand', ca: 'Canada', il: 'Israel', ae: 'United Arab Emirates', sa: 'Saudi Arabia',
  qa: 'Qatar', eg: 'Egypt', za: 'South Africa', in: 'India', br: 'Brazil', tr: 'Türkiye',
};
const US_STATES = new Set([
  'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut', 'delaware',
  'florida', 'georgia', 'hawaii', 'idaho', 'illinois', 'indiana', 'iowa', 'kansas', 'kentucky',
  'louisiana', 'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota', 'mississippi', 'missouri',
  'montana', 'nebraska', 'nevada', 'new hampshire', 'new jersey', 'new mexico', 'new york', 'ohio',
  'oklahoma', 'oregon', 'pennsylvania', 'rhode island', 'south carolina', 'south dakota', 'tennessee',
  'texas', 'utah', 'vermont', 'virginia', 'washington', 'west virginia', 'wisconsin', 'wyoming',
]);
const TAIL_CODE = /\(([A-Za-z]{2})\)\s*$/;

/** The country a place names, or '' when it names none.
 *
 *  Read from the END, because that is where people put the country: "Lyon, France" and
 *  "Cambridge, Cambridgeshire, UK" both give the right answer, and "Lyon" alone gives nothing rather
 *  than inventing a country called Lyon. */
export function countryOf(place: unknown): string {
  const said = String(place ?? '').split(/\s+/).join(' ').trim().slice(0, 120);
  if (!said || NOWHERE.has(said.toLowerCase())) return '';
  const tail = TAIL_CODE.exec(said);                  // "... (DE)" -- the country, written as a code
  if (tail && CODES[tail[1].toLowerCase()]) return CODES[tail[1].toLowerCase()];
  const parts = said.replace(TAIL_CODE, '').split(',').map((p) => p.replace(/^[\s.]+|[\s.]+$/g, ''));
  for (let i = parts.length - 1; i >= 0; i--) {
    const low = parts[i].toLowerCase();
    if (BY_NAME[low]) return BY_NAME[low];
    if (ALIAS[low]) return ALIAS[low];
    if (US_STATES.has(low)) return 'United States';   // an American board naming only the state
  }
  return '';
}

/** Every country these listings are actually in, in order, for a filter to offer. Built from the
 *  listings themselves, so the filter can never offer a country with nothing behind it. */
export function countriesIn(items: { country?: string }[]): string[] {
  return [...new Set(items.map((it) => it.country ?? '').filter(Boolean))].sort((a, b) => a.localeCompare(b));
}
