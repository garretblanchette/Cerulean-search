"""
List-intent reranker (Layers 2 + 3 of the ranking refinement pipeline).

Activated only when the Layer 1 classifier reports LIST intent. Takes the
search results returned by the upstream providers (Brave / Serper / DDG)
and rescores them based on:

    1. Entity-homepage probability   (penalize)
    2. Editorial list probability    (boost)
    3. Domain reputation             (publisher boost, aggregator neutral)

All features extracted from data already present in SERP API responses:
URL, title, description/snippet, optional structured-data hints. No DOM
fetch required. Sub-millisecond per result.

Layers 2 (schema penalty) and 3 (structural detection) from the spec are
combined here because they share the same feature extraction pass.
Schema is treated as one feature among several rather than a separate
stage. This is the elegant simplification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from intent_classifier import IntentResult, Intent
from intent_lexicons import (
    CATEGORY_NOUNS_PLURAL,
    CATEGORY_NOUNS_SINGULAR,
    EDITORIAL_DOMAINS,
    EDITORIAL_TITLE_PATTERN_SOURCES,
    ENTITY_QUALIFIERS,
    ENTITY_SNIPPET_PATTERN_SOURCES,
    ENTITY_TITLE_PATTERN_SOURCES,
    KNOWN_AGGREGATORS,
    OFFICIAL_TOURISM_DOMAIN_PATTERNS,
)


# ----------------------------------------------------------------------
# Compiled patterns
# ----------------------------------------------------------------------

_ENTITY_TITLE_RES = tuple(re.compile(p) for p in ENTITY_TITLE_PATTERN_SOURCES)
_ENTITY_SNIPPET_RES = tuple(re.compile(p, re.IGNORECASE) for p in ENTITY_SNIPPET_PATTERN_SOURCES)
_EDITORIAL_TITLE_RES = tuple(re.compile(p, re.IGNORECASE) for p in EDITORIAL_TITLE_PATTERN_SOURCES)
_OFFICIAL_TOURISM_RES = tuple(re.compile(p) for p in OFFICIAL_TOURISM_DOMAIN_PATTERNS)

# Single-entity schema types - the ones that mark a result as a business homepage
SINGLE_ENTITY_SCHEMA_TYPES = frozenset({
    "restaurant", "localbusiness", "store", "hotel", "lodgingbusiness",
    "foodestablishment", "barorpub", "cafeorcoffeeshop", "fastfoodrestaurant",
    "bakery", "brewery", "winery", "nightclub", "spa", "healthclub",
    "beautysalon", "automotivebusiness", "legalservice", "medicalbusiness",
    "professionalservice", "homeandconstructionbusiness",
})


# ----------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------

@dataclass
class ResultFeatures:
    """Extracted features for one search result. Exposed for debugging."""
    # Entity-homepage signals
    title_matches_entity_pattern: bool = False
    snippet_entity_signals: int = 0  # count of snippet patterns matched
    has_single_entity_schema: bool = False
    domain_contains_location: bool = False
    domain_contains_category: bool = False
    url_at_root: bool = False

    # Editorial-list signals
    title_matches_editorial_pattern: bool = False
    domain_is_known_editorial: bool = False
    domain_is_official_tourism: bool = False

    # Aggregator (treated neutrally)
    domain_is_known_aggregator: bool = False

    # Final composite scores
    entity_homepage_score: float = 0.0
    editorial_score: float = 0.0


# ----------------------------------------------------------------------
# Feature extraction
# ----------------------------------------------------------------------

def _normalize_domain(url: str) -> str:
    """Return the registered domain without subdomain or www prefix."""
    try:
        netloc = urlparse(url).netloc.lower()
    except (ValueError, TypeError):
        return ""
    netloc = netloc.removeprefix("www.")
    return netloc


def _second_level_domain(domain: str) -> str:
    """For 'farmpalmsprings.com' return 'farmpalmsprings'."""
    if not domain:
        return ""
    parts = domain.split(".")
    if len(parts) >= 2:
        return parts[-2]
    return parts[0]


def _url_depth(url: str) -> int:
    """Path depth. https://example.com/ -> 0, https://example.com/foo/bar -> 2."""
    try:
        path = urlparse(url).path.strip("/")
    except (ValueError, TypeError):
        return 0
    if not path:
        return 0
    return path.count("/") + 1


