"""
Lexicons and patterns for query intent classification and list-intent reranking.

Separated from logic so editing the data does not require touching the classifier.
All sets are frozen for cheap module-level lookup. Order matters only for the
MULTI_WORD_CATEGORIES list, which is sorted by length to enable longest-match.
"""

# ----------------------------------------------------------------------
# Category nouns (plural) - the strongest list-intent signal
# ----------------------------------------------------------------------

CATEGORY_NOUNS_PLURAL = frozenset({
    # food and drink
    "restaurants", "bars", "cafes", "cafés", "coffee shops", "breweries",
    "wineries", "bakeries", "pubs", "diners", "taverns", "eateries",
    "pizzerias", "bistros", "delis", "food trucks", "speakeasies",
    "dive bars", "wine bars", "cocktail bars", "sports bars",
    "tea houses", "ice cream shops", "donut shops", "juice bars",

    # lodging
    "hotels", "motels", "hostels", "resorts", "inns", "lodges",
    "b&bs", "bed and breakfasts", "airbnbs", "vacation rentals",
    "boutique hotels",

    # shopping
    "stores", "shops", "boutiques", "markets", "malls", "dispensaries",
    "bookstores", "thrift stores", "vintage shops", "record stores",
    "grocery stores", "supermarkets", "farmers markets",

    # services
    "salons", "spas", "gyms", "dentists", "doctors", "mechanics",
    "plumbers", "electricians", "lawyers", "attorneys", "barbers",
    "tattoo shops", "chiropractors", "therapists", "veterinarians",
    "pediatricians", "optometrists", "dermatologists", "accountants",
    "florists", "photographers", "caterers", "tailors",

    # entertainment / leisure
    "museums", "galleries", "theaters", "theatres", "cinemas",
    "clubs", "nightclubs", "venues", "parks", "attractions",
    "landmarks", "casinos", "concerts", "shows", "festivals",
    "tours", "experiences", "escape rooms", "bowling alleys",
    "arcades", "trails", "hikes", "beaches", "campgrounds",
    "art galleries",

    # generic discovery
    "places", "spots", "destinations", "businesses", "neighborhoods",
    "things to do", "activities", "events", "hangouts",
    "places to eat", "places to drink", "places to stay",
    "places to visit", "places to go", "places to shop",

    # list-trigger phrases that map to discovery intent
    "hidden gems", "must-sees", "must sees",

    # "where to X" phrases - canonical list-intent surface form
    "where to eat", "where to drink", "where to stay",
    "where to go", "where to shop", "where to visit",
})

# Singular forms that imply list intent when paired with a list modifier
# Example: "best restaurant in palm springs" - singular surface form,
# list intent in practice
CATEGORY_NOUNS_SINGULAR = frozenset({
    "restaurant", "bar", "cafe", "café", "brewery", "winery", "bakery",
    "pub", "diner", "tavern", "eatery", "pizzeria", "bistro", "deli",
    "hotel", "motel", "hostel", "resort", "inn", "lodge",
    "store", "shop", "boutique", "market", "mall", "dispensary",
    "bookstore", "gym", "spa", "salon", "barber", "dentist", "doctor",
    "mechanic", "plumber", "electrician", "lawyer", "attorney",
    "museum", "gallery", "theater", "theatre", "cinema",
    "club", "nightclub", "venue", "park", "attraction", "landmark",
    "casino", "place", "spot", "destination", "business",

    # food and cuisine types - moved here from PLURAL so they need a list
    # modifier or location to imply list intent. This avoids brand-name
    # false positives like "Pizza Hut menu" or "Burger King".
    "pizza", "ramen", "sushi", "bbq", "barbecue", "noodles",
    "ice cream", "coffee", "tea", "cocktails", "wine", "beer",
    "whisky", "whiskey", "brunch", "breakfast", "lunch", "dinner",
    "dessert", "desserts", "eats", "food", "dining", "cuisine",
    "taco", "burger", "wing", "donut", "bagel",
    "sandwich", "salad", "tacos", "burgers", "wings", "donuts",
    "bagels", "sandwiches", "salads",
})

# Sorted longest-first for greedy multi-word matching
MULTI_WORD_CATEGORIES = sorted(
    (c for c in CATEGORY_NOUNS_PLURAL if " " in c),
    key=len,
    reverse=True,
)

