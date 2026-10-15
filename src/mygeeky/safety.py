"""What myGeeKy will not teach: anything done at a bench, and anything needing approvals it can't see.

**myGeeKy teaches analysis, not laboratory work.** It helps with code, data,
statistics, figures and pipelines -- the work done at a computer. It does not
give protocols, steps, recipes, volumes, conditions or troubleshooting for
anything done at a bench, with reagents, cells, organisms or instruments.

Why, plainly: a wrong line of R wastes an afternoon; a wrong line at a bench
can hurt somebody. myGeeKy has one maintainer, cannot review bench safety,
cannot know anyone's local rules, training or containment, and cannot check
what anyone actually does. So it stays out of it -- not as a judgement about
that work, which is somebody else's expertise, but because it isn't myGeeKy's
to give.

**This is a refusal rule, not a filter to be tuned.** `allowed()` says no to:

  - any skill the dictionary marks as bench work (there are none left: they
    were removed, and this stops a reintroduced one slipping through);
  - any skill or goal naming a laboratory technique, reagent or instrument;
  - the category rules below (containment, controlled agents, harm, work on
    people or animals, controlled substances).

**It also closes the way in.** `blocked_source()` drops links from protocol
repositories, protocol journals and suppliers' method libraries wherever they
could arrive: a protocol myGeeKy builds, a reviewed one in the curated file, a
protocol another user published, and a quiz question's source. So a bench
protocol cannot reach anyone through myGeeKy even if one is put in by hand.

Analysing data that came out of an experiment is **not** bench work, and is
welcome: "from Excel to R with your own lab data", "which statistical test",
"figures for papers", "measuring images in Fiji". Those name no technique and
tell nobody to touch anything.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

# ---- the kinds of work myGeeKy stays out of, in the words used in messages and prompts
CATEGORY_RULES = (
    "anything performed at a laboratory bench: protocols, steps, recipes, volumes, concentrations, "
    "incubation conditions, instrument settings or troubleshooting",
    "handling reagents, chemicals, cells, tissue, organisms, samples or laboratory animals",
    "work that needs containment, a licence, or training myGeeKy cannot see",
    "anything aimed at making an organism or substance more harmful, more transmissible or harder to treat",
    "anything whose point is to harm people, animals, crops or the environment",
    "work on people, patients, their samples or animals, which needs an ethics approval myGeeKy cannot see",
    "handling controlled drugs, explosives or radioactive material",
)

WHY_LAB = ("myGeeKy only covers work done at a computer — code, data, statistics, figures and pipelines. It "
           "doesn't give laboratory protocols or bench instructions: that's for your lab, your supervisor and "
           "your institution's own rules. Analysing the data an experiment produced is welcome — try the "
           "skill you'd analyse it with (R, Python, statistics, plotting).")

# Named techniques, reagents and instruments. Deliberately broad: a refusal costs somebody one search, and
# the message says what to ask for instead.
_BENCH = re.compile(
    r"\b(pcr|qpcr|rt-?pcr|ddpcr|electrophoresis|agarose|sds-?page|western\s*blot|immunoblot|northern\s*blot|"
    r"southern\s*blot|elisa|immunostain\w*|immunofluorescen\w*|immunohistochem\w*|histolog\w*|"
    r"cell\s*cultur\w*|tissue\s*cultur\w*|transfect\w*|electroporat\w*|molecular\s*cloning|plasmid|"
    r"restriction\s*(?:digest|enzyme)|gibson\s*assembly|golden\s*gate|mutagenesis|"
    r"crispr\s*(?:editing|knockout|screen)|knock-?out\s*line|primer\s*design|"
    r"dna\s*extraction|rna\s*extraction|nucleic\s*acid\s*extraction|miniprep|maxiprep|library\s*prep\w*|"
    r"sanger\s*sequencing|flow\s*cytometr\w*|facs|cell\s*sorting|"
    r"protein\s*purification|chromatograph\w*|bradford\s*assay|bca\s*assay|enzyme\s*assay|"
    r"plate\s*reader|microplate\s*assay|od600|pipett\w*|serial\s*dilution|master\s*mix|"
    r"buffer\s*(?:recipe|preparation)|reagent\w*|centrifug\w*|autoclav\w*|aseptic|"
    r"sterile\s*technique|biosafety|fume\s*hood|wet\s*lab|bench\s*work|lab(?:oratory)?\s*protocol|"
    r"antibiotic\s*sensitivity|plating\s*bacteria|bacterial\s*cultur\w*|yeast\s*cultur\w*|"
    r"plant\s*tissue\s*culture|micropropagation|callus|seed\s*germination|field\s*trial|"
    r"animal\s*(?:handling|surgery|husbandry)|dissect\w*|perfusion|cryosection\w*|"
    r"staining|fixation|antibod\w*|blocking\s*buffer|sample\s*prep\w*)\b", re.I)

_CATEGORY = re.compile(
    r"\b(bsl-?[34]|biosafety level [34]|select agent|category [ab] agent|bioterror|biological weapon|"
    r"bioweapon|weapon[ií]s|gain[- ]of[- ]function|enhanced potential pandemic|aerosoli[sz]ed pathogen|"
    r"nerve agent|chemical weapon|explosive|radioactive source|controlled substance synthesis|"
    r"increas\w*(?: the)? (?:virulence|transmissibility|lethality|pathogenicity)|"
    r"antibiotic resistance engineering)\b", re.I)

_NEEDS_APPROVAL = re.compile(r"\b(human (?:subject|participant|trial|challenge)|clinical trial|patient sample"
                             r"|animal (?:experiment|surgery|model)|vivisection|in vivo (?:infection|challenge))\b",
                             re.I)

# Where bench protocols live. Nothing from these ever becomes a link, a step, or a question's source.
BLOCKED_SITES = (
    "protocols.io", "bio-protocol.org", "openwetware.org", "jove.com",
    "protocolexchange.researchsquare.com", "addgene.org", "neb.com", "thermofisher.com",
    "lifetechnologies.com", "invitrogen.com", "sigmaaldrich.com", "merckmillipore.com", "qiagen.com",
    "promega.com", "abcam.com", "cellsignal.com", "bio-rad.com", "biolegend.com", "rndsystems.com",
    "takarabio.com", "agilent.com", "culturecollections.org.uk", "atcc.org", "bitesizebio.com",
    "microscopyu.com", "leica-microsystems.com", "zeiss.com", "corning.com", "miltenyibiotec.com",
    "beckman.com", "primer3.ut.ee",
)
# Protocol journals, as OpenAlex source ids: a hit from one of these is never a candidate.
BLOCKED_SOURCE_IDS = {
    "S4210179406",   # Bio-protocol
    "S4210212477",   # STAR Protocols
    "S4363604116",   # protocols.io
    "S199738284",    # JoVE
    "S109387254",    # Nature Protocols
    "S119953358",    # Cold Spring Harbor Protocols
    "S4210172139",   # Methods in Molecular Biology
    "S2898269294",   # MethodsX
    "S79990748",     # BioTechniques
    "S4210177645",   # Current Protocols in Bioinformatics
    "S2755386604",   # Current Protocols in Molecular Biology
    "S2764460200",   # Current Protocols in Immunology
}


def _host(url: str) -> str:
    try:
        host = urlsplit(str(url or "")).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def blocked_source(url: str, source_id: str = "") -> bool:
    """Is this link a bench protocol's home? Those never reach anyone through myGeeKy."""
    if str(source_id or "").rsplit("/", 1)[-1] in BLOCKED_SOURCE_IDS:
        return True
    host = _host(url)
    return bool(host) and any(host == s or host.endswith("." + s) for s in BLOCKED_SITES)