def _count_snippet_signals(snippet: str) -> int:
    if not snippet:
        return 0
    return sum(1 for pat in _ENTITY_SNIPPET_RES if pat.search(snippet))


def _title_is_entity_pattern(title: str) -> bool:
    if not title:
        return False
    return any(pat.search(title) for pat in _ENTITY_TITLE_RES)


def _title_is_editorial_pattern(title: str) -> bool:
    if not title:
        return False
    return any(pat.search(title) for pat in _EDITORIAL_TITLE_RES)


def _is_official_tourism(domain: str) -> bool:
    return any(pat.match(domain) for pat in _OFFICIAL_TOURISM_RES)


def _domain_contains_token(domain_sld: str, token: str) -> bool:
    """
    Substring match on the second-level domain. Locations like 'Palm Springs'
    get joined to 'palmsprings'. Catches farmpalmsprings, clandestinopalmsprings,
    spencersrestaurant, etc.
    """
    if not domain_sld or not token:
        return False
    needle = re.sub(r"[^a-z0-9]", "", token.lower())
    if len(needle) < 4:
        # Too short, would false-positive on common substrings
        return False
    return needle in domain_sld


def _has_single_entity_schema(result: dict[str, Any]) -> bool:
    """
    Check for single-entity LocalBusiness schema if the SERP API surfaced it.
    Different providers expose this differently:
        - Serper sometimes includes a 'type' field at the top level
        - Brave sometimes includes a 'rich' or 'subtype' field
        - Custom: a 'schema_types' list set during a deeper extraction pass
    """
    candidates = []
    for key in ("type", "subtype", "schema_type", "page_type"):
        val = result.get(key)
        if isinstance(val, str):
            candidates.append(val.lower())
    for key in ("schema_types", "types"):
        val = result.get(key)
        if isinstance(val, (list, tuple)):
            candidates.extend(str(v).lower() for v in val)

    return any(c in SINGLE_ENTITY_SCHEMA_TYPES for c in candidates)


def extract_features(
    result: dict[str, Any],
    intent: IntentResult,
) -> ResultFeatures:
    """
    Run all detectors on one result. Combine into composite scores.
    Pure function; safe to memoize per (url, query) pair if it becomes hot.
    """
    url = result.get("url") or result.get("link") or ""
    title = result.get("title") or ""
    snippet = (
        result.get("description")
        or result.get("snippet")
        or result.get("body")
        or ""
    )

    domain = _normalize_domain(url)
    sld = _second_level_domain(domain)

    f = ResultFeatures()
    f.url_at_root = _url_depth(url) <= 1
    f.title_matches_entity_pattern = _title_is_entity_pattern(title)
    f.title_matches_editorial_pattern = _title_is_editorial_pattern(title)
    f.snippet_entity_signals = _count_snippet_signals(snippet)
    f.has_single_entity_schema = _has_single_entity_schema(result)
    f.domain_is_known_editorial = domain in EDITORIAL_DOMAINS
    f.domain_is_official_tourism = _is_official_tourism(domain)
    f.domain_is_known_aggregator = domain in KNOWN_AGGREGATORS

    if intent.location and intent.location != "__GEOLOCATION__":
        f.domain_contains_location = _domain_contains_token(sld, intent.location)
    if intent.category:
        # Category sometimes plural ('restaurants'), check singular too
        f.domain_contains_category = (
            _domain_contains_token(sld, intent.category)
            or any(
                _domain_contains_token(sld, sing)
                for sing in CATEGORY_NOUNS_SINGULAR
                if sing in intent.category
            )
        )

    f.entity_homepage_score = _compute_entity_score(f)
    f.editorial_score = _compute_editorial_score(f)
    return f


