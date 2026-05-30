# tier1_enhanced.py - librarian-grade Tier 1 classifier for Cerulean.
# Resolution order (most authoritative first):
#   1. Authority registry  - the curated librarian authority file (authority_registry.json)
#   2. Bundled index       - source_categorizer domain buckets + curated publisher expansion
#   3. Structural heuristic - subdomain patterns (forums)
#   4. Role refinement      - primary/secondary/tertiary from document signals, not type alone
# Falls through to None (Tier 3 LLM) only for the genuine long tail.
import os, json, sys
from urllib.parse import urlparse
sys.path.insert(0, "backend")
from source_categorizer import categorize  # noqa: E402

OLD_TYPE_TO_NEW_TYPE = {
    "news": "JOURNALISM", "reference": "REFERENCE", "academic": "ACADEMIC",
    "gov": "PRIMARY_SOURCE_PUBLISHER", "community": "COMMUNITY",
    "docs": "PRIMARY_SOURCE_PUBLISHER", "commercial": "COMMERCIAL",
    "video": "AGGREGATOR", "indie": "INDIE", "social": "AGGREGATOR",
    "health": "REFERENCE", "ai_slop": "SEO_FARM", "other": None,
}
TYPE_TO_DEFAULT_ROLE = {
    "PRIMARY_SOURCE_PUBLISHER": "PRIMARY", "JOURNALISM": "SECONDARY",
    "ACADEMIC": "SECONDARY", "REFERENCE": "TERTIARY", "INDIE": "SECONDARY",
    "COMMUNITY": "SECONDARY", "COMMERCIAL": "SECONDARY", "AGGREGATOR": "TERTIARY",
    "SEO_FARM": "TERTIARY", "UNCLASSIFIED": "UNCLASSIFIED",
}
# Curated publisher expansion. Seed list of unambiguous, well-known publishers
# missing from the base index. Grow this from live traffic, not the benchmark.
INDEX_EXPANSION = {
    **{d: "JOURNALISM" for d in ["abcnews.com","caranddriver.com","empireonline.com","elpais.com","36kr.com","fiercehealthcare.com","forbes.com","gizmodo.com","kcra.com","kiplinger.com","lawfaremedia.org","mashable.com","money.com","motortrend.com","pbs.org","pcmag.com","retaildive.com","runnersworld.com","inquirer.net","techradar.com","thehill.com","thetrace.org","advisorperspectives.com"]},
    **{d: "ACADEMIC" for d in ["neurips.cc","cambridge.org","iopscience.iop.org","asm.org","opentextbc.ca","pnas.org","politybooks.com","povertyactionlab.org","tandfonline.com"]},
    **{d: "REFERENCE" for d in ["adamsmithworks.org","ballotpedia.org","constitutioncenter.org","ebsco.com","investopedia.com","ncsl.org","oauth.net","oyez.org","usafacts.org"]},
    **{d: "PRIMARY_SOURCE_PUBLISHER" for d in ["ietf.org","gunviolencearchive.org","manhattanda.org","justia.com"]},
    **{d: "AGGREGATOR" for d in ["broadbandmap.com","broadbandnow.com","inmyarea.com","paperdigest.org","truecar.com"]},
    **{d: "SEO_FARM" for d in ["highspeedinternet.com","linuxtoday.com","tecmint.com","thegadgetflow.com","worldpopulationreview.com"]},
}
PREPRINT = ("arxiv.org", "biorxiv.org", "medrxiv.org", "ssrn.com")
FORUM_PREFIXES = ("community.", "discourse.", "talk.", "devforum.", "forum.")

def _load_registry(path):
    try:
        ents = json.load(open(path))["entities"]
        return {d: ents[d]["type_classification"] for d in ents}
    except Exception:
        return {}

REGISTRY = _load_registry(os.environ.get("CERULEAN_REGISTRY", "benchmark/authority_registry.json"))

def _host(u): return (urlparse(u).hostname or "").replace("www.", "").lower()
def _path(u): return (urlparse(u).path or "").lower()

# Types whose role splits within the type and needs document-level signals.
ROLE_REFINED = ("ACADEMIC", "PRIMARY_SOURCE_PUBLISHER", "COMMERCIAL", "REFERENCE")

def _role_for(t, u):
    """Document-level role: primary/secondary/tertiary from path signals, not type alone."""
    h, p = _host(u), _path(u)
    if t == "ACADEMIC":
        if any(h == d or h.endswith("." + d) for d in PREPRINT) or "/abs/" in p:
            return "PRIMARY"
        # an actual journal article / DOI is the primary research artifact
        if any(s in p for s in ("/doi/", "/articles/", "/article/", "/stable/", "/journals/", "/full/", "/pmc")):
            return "PRIMARY"
        # think-tank "research"/"our-work" pages are secondary analysis
        return "SECONDARY"
    if t == "PRIMARY_SOURCE_PUBLISHER":
        return "SECONDARY" if ("/news/" in p or "/press" in p) else "PRIMARY"
    if t == "COMMERCIAL":
        if "/blog" in p:
            return "SECONDARY"  # commentary
        if any(s in p for s in ("/docs", "/reference", "/support", "/news", "/gp/", "/compose", "/help")):
            return "PRIMARY"   # entity's own product/docs = official communication
        return "SECONDARY"
    if t == "REFERENCE":
        if "/wiki" in p or "/wex" in p:
            return "TERTIARY"
        if "man7.org" in h or "/man-pages" in p or "/docs" in p or h.endswith("oauth.net"):
            return "PRIMARY"   # specs / man pages
        return "SECONDARY"
    return TYPE_TO_DEFAULT_ROLE.get(t, "SECONDARY")

def _match(h, d): return h == d or h.endswith("." + d)

def tier1(url):
    """Returns (role, type, source) or None to defer to Tier 3."""
    h = _host(url)
    for d, t in REGISTRY.items():
        if _match(h, d):
            return (_role_for(t, url), t, "registry")
    for d, t in INDEX_EXPANSION.items():
        if _match(h, d):
            return (_role_for(t, url), t, "index")
    if any(h.startswith(p) for p in FORUM_PREFIXES):
        return ("SECONDARY", "COMMUNITY", "heuristic")
    ot = categorize(url)
    nt = OLD_TYPE_TO_NEW_TYPE.get(ot)
    if nt is None:
        return None
    role = TYPE_TO_DEFAULT_ROLE.get(nt, "SECONDARY")
    if ot in ("video", "social"):
        role = "SECONDARY"
    if nt in ROLE_REFINED:
        role = _role_for(nt, url)
    return (role, nt, "tier1")
