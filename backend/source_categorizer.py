"""
backend/source_categorizer.py

Domain-based source-type classification for Cerulean Search.
No external API calls, no ML. Hardcoded mappings.

Returns one of:
  news, reference, wiki_community, academic, gov, forum, social,
  video, docs, code, blog, commerce, reviews, press, health,
  recipe, learning, ai_slop, other
"""
from urllib.parse import urlparse

# Subdomain-specific overrides. Checked first (most specific).
SUBDOMAIN_OVERRIDES = {
    "news.ycombinator.com": "community",
    "scholar.google.com": "academic",
    "books.google.com": "reference",
    "developer.mozilla.org": "docs",
    "learn.microsoft.com": "docs",
    "docs.python.org": "docs",
    "docs.aws.amazon.com": "docs",
    "docs.github.com": "docs",
    "cloud.google.com": "docs",
    "cooking.nytimes.com": "reference",
    "health.harvard.edu": "health",
    "my.clevelandclinic.org": "health",
    "medlineplus.gov": "health",
    "kaiserhealthnews.org": "health",
}

# Exact registered-domain matches. Checked second.
EXACT = {
    # ---- news ----
    "nytimes.com": "news", "wsj.com": "news", "washingtonpost.com": "news",
    "reuters.com": "news", "apnews.com": "news", "bbc.com": "news",
    "bbc.co.uk": "news", "theguardian.com": "news", "ft.com": "news",
    "economist.com": "news", "bloomberg.com": "news", "cnn.com": "news",
    "foxnews.com": "news", "msnbc.com": "news", "npr.org": "news",
    "nbcnews.com": "news", "cbsnews.com": "news", "axios.com": "news",
    "politico.com": "news", "vox.com": "news", "theatlantic.com": "news",
    "newyorker.com": "news", "time.com": "news", "propublica.org": "news",
    "wired.com": "news", "theverge.com": "news", "techcrunch.com": "news",
    "arstechnica.com": "news", "espn.com": "news", "businessinsider.com": "news",
    "cnbc.com": "news", "marketwatch.com": "news", "aljazeera.com": "news",
    # ---- reference ----
    "wikipedia.org": "reference", "britannica.com": "reference",
    "merriam-webster.com": "reference", "dictionary.com": "reference",
    "thesaurus.com": "reference", "wiktionary.org": "reference",
    "wikiquote.org": "reference", "wikibooks.org": "reference",
    "gutenberg.org": "reference", "archive.org": "reference",
    "goodreads.com": "reference", "imdb.com": "reference",
    "etymonline.com": "reference",
    # ---- wiki_community ----
    "fandom.com": "community", "fextralife.com": "community",
    "wikia.com": "community", "gamepedia.com": "community",
    "miraheze.org": "community",
    # ---- academic ----
    "arxiv.org": "academic", "biorxiv.org": "academic", "medrxiv.org": "academic",
    "jstor.org": "academic", "ssrn.com": "academic", "nature.com": "academic",
    "science.org": "academic", "sciencedirect.com": "academic",
    "springer.com": "academic", "wiley.com": "academic",
    "researchgate.net": "academic", "semanticscholar.org": "academic",
    "academia.edu": "academic", "plos.org": "academic", "mdpi.com": "academic",
    "cell.com": "academic", "thelancet.com": "academic", "nejm.org": "academic",
    "bmj.com": "academic", "jamanetwork.com": "academic",
    # ---- gov (international/IGO; .gov/.mil handled by suffix) ----
    "who.int": "gov", "un.org": "gov", "unesco.org": "gov", "unicef.org": "gov",
    "imf.org": "gov", "worldbank.org": "gov", "wto.org": "gov",
    "oecd.org": "gov", "europa.eu": "gov", "ec.europa.eu": "gov",
    "nato.int": "gov", "interpol.int": "gov",
    # ---- forum ----
    "reddit.com": "community", "stackexchange.com": "community",
    "stackoverflow.com": "community", "superuser.com": "community",
    "serverfault.com": "community", "askubuntu.com": "community",
    "mathoverflow.net": "community", "quora.com": "community",
    "lobste.rs": "community", "slashdot.org": "community",
    # ---- social (authoritative: social media, not generic community) ----
    "x.com": "social", "twitter.com": "social", "instagram.com": "social",
    "tiktok.com": "social", "facebook.com": "social", "threads.net": "social",
    "bsky.app": "social", "mastodon.social": "social", "pinterest.com": "social",
    "snapchat.com": "social", "tumblr.com": "social", "linkedin.com": "social",
    # ---- video ----
    "youtube.com": "video", "youtu.be": "video", "vimeo.com": "video",
    "twitch.tv": "video", "dailymotion.com": "video", "rumble.com": "video",
    # ---- docs ----
    "readthedocs.io": "docs", "kubernetes.io": "docs", "react.dev": "docs",
    "vuejs.org": "docs", "nodejs.org": "docs", "go.dev": "docs",
    "rust-lang.org": "docs", "python.org": "docs", "postgresql.org": "docs",
    "mongodb.com": "docs", "redis.io": "docs",
    # ---- code ----
    "github.com": "docs", "gitlab.com": "docs", "bitbucket.org": "docs",
    "codeberg.org": "docs", "sourceforge.net": "docs", "pypi.org": "docs",
    "npmjs.com": "docs", "crates.io": "docs", "rubygems.org": "docs",
    "hub.docker.com": "docs", "huggingface.co": "docs",
    # ---- indie / personal publishing platforms ----
    "medium.com": "indie", "substack.com": "indie", "ghost.org": "indie",
    "dev.to": "indie", "hashnode.com": "indie",
    "neocities.org": "indie", "bearblog.dev": "indie", "micro.blog": "indie",
    "write.as": "indie", "mataroa.blog": "indie",
    # ---- commerce ----
    "amazon.com": "commercial", "amazon.co.uk": "commercial", "ebay.com": "commercial",
    "etsy.com": "commercial", "walmart.com": "commercial", "target.com": "commercial",
    "bestbuy.com": "commercial", "homedepot.com": "commercial", "lowes.com": "commercial",
    "costco.com": "commercial", "wayfair.com": "commercial", "alibaba.com": "commercial",
    "aliexpress.com": "commercial", "temu.com": "commercial", "shein.com": "commercial",
    "newegg.com": "commercial", "macys.com": "commercial", "nordstrom.com": "commercial",
    # ---- reviews ----
    "yelp.com": "commercial", "trustpilot.com": "commercial", "tripadvisor.com": "commercial",
    "rottentomatoes.com": "commercial", "metacritic.com": "commercial", "g2.com": "commercial",
    "capterra.com": "commercial", "glassdoor.com": "commercial", "bbb.org": "commercial",
    "consumerreports.org": "commercial", "wirecutter.com": "commercial", "rtings.com": "commercial",
    # ---- press ----
    "prnewswire.com": "news", "businesswire.com": "news",
    "globenewswire.com": "news", "einpresswire.com": "news",
    "accesswire.com": "news", "prweb.com": "news", "newswire.com": "news",
    # ---- health ----
    "mayoclinic.org": "health", "webmd.com": "health", "healthline.com": "health",
    "medicalnewstoday.com": "health", "drugs.com": "health", "rxlist.com": "health",
    "verywellhealth.com": "health", "verywellmind.com": "health",
    "verywellfit.com": "health", "clevelandclinic.org": "health",
    "hopkinsmedicine.org": "health", "psychologytoday.com": "health",
    "everydayhealth.com": "health", "kff.org": "health",
    # ---- recipe ----
    "allrecipes.com": "reference", "foodnetwork.com": "reference", "food.com": "reference",
    "seriouseats.com": "reference", "bonappetit.com": "reference", "epicurious.com": "reference",
    "kingarthurbaking.com": "reference", "smittenkitchen.com": "reference",
    "thekitchn.com": "reference", "tasty.co": "reference", "delish.com": "reference",
    "foodandwine.com": "reference", "simplyrecipes.com": "reference",
    "minimalistbaker.com": "reference", "budgetbytes.com": "reference",
    # ---- learning ----
    "khanacademy.org": "docs", "coursera.org": "docs", "udemy.com": "docs",
    "udacity.com": "docs", "edx.org": "docs", "codecademy.com": "docs",
    "brilliant.org": "docs", "skillshare.com": "docs",
    "pluralsight.com": "docs", "duolingo.com": "docs",
    "freecodecamp.org": "docs", "w3schools.com": "docs",
    "geeksforgeeks.org": "docs", "tutorialspoint.com": "docs",
    # ---- ai_slop ----
    # Placeholder list; needs ongoing curation from NewsGuard AI tracker etc.
    "biztoc.com": "ai_slop", "famousbirthdays.com": "ai_slop",
    "celebsagewiki.com": "ai_slop", "trendynewsworld.com": "ai_slop",
}