# Build the singular -> plural map for downstream reporting
# "best restaurant" should report category as "restaurants"
_SINGULAR_TO_PLURAL = {
    "restaurant": "restaurants", "bar": "bars", "cafe": "cafes",
    "café": "cafés", "brewery": "breweries", "winery": "wineries",
    "bakery": "bakeries", "pub": "pubs", "diner": "diners",
    "tavern": "taverns", "eatery": "eateries", "pizzeria": "pizzerias",
    "bistro": "bistros", "deli": "delis", "hotel": "hotels",
    "motel": "motels", "hostel": "hostels", "resort": "resorts",
    "inn": "inns", "lodge": "lodges", "store": "stores",
    "shop": "shops", "boutique": "boutiques", "market": "markets",
    "mall": "malls", "dispensary": "dispensaries",
    "bookstore": "bookstores", "gym": "gyms", "spa": "spas",
    "salon": "salons", "barber": "barbers", "dentist": "dentists",
    "doctor": "doctors", "mechanic": "mechanics", "plumber": "plumbers",
    "electrician": "electricians", "lawyer": "lawyers",
    "attorney": "attorneys", "museum": "museums", "gallery": "galleries",
    "theater": "theaters", "theatre": "theatres", "cinema": "cinemas",
    "club": "clubs", "nightclub": "nightclubs", "venue": "venues",
    "park": "parks", "attraction": "attractions", "landmark": "landmarks",
    "casino": "casinos", "place": "places", "spot": "spots",
    "destination": "destinations", "business": "businesses",
}

def singularize_to_plural(token: str) -> str | None:
    """Return canonical plural form for a singular category token, or None."""
    return _SINGULAR_TO_PLURAL.get(token)


# ----------------------------------------------------------------------
# Modifiers and qualifiers
# ----------------------------------------------------------------------

LIST_MODIFIERS = frozenset({
    "best", "top", "great", "good", "favorite", "popular", "trendy",
    "famous", "underrated", "hidden", "cheap", "affordable", "fancy",
    "upscale", "casual", "romantic", "must-try", "must", "highest-rated",
    "highest", "recommended", "iconic", "legendary", "trending",
    "newest", "cool", "fun", "hip", "chill", "quiet", "lively",
    "essential", "notable",
})

# Multi-word list modifier phrases (e.g., "must try", "highest rated")
MULTI_WORD_MODIFIERS = (
    "must try", "must visit", "must see", "must-try", "must-visit",
    "must-see", "highest rated", "kid friendly", "kid-friendly",
    "family friendly", "family-friendly", "dog friendly", "dog-friendly",
    "where to eat", "where to drink", "where to stay", "where to go",
)

# Words that strongly suggest entity-intent: someone wants a specific business
ENTITY_QUALIFIERS = frozenset({
    "hours", "menu", "reservations", "reservation", "phone",
    "address", "directions", "website", "email",
    "contact", "open", "closed", "opening", "closing",
    "today", "tonight",
    "booking", "delivery", "takeout",
    "parking", "yelp", "tripadvisor",
})

QUESTION_WORDS = frozenset({
    "how", "what", "why", "when", "where", "who", "which",
    "whose", "can", "could", "should", "would", "will", "does",
    "do", "did", "is", "are", "was", "were", "has", "have",
})


# ----------------------------------------------------------------------
# Location signals
# ----------------------------------------------------------------------

LOCATION_PREPOSITIONS = frozenset({
    "in", "near", "around", "at", "by", "outside", "inside",
    "within", "throughout",
})

NEAR_ME_PATTERNS = (
    "near me", "nearby", "around me", "close to me", "by me",
    "around here", "near here", "close by",
)

# Common location abbreviations
LOCATION_ABBREVIATIONS = frozenset({
    "nyc", "la", "sf", "dc", "atl", "chi", "vegas", "philly",
    "nola", "stl", "msp", "pdx", "atx", "rva", "boston",
})

# US state two-letter codes - used to recognize "Palm Springs CA" patterns
US_STATE_CODES = frozenset({
    "ak", "al", "ar", "az", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "ia", "id", "il", "in", "ks", "ky", "la", "ma", "md",
    "me", "mi", "mn", "mo", "ms", "mt", "nc", "nd", "ne", "nh",
    "nj", "nm", "nv", "ny", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "va", "vt", "wa", "wi", "wv", "wy",
})


# ----------------------------------------------------------------------
# Reranker signal patterns
# Used by list_intent_reranker for entity-homepage detection
# ----------------------------------------------------------------------

# Title patterns indicating single-entity homepages
# Compiled in the reranker module to keep this file data-only
ENTITY_TITLE_PATTERN_SOURCES = (
    # "Brand - Palm Springs, CA" or "Brand | Palm Springs, CA"
    r"^[^|\-–—]{2,50}\s*[|\-–—]\s*[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2},?\s+[A-Z]{2}\s*$",
    # "Brand's Restaurant" / "Brand's Cafe" etc.
    r"^[A-Z][a-zA-Z']{1,30}'s\s+(Restaurant|Cafe|Bar|Kitchen|Diner|Bistro|Grill|Pub|Tavern|Lounge|House|Place|Bakery|Brewery)\s*$",
    # "Welcome to X" titles
    r"^Welcome\s+to\s+",
    # "Brand Restaurant & Lounge" style titles (no location qualifier, just brand + entity word)
    r"^[A-Z][a-zA-Z0-9]+\s+(Restaurant|Cafe|Bar|Kitchen|Diner|Bistro|Grill|Pub|Tavern|Lounge|Bakery|Brewery)(\s+(&|and)\s+[A-Z][a-zA-Z]+)?\s*$",
)

