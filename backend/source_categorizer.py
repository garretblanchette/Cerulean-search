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
    "news.ycombinator.com": "forum",
    "scholar.google.com": "academic",
    "books.google.com": "reference",
    "developer.mozilla.org": "docs",
    "learn.microsoft.com": "docs",
    "docs.python.org": "docs",
    "docs.aws.amazon.com": "docs",
    "docs.github.com": "docs",
    "cloud.google.com": "docs",
    "cooking.nytimes.com": "recipe",
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
    "fandom.com": "wiki_community", "fextralife.com": "wiki_community",
    "wikia.com": "wiki_community", "gamepedia.com": "wiki_community",
    "miraheze.org": "wiki_community",
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
    "reddit.com": "forum", "stackexchange.com": "forum",
    "stackoverflow.com": "forum", "superuser.com": "forum",
    "serverfault.com": "forum", "askubuntu.com": "forum",
    "mathoverflow.net": "forum", "quora.com": "forum",
    "lobste.rs": "forum", "slashdot.org": "forum",
    # ---- social ----
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
    "github.com": "code", "gitlab.com": "code", "bitbucket.org": "code",
    "codeberg.org": "code", "sourceforge.net": "code", "pypi.org": "code",
    "npmjs.com": "code", "crates.io": "code", "rubygems.org": "code",
    "hub.docker.com": "code", "huggingface.co": "code",
    # ---- blog ----
    "medium.com": "blog", "substack.com": "blog", "ghost.org": "blog",
    "dev.to": "blog", "hashnode.com": "blog",
    # ---- commerce ----
    "amazon.com": "commerce", "amazon.co.uk": "commerce", "ebay.com": "commerce",
    "etsy.com": "commerce", "walmart.com": "commerce", "target.com": "commerce",
    "bestbuy.com": "commerce", "homedepot.com": "commerce", "lowes.com": "commerce",
    "costco.com": "commerce", "wayfair.com": "commerce", "alibaba.com": "commerce",
    "aliexpress.com": "commerce", "temu.com": "commerce", "shein.com": "commerce",
    "newegg.com": "commerce", "macys.com": "commerce", "nordstrom.com": "commerce",
    # ---- reviews ----
    "yelp.com": "reviews", "trustpilot.com": "reviews", "tripadvisor.com": "reviews",
    "rottentomatoes.com": "reviews", "metacritic.com": "reviews", "g2.com": "reviews",
    "capterra.com": "reviews", "glassdoor.com": "reviews", "bbb.org": "reviews",
    "consumerreports.org": "reviews", "wirecutter.com": "reviews", "rtings.com": "reviews",
    # ---- press ----
    "prnewswire.com": "press", "businesswire.com": "press",
    "globenewswire.com": "press", "einpresswire.com": "press",
    "accesswire.com": "press", "prweb.com": "press", "newswire.com": "press",
    # ---- health ----
    "mayoclinic.org": "health", "webmd.com": "health", "healthline.com": "health",
    "medicalnewstoday.com": "health", "drugs.com": "health", "rxlist.com": "health",
    "verywellhealth.com": "health", "verywellmind.com": "health",
    "verywellfit.com": "health", "clevelandclinic.org": "health",
    "hopkinsmedicine.org": "health", "psychologytoday.com": "health",
    "everydayhealth.com": "health", "kff.org": "health",
    # ---- recipe ----
    "allrecipes.com": "recipe", "foodnetwork.com": "recipe", "food.com": "recipe",
    "seriouseats.com": "recipe", "bonappetit.com": "recipe", "epicurious.com": "recipe",
    "kingarthurbaking.com": "recipe", "smittenkitchen.com": "recipe",
    "thekitchn.com": "recipe", "tasty.co": "recipe", "delish.com": "recipe",
    "foodandwine.com": "recipe", "simplyrecipes.com": "recipe",
    "minimalistbaker.com": "recipe", "budgetbytes.com": "recipe",
    # ---- learning ----
    "khanacademy.org": "learning", "coursera.org": "learning", "udemy.com": "learning",
    "udacity.com": "learning", "edx.org": "learning", "codecademy.com": "learning",
    "brilliant.org": "learning", "skillshare.com": "learning",
    "pluralsight.com": "learning", "duolingo.com": "learning",
    "freecodecamp.org": "learning", "w3schools.com": "learning",
    "geeksforgeeks.org": "learning", "tutorialspoint.com": "learning",
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
    (".fandom.com", "wiki_community"),
    (".substack.com", "blog"), (".medium.com", "blog"),
    (".blogspot.com", "blog"), (".wordpress.com", "blog"),
    (".tumblr.com", "social"),
    (".github.io", "code"), (".readthedocs.io", "docs"),
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
    "news": "News", "reference": "Reference", "wiki_community": "Fan Wiki",
    "academic": "Academic", "gov": "Official", "forum": "Forum",
    "social": "Social", "video": "Video", "docs": "Docs", "code": "Code",
    "blog": "Blog", "commerce": "Shop", "reviews": "Reviews",
    "press": "Press Release", "health": "Health", "recipe": "Recipe",
    "learning": "Learning", "ai_slop": "AI Content", "other": "Other",
}
