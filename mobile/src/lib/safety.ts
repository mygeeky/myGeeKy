// What myGeeKy will not teach -- the same refusal as the desktop's safety.py, so the phone behaves
// identically. myGeeKy covers work done at a computer: code, data, statistics, figures and pipelines.
// It does not give protocols, steps, recipes, volumes, conditions or troubleshooting for anything done at a
// bench, with reagents, cells, organisms or instruments.
//
// Why, plainly: a wrong line of R wastes an afternoon; a wrong line at a bench can hurt somebody. myGeeKy
// has one maintainer, cannot review bench safety, cannot know anyone's local rules or training, and cannot
// check what anyone actually does. That work belongs to their lab and their institution.
//
// `allowed()` refuses a skill or goal that names laboratory work, and `blockedSource()` keeps protocol
// repositories, protocol journals and suppliers' method libraries out of every link, wherever one arrives:
// a protocol built here, one from the curated file, one another user published, or a quiz question's source.
//
// Analysing data an experiment produced is NOT bench work, and is welcome.

export const WHY_LAB =
  'myGeeKy only covers work done at a computer — code, data, statistics, figures and pipelines. It '
  + "doesn't give laboratory protocols or bench instructions: that's for your lab, your supervisor and your "
  + 'institution’s own rules. Analysing the data an experiment produced is welcome — try the skill '
  + "you'd analyse it with (R, Python, statistics, plotting).";

const BENCH = new RegExp(
  '\\b(pcr|qpcr|rt-?pcr|ddpcr|electrophoresis|agarose|sds-?page|western\\s*blot|immunoblot|northern\\s*blot|'
  + 'southern\\s*blot|elisa|immunostain\\w*|immunofluorescen\\w*|immunohistochem\\w*|histolog\\w*|'
  + 'cell\\s*cultur\\w*|tissue\\s*cultur\\w*|transfect\\w*|electroporat\\w*|molecular\\s*cloning|plasmid|'
  + 'restriction\\s*(?:digest|enzyme)|gibson\\s*assembly|golden\\s*gate|mutagenesis|'
  + 'crispr\\s*(?:editing|knockout|screen)|knock-?out\\s*line|primer\\s*design|'
  + 'dna\\s*extraction|rna\\s*extraction|nucleic\\s*acid\\s*extraction|miniprep|maxiprep|library\\s*prep\\w*|'
  + 'sanger\\s*sequencing|flow\\s*cytometr\\w*|facs|cell\\s*sorting|'
  + 'protein\\s*purification|chromatograph\\w*|bradford\\s*assay|bca\\s*assay|enzyme\\s*assay|'
  + 'plate\\s*reader|microplate\\s*assay|od600|pipett\\w*|serial\\s*dilution|master\\s*mix|'
  + 'buffer\\s*(?:recipe|preparation)|reagent\\w*|centrifug\\w*|autoclav\\w*|aseptic|'
  + 'sterile\\s*technique|biosafety|fume\\s*hood|wet\\s*lab|bench\\s*work|lab(?:oratory)?\\s*protocol|'
  + 'antibiotic\\s*sensitivity|plating\\s*bacteria|bacterial\\s*cultur\\w*|yeast\\s*cultur\\w*|'
  + 'plant\\s*tissue\\s*culture|micropropagation|callus|seed\\s*germination|field\\s*trial|'
  + 'animal\\s*(?:handling|surgery|husbandry)|dissect\\w*|perfusion|cryosection\\w*|'
  + 'staining|fixation|antibod\\w*|blocking\\s*buffer|sample\\s*prep\\w*)\\b', 'i');

const CATEGORY = new RegExp(
  '\\b(bsl-?[34]|biosafety level [34]|select agent|category [ab] agent|bioterror|biological weapon|bioweapon|'
  + 'weapon[ií]s|gain[- ]of[- ]function|enhanced potential pandemic|aerosoli[sz]ed pathogen|nerve agent|'
  + 'chemical weapon|explosive|radioactive source|controlled substance synthesis|'
  + 'increas\\w*(?: the)? (?:virulence|transmissibility|lethality|pathogenicity)|'
  + 'antibiotic resistance engineering)\\b', 'i');

const NEEDS_APPROVAL = new RegExp(
  '\\b(human (?:subject|participant|trial|challenge)|clinical trial|patient sample|'
  + 'animal (?:experiment|surgery|model)|vivisection|in vivo (?:infection|challenge))\\b', 'i');

/** Where bench protocols live: nothing from these ever becomes a link, a step or a question's source. */
export const BLOCKED_SITES = [
  'protocols.io', 'bio-protocol.org', 'openwetware.org', 'jove.com', 'protocolexchange.researchsquare.com',
  'addgene.org', 'neb.com', 'thermofisher.com', 'lifetechnologies.com', 'invitrogen.com', 'sigmaaldrich.com',
  'merckmillipore.com', 'qiagen.com', 'promega.com', 'abcam.com', 'cellsignal.com', 'bio-rad.com',
  'biolegend.com', 'rndsystems.com', 'takarabio.com', 'agilent.com', 'culturecollections.org.uk', 'atcc.org',
  'bitesizebio.com', 'microscopyu.com', 'leica-microsystems.com', 'zeiss.com', 'corning.com',
  'miltenyibiotec.com', 'beckman.com', 'primer3.ut.ee',
];
/** Protocol journals, as OpenAlex source ids. */
export const BLOCKED_SOURCE_IDS = new Set(['S4210179406', 'S4210212477', 'S4363604116', 'S199738284',
  'S109387254', 'S119953358', 'S4210172139', 'S2898269294', 'S79990748', 'S4210177645', 'S2755386604',
  'S2764460200']);

const host = (url: string) => (String(url ?? '').split('/')[2] ?? '').toLowerCase().replace(/^www\./, '');

export function blockedSource(url: string, sourceId = ''): boolean {
  if (BLOCKED_SOURCE_IDS.has(String(sourceId ?? '').split('/').pop() ?? '')) return true;
  const h = host(url);
  return !!h && BLOCKED_SITES.some((s) => h === s || h.endsWith(`.${s}`));
}

/** Why myGeeKy leaves this alone, or '' when nothing in the text trips a rule. */
export function blocked(text: string): string {
  if (!text) return '';
  if (CATEGORY.test(text)) {
    return "it falls under work myGeeKy doesn't cover: high-containment, controlled or harm-increasing work";
  }
  if (NEEDS_APPROVAL.test(text)) {
    return "it needs an ethics approval myGeeKy can't see (people, patient samples or animals)";
  }
  if (BENCH.test(text)) return WHY_LAB;
  return '';
}

/** Does this name laboratory work? */
export const isBench = (text: string) => !!text && (BENCH.test(text) || CATEGORY.test(text) || NEEDS_APPROVAL.test(text));

/** May myGeeKy build a protocol about this skill? [ok, why not] */
export function allowed(name: string, goal = '', lab = false): [boolean, string] {
  if (lab) return [false, WHY_LAB];
  const why = blocked(`${name} ${goal}`.trim());
  return why ? [false, why] : [true, ''];
}