def _compute_entity_score(f: ResultFeatures) -> float:
    """
    Composite 0-1 score. Requires multiple co-firing signals for high values.
    Single signals stay low. This is the precision-over-recall rule from the spec.
    """
    if f.domain_is_known_editorial or f.domain_is_official_tourism:
        return 0.0  # explicit allow-list

    score = 0.0
    if f.title_matches_entity_pattern:
        score += 0.35
    if f.snippet_entity_signals >= 1:
        score += 0.20
    if f.snippet_entity_signals >= 2:
        score += 0.15  # additional signal stack
    if f.has_single_entity_schema:
        score += 0.30
    if f.domain_contains_location and f.domain_contains_category:
        score += 0.30  # the farmpalmsprings.com / clandestinopalmsprings.com case
    elif f.domain_contains_location:
        score += 0.15
    elif f.domain_contains_category:
        score += 0.10
    if f.url_at_root:
        score += 0.10

    # Require co-firing: any one signal alone caps at ~0.35
    # Two signals can reach ~0.55. Three+ can hit 0.85+.
    return min(1.0, score)


def _compute_editorial_score(f: ResultFeatures) -> float:
    score = 0.0
    if f.domain_is_known_editorial:
        score += 0.60
    if f.domain_is_official_tourism:
        score += 0.40
    if f.title_matches_editorial_pattern:
        score += 0.30
    if f.domain_is_known_aggregator:
        # Aggregators are not editorial, but not entity either
        score = max(score, 0.10)
    return min(1.0, score)


# ----------------------------------------------------------------------
# Shared reranking constants and helpers
# ----------------------------------------------------------------------

# Tuning constants. Conservative defaults. Adjust with benchmark feedback.
_ENTITY_PENALTY_STRENGTH = 0.55   # max multiplicative downweight (LIST)
_EDITORIAL_BOOST_STRENGTH = 0.45  # max additive boost (LIST)
_QUALITY_SCORE_KEY = "quality_score"
_RERANK_SCORE_KEY = "rerank_score"
_RERANK_FEATURES_KEY = "rerank_features"


def _base_score(result: dict[str, Any], index: int) -> float:
    """
    Get the result's existing quality score. Fall back to rank-based if missing.
    Cerulean's pipeline stores numeric scores; production should pass them in.
    """
    score = result.get(_QUALITY_SCORE_KEY)
    if isinstance(score, (int, float)):
        return float(score)
    # Synthetic score: position 0 -> 1.0, position N -> ~0.05
    return max(0.05, 1.0 - (index * 0.05))


# ----------------------------------------------------------------------
# List-intent reranker (Layers 2 + 3)
# ----------------------------------------------------------------------