# Snippet patterns indicating entity-homepage content
ENTITY_SNIPPET_PATTERN_SOURCES = (
    # Phone number (paren format)
    r"\(\d{3}\)\s*\d{3}[-.\s]?\d{4}",
    # Phone number (dash format)
    r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
    # Copyright lines
    r"©\s*Copyright",
    r"All\s+Rights\s+Reserved",
    # Address with street suffix
    r"\b\d{1,5}\s+(?:North|South|East|West|N|S|E|W)?\s*[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Place|Pl|Court|Ct|Parkway|Pkwy)\b",
    # City State ZIP
    r"[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?\s+[A-Z]{2}\s+\d{5}",
    # First-person possessive about a business
    r"\bour\s+(?:restaurant|menu|kitchen|chef|bar|cafe|store|shop|bakery|hotel|inn|location|family|team|staff)\b",
    # Welcome / about-us boilerplate
    r"\bwelcome\s+to\b",
    # Reservation / booking CTAs
    r"\b(?:make|book)\s+a?\s*(?:reservation|booking)\b",
)


# ----------------------------------------------------------------------
# Editorial list page signals - inverse of entity signals
# ----------------------------------------------------------------------

# Title patterns indicating editorial list / guide content
EDITORIAL_TITLE_PATTERN_SOURCES = (
    # "The 10 Best Restaurants in..." / "15 Best Bars..."
    r"\b\d{1,3}\s+(?:Best|Top|Great|Greatest|Essential|Must)\b",
    # "Best X in Y"
    r"\bBest\s+[A-Z][a-zA-Z]+\s+(?:in|of)\s+",
    # "Top X" / "Guide to X" / "Where to eat in X"
    r"^(?:The\s+)?(?:Top|Best|Greatest|Essential)\s+",
    r"\bGuide\s+to\b",
    r"\bWhere\s+to\s+(?:eat|drink|stay|go|shop|find)\b",
    # "Dining in X" / "Eating in X" / "Things to do in X"
    r"\b(?:Dining|Eating|Drinking|Shopping)\s+in\b",
    r"\bThings\s+to\s+do\b",
    # Possessive guide ("A Foodie's Guide to...")
    r"\b(?:Foodie|Traveler|Local|Insider|Visitor)['']s\s+Guide\b",
)


# ----------------------------------------------------------------------
# Domain reputation lists
# ----------------------------------------------------------------------

# Editorial publishers - boost in list-intent mode
# Curated, conservative. Each addition needs justification.
EDITORIAL_DOMAINS = frozenset({
    # Eater network
    "eater.com",
    "ny.eater.com", "la.eater.com", "sf.eater.com",
    "chicago.eater.com", "boston.eater.com", "dc.eater.com",
    "philly.eater.com", "atlanta.eater.com", "austin.eater.com",
    "denver.eater.com", "detroit.eater.com", "houston.eater.com",
    "miami.eater.com", "nashville.eater.com", "pdx.eater.com",
    "portland.eater.com", "seattle.eater.com", "twincities.eater.com",
    "vegas.eater.com", "carolinas.eater.com", "sandiego.eater.com",

    # Other food / travel editorial
    "thrillist.com", "timeout.com", "cntraveler.com",
    "travelandleisure.com", "afar.com", "fodors.com",
    "frommers.com", "lonelyplanet.com", "bonappetit.com",
    "epicurious.com", "foodandwine.com", "saveur.com",
    "seriouseats.com", "theinfatuation.com", "infatuation.com",
    "atlasobscura.com", "michelin.com", "guide.michelin.com",

    # General-interest with strong food/local sections
    "nytimes.com", "washingtonpost.com", "wsj.com",
    "theguardian.com", "bbc.com", "bbc.co.uk", "newyorker.com",
    "theatlantic.com",

    # Local alt-weeklies and city mags
    "lamag.com", "nymag.com", "chicagomag.com", "texasmonthly.com",
    "phoenixmag.com", "palmspringslife.com",
})

# Tourism / city-government domains - boost in list-intent mode
# Pattern-matched at runtime; some hardcoded for high-traffic cases
OFFICIAL_TOURISM_DOMAIN_PATTERNS = (
    # "visit{city}.com|.org"
    r"^visit[a-z]{3,}\.(?:com|org|gov)$",
    # "discover{city}.com|.org"
    r"^discover[a-z]{3,}\.(?:com|org)$",
    # "explore{city}.com|.org"
    r"^explore[a-z]{3,}\.(?:com|org)$",
    # state/city .gov
    r"^[a-z]+\.gov$",
    r"^[a-z]+\.ca\.gov$",
)

# Aggregator domains that are neither editorial nor single-entity
# Useful so the reranker doesn't accidentally boost or penalize them
KNOWN_AGGREGATORS = frozenset({
    "yelp.com", "tripadvisor.com", "opentable.com", "resy.com",
    "google.com", "maps.google.com", "yellowpages.com",
    "foursquare.com", "zomato.com",
})