# Suffix patterns. Checked third. Order matters; more specific first.
SUFFIX = [
    (".gov.uk", "gov"), (".gov.au", "gov"), (".gov.in", "gov"),
    (".gc.ca", "gov"), (".gob.mx", "gov"),
    (".gov", "gov"), (".mil", "gov"),
    (".ac.uk", "academic"), (".edu.au", "academic"),
    (".ac.jp", "academic"), (".edu.cn", "academic"),
    (".edu", "academic"),
    (".fandom.com", "community"),
    (".substack.com", "indie"), (".medium.com", "indie"),
    (".blogspot.com", "indie"), (".wordpress.com", "indie"),
    (".tumblr.com", "social"),
    (".github.io", "indie"), (".gitlab.io", "indie"),
    (".neocities.org", "indie"), (".bearblog.dev", "indie"),
    (".micro.blog", "indie"), (".write.as", "indie"),
    (".dreamwidth.org", "indie"), (".mataroa.blog", "indie"),
    (".readthedocs.io", "docs"),
]

TWO_PART_TLDS = {
    "co.uk", "com.au", "gov.uk", "ac.uk", "gov.au", "edu.au",
    "ac.jp", "co.jp", "com.cn", "edu.cn", "gov.cn", "gc.ca",
    "co.in", "gov.in", "ac.in", "edu.in", "gob.mx",
}