def rerank_for_list_intent(
    results: list[dict[str, Any]],
    intent: IntentResult,
    *,
    debug: bool = False,
) -> list[dict[str, Any]]:
    """
    Re-rank results for a LIST-intent query.

    Returns a new list, sorted descending by adjusted score. Each result gets
    a `rerank_score` field added. With debug=True, results also get a
    `rerank_features` field for inspection.

    Idempotent: existing rerank_score and rerank_features fields are overwritten.
    """
    if intent.intent is not Intent.LIST:
        return results  # No-op for non-list intent

    annotated: list[tuple[float, int, dict[str, Any]]] = []

    for idx, r in enumerate(results):
        features = extract_features(r, intent)
        base = _base_score(r, idx)

        # Entity penalty: multiplicative
        entity_mult = 1.0 - (features.entity_homepage_score * _ENTITY_PENALTY_STRENGTH)
        # Editorial boost: additive
        editorial_add = features.editorial_score * _EDITORIAL_BOOST_STRENGTH

        new_score = (base * entity_mult) + editorial_add
        new_score = max(0.0, min(2.0, new_score))

        # Attach to the result (do not mutate caller's dict in place)
        out = dict(r)
        out[_RERANK_SCORE_KEY] = round(new_score, 4)
        if debug:
            out[_RERANK_FEATURES_KEY] = {
                "entity_homepage_score": round(features.entity_homepage_score, 3),
                "editorial_score": round(features.editorial_score, 3),
                "base_score": round(base, 3),
                "entity_multiplier": round(entity_mult, 3),
                "editorial_additive": round(editorial_add, 3),
                "signals": {
                    "title_entity": features.title_matches_entity_pattern,
                    "title_editorial": features.title_matches_editorial_pattern,
                    "snippet_signals": features.snippet_entity_signals,
                    "schema_entity": features.has_single_entity_schema,
                    "domain_loc": features.domain_contains_location,
                    "domain_cat": features.domain_contains_category,
                    "domain_editorial": features.domain_is_known_editorial,
                    "domain_official": features.domain_is_official_tourism,
                    "domain_aggregator": features.domain_is_known_aggregator,
                    "url_root": features.url_at_root,
                },
            }
        annotated.append((new_score, idx, out))

    # Sort by new score descending. Stable on ties via original index.
    annotated.sort(key=lambda t: (-t[0], t[1]))
    return [t[2] for t in annotated]


# ----------------------------------------------------------------------
# Graded domain-match boost (Layer 5, refactored)
# ----------------------------------------------------------------------

# Fires for all non-LIST intents. Computes a domain-match score against the
# query and applies a boost whose magnitude scales with intent type.
#
# The previous version was a binary gate: NAV intent -> strong boost, anything
# else -> no boost. That underserved the majority case where users type brand
# names in lowercase ("ebay") and the classifier falls back to INFORMATIONAL
# because lowercase brand detection is ambiguous (could be brand, could be
# the common noun).
#
# Graded model: intent confidence determines boost STRENGTH, not whether
# boosting happens. Lowercase brand queries get a modest boost that lifts
# canonical destinations near the top without pinning them. If the result
# set turns out to be genuinely ambiguous (e.g., "apple" returning both
# Apple Inc. and apple-the-fruit content), the ambiguity detector flags it
# and the UI surfaces filter chips for the user to navigate.

_NAV_EXACT_MATCH_SCORE = 1.0
_NAV_CORPORATE_MATCH_SCORE = 0.55  # ebayinc.com when query is "ebay"
_NAV_SUBSTRING_MATCH_SCORE = 0.30
_NAV_PATH_MATCH_SCORE = 0.10       # instagram.com/ebay
_NAV_BOOST_STRENGTH = 2.5          # peak boost; modulated by intent factor below

# How strongly to apply the domain-match boost per intent type.
# Tuned conservatively. LIST is zero because the list reranker handles
# its own logic and a domain-match boost would conflict with editorial bias.
_INTENT_BOOST_FACTORS: dict[str, float] = {
    "navigational": 1.0,    # confident brand intent - full boost
    "entity": 0.4,          # brand + qualifier - moderate boost
    "informational": 0.3,   # uncertain - modest boost, covers lowercase brands
    "list": 0.0,            # list reranker handles this path
}


def _normalize_query_for_domain_match(query: str) -> str:
    """Strip non-alphanumerics, lowercase. 'In-N-Out' -> 'innout'."""
    return re.sub(r"[^a-z0-9]", "", query.lower())


def _strip_entity_qualifiers(query: str) -> str:
    """
    Remove entity qualifier words from a query. Used before domain matching
    for ENTITY intent so 'starbucks hours' matches starbucks.com.
    """
    q = query
    for qual in ENTITY_QUALIFIERS:
        q = re.sub(rf"\b{re.escape(qual)}\b", " ", q, flags=re.IGNORECASE)
    return q