def blocked(text: str) -> str:
    """Why myGeeKy leaves this alone, or "" when nothing in the text trips a rule."""
    if not text:
        return ""
    if _CATEGORY.search(text):
        return "it falls under work myGeeKy doesn't cover: high-containment, controlled or harm-increasing work"
    if _NEEDS_APPROVAL.search(text):
        return "it needs an ethics approval myGeeKy can't see (people, patient samples or animals)"
    if _BENCH.search(text):
        return WHY_LAB
    return ""


def is_bench(text: str) -> bool:
    """Does this name laboratory work? The plain yes-or-no, for callers that need nothing else."""
    return bool(text) and bool(_BENCH.search(text) or _CATEGORY.search(text) or _NEEDS_APPROVAL.search(text))


def allowed(name: str, goal: str = "", lab: bool | None = None) -> tuple[bool, str]:
    """May myGeeKy build a protocol or write questions about this skill? (ok, why not).

    `lab` is for callers that already know the skill is bench work (a `kind` of "lab" in skills.json):
    an immediate no. The dictionary has no such skill any more, and this stops a reintroduced one."""
    if lab:
        return False, WHY_LAB
    why = blocked(f"{name} {goal}".strip())
    return (False, why) if why else (True, "")


def prompt_rules() -> str:
    """The rules as a block for a model prompt (the quiz writer, the listing scout)."""
    return ("myGeeKy only ever covers work done at a computer: code, data, statistics, figures and pipelines.\n"
            "Never write anything about:\n" + "\n".join(f"- {r}" for r in CATEGORY_RULES)
            + "\nIf the source is a laboratory protocol, or describes bench steps, write nothing at all.")