def _extract_domain(url: str):
    """Returns (full_host, registered_domain) lowercased, www-stripped."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return "", ""
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return "", ""
    parts = host.split(".")
    if len(parts) <= 2:
        return host, host
    last_two = ".".join(parts[-2:])
    if last_two in TWO_PART_TLDS and len(parts) >= 3:
        registered = ".".join(parts[-3:])
    else:
        registered = ".".join(parts[-2:])
    return host, registered


def categorize(url: str) -> str:
    """Returns the source-type category for a URL. Defaults to 'other'."""
    full_host, registered = _extract_domain(url)
    if not full_host:
        return "other"
    if full_host in SUBDOMAIN_OVERRIDES:
        return SUBDOMAIN_OVERRIDES[full_host]
    if registered in EXACT:
        return EXACT[registered]
    if full_host in EXACT:
        return EXACT[full_host]
    for suffix, category in SUFFIX:
        if full_host.endswith(suffix) or registered.endswith(suffix):
            return category
    return "other"


# Badge labels for UI display
LABELS = {
    'news': 'News',
    'reference': 'Reference',
    'academic': 'Academic',
    'gov': 'Official',
    'community': 'Community',
    'docs': 'Docs',
    'indie': 'Indie',
    'social': 'Social',
    'commercial': 'Commercial',
    'video': 'Video',
    'health': 'Health',
    'ai_slop': 'AI Content',
    'other': 'Other',
}