def _domain_match_score(url: str, query_norm: str) -> float:
    """
    How well does this URL's registered domain match the query?

    Returns:
        1.0  - SLD exactly matches query (ebay.com for "ebay")
        0.55 - SLD is query + corporate suffix (ebayinc.com for "ebay")
        0.30 - SLD contains query as substring (myebayshop.com)
        0.10 - URL path contains query (instagram.com/ebay)
        0.0  - no match
    """
    if not query_norm or len(query_norm) < 2:
        return 0.0

    domain = _normalize_domain(url)
    if not domain:
        return 0.0
    sld = _second_level_domain(domain)

    if sld == query_norm:
        return _NAV_EXACT_MATCH_SCORE

    # Corporate variants: ebayinc.com, openaiinc.com
    for suffix in ("inc", "corp", "co", "official"):
        if sld == query_norm + suffix:
            return _NAV_CORPORATE_MATCH_SCORE

    if query_norm in sld and len(query_norm) >= 4:
        return _NAV_SUBSTRING_MATCH_SCORE

    # Check path - "instagram.com/ebay", "facebook.com/ebay"
    try:
        path = urlparse(url).path.lower()
    except (ValueError, TypeError):
        path = ""
    if path:
        path_norm = re.sub(r"[^a-z0-9/]", "", path)
        if f"/{query_norm}" in path_norm:
            return _NAV_PATH_MATCH_SCORE

    return 0.0


def apply_graded_domain_boost(
    results: list[dict[str, Any]],
    intent: IntentResult,
    *,
    debug: bool = False,
) -> list[dict[str, Any]]:
    """
    Apply domain-match boost with strength varying by intent type.

    Re-sorts results descending by adjusted score. Pure function; does not
    mutate input.

    No-ops for LIST intent (the list reranker handles that path) and for
    queries that don't normalize to a usable form.
    """
    intent_key = intent.intent.value
    factor = _INTENT_BOOST_FACTORS.get(intent_key, 0.0)
    if factor == 0.0:
        return results

    # For ENTITY queries, strip the qualifier so we match on the brand portion
    # ("starbucks hours" -> domain-match against "starbucks", not "starbuckshours")
    clean_query = intent.raw_query
    if intent.intent is Intent.ENTITY:
        clean_query = _strip_entity_qualifiers(clean_query)

    query_norm = _normalize_query_for_domain_match(clean_query)
    if not query_norm:
        return results

    effective_strength = _NAV_BOOST_STRENGTH * factor

    annotated: list[tuple[float, int, dict[str, Any]]] = []
    for idx, r in enumerate(results):
        url = r.get("url") or r.get("link") or ""
        match_score = _domain_match_score(url, query_norm)
        base = _base_score(r, idx)
        boost = match_score * effective_strength
        new_score = base + boost

        out = dict(r)
        out[_RERANK_SCORE_KEY] = round(new_score, 4)
        if debug:
            out[_RERANK_FEATURES_KEY] = {
                "domain_match_score": round(match_score, 3),
                "base_score": round(base, 3),
                "intent_factor": factor,
                "effective_strength": round(effective_strength, 3),
                "domain_boost": round(boost, 3),
            }
        annotated.append((new_score, idx, out))

    annotated.sort(key=lambda t: (-t[0], t[1]))
    return [t[2] for t in annotated]


# Backward-compat alias - existing imports keep working
rerank_for_navigational_intent = apply_graded_domain_boost


# ----------------------------------------------------------------------
# Dispatch
# ----------------------------------------------------------------------

def rerank(
    results: list[dict[str, Any]],
    intent: IntentResult,
    *,
    debug: bool = False,
) -> list[dict[str, Any]]:
    """
    Dispatch reranker based on intent. Single entry point for the rerank stage.

    LIST intent: editorial boost + entity-homepage penalty
    All other intents: graded domain-match boost (modest for INFO, strong for NAV)
    """
    if intent.intent is Intent.LIST:
        return rerank_for_list_intent(results, intent, debug=debug)
    return apply_graded_domain_boost(results, intent, debug=debug)

