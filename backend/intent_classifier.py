"""
Query intent classifier (Layer 1 of the ranking refinement pipeline).

Classifies a query into one of four intents:
    LIST          - "[category] in [location]" - user wants a curated list
    ENTITY        - "[brand] hours" - user wants a specific business
    INFORMATIONAL - "how does X work" - user wants an answer
    NAVIGATIONAL  - "X" alone - user wants to reach a known site

The LIST classification is the one that gates downstream penalty layers in
list_intent_reranker. Other intents bypass reranking and pass through with
the existing pipeline's behavior unchanged.

Pure functions. No I/O. No async. Sub-millisecond per call on realistic
queries. Designed to be swappable with an ML classifier later: same input,
same output shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .intent_lexicons import (
    CATEGORY_NOUNS_PLURAL,
    CATEGORY_NOUNS_SINGULAR,
    ENTITY_QUALIFIERS,
    LIST_MODIFIERS,
    LOCATION_ABBREVIATIONS,
    LOCATION_PREPOSITIONS,
    MULTI_WORD_CATEGORIES,
    MULTI_WORD_MODIFIERS,
    NEAR_ME_PATTERNS,
    QUESTION_WORDS,
    US_STATE_CODES,
    singularize_to_plural,
)


# ----------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------

class Intent(str, Enum):
    LIST = "list"
    ENTITY = "entity"
    INFORMATIONAL = "informational"
    NAVIGATIONAL = "navigational"


@dataclass
class IntentSignals:
    """All detected signals. Exposed for debugging and tuning."""
    has_category: bool = False
    category_plural: bool = False
    has_location: bool = False
    has_near_me: bool = False
    has_list_modifier: bool = False
    has_entity_qualifier: bool = False
    has_question_word: bool = False
    has_count_pattern: bool = False  # "10 best", "top 5"
    token_count: int = 0


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    category: Optional[str] = None
    location: Optional[str] = None
    modifiers: list[str] = field(default_factory=list)
    signals: IntentSignals = field(default_factory=IntentSignals)
    raw_query: str = ""

    def is_list(self) -> bool:
        return self.intent is Intent.LIST

    def is_entity(self) -> bool:
        return self.intent is Intent.ENTITY

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.value,
            "confidence": round(self.confidence, 3),
            "category": self.category,
            "location": self.location,
            "modifiers": self.modifiers,
        }


# ----------------------------------------------------------------------
# Compiled patterns
# ----------------------------------------------------------------------

# "best 10" / "top 5" / "10 best"
_COUNT_PATTERN_RE = re.compile(
    r"\b(?:top|best)\s+\d+\b|\b\d+\s+(?:best|top|greatest|essential|notable)\b",
    re.IGNORECASE,
)

# Captures location after "in/near/around X" with capitalized words
_LOCATION_TRIGGER_RE = re.compile(
    r"\b(?:in|near|around|at|outside|inside)\s+"
    r"([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+){0,3})",
)

# "Palm Springs CA" - city plus state code
_CITY_STATE_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})\s+([A-Z]{2})\b",
)

# Geolocation marker - kept as a sentinel string so callers know to fetch coords
GEOLOCATION_SENTINEL = "__GEOLOCATION__"


# ----------------------------------------------------------------------
# Detection helpers
# ----------------------------------------------------------------------

def _detect_category(query_lower: str) -> tuple[Optional[str], bool]:
    """
    Return (category_canonical_form, is_plural).
    Plural matches are returned as-is. Singular matches are returned in their
    canonical plural form for downstream consistency.
    """
    # Multi-word phrases first, longest match
    for phrase in MULTI_WORD_CATEGORIES:
        if phrase in query_lower:
            return phrase, True

    # Single tokens
    tokens = re.findall(r"[a-zA-Z]+", query_lower)
    for tok in tokens:
        if tok in CATEGORY_NOUNS_PLURAL:
            return tok, True
        if tok in CATEGORY_NOUNS_SINGULAR:
            plural = singularize_to_plural(tok) or tok
            return plural, False

    return None, False


def _detect_modifiers(query_lower: str) -> list[str]:
    found = []
    # Multi-word first to avoid double-counting "highest rated" + "highest"
    for phrase in MULTI_WORD_MODIFIERS:
        if phrase in query_lower:
            found.append(phrase)

    tokens = set(re.findall(r"[a-zA-Z\-]+", query_lower))
    for mod in LIST_MODIFIERS:
        if mod in tokens:
            found.append(mod)

    # Dedup while preserving first-seen order
    seen = set()
    return [m for m in found if not (m in seen or seen.add(m))]


def _detect_entity_qualifier(query_lower: str) -> bool:
    tokens = set(re.findall(r"[a-zA-Z]+", query_lower))
    return bool(tokens & ENTITY_QUALIFIERS)


def _detect_near_me(query_lower: str) -> bool:
    return any(phrase in query_lower for phrase in NEAR_ME_PATTERNS)


_STOPWORDS_FOR_RESIDUE = frozenset({
    "in", "near", "around", "at", "by", "of", "the", "a", "an",
    "to", "for", "and", "or", "with", "from", "outside", "inside",
})


def _detect_location(
    query: str,
    query_lower: str,
    category: Optional[str],
    modifiers: list[str],
) -> Optional[str]:
    """
    Best-effort location extraction. Returns None when no signal.
    Returns GEOLOCATION_SENTINEL for "near me" queries.

    Heuristics, in priority order:
        1. "near me" / "nearby" / etc.
        2. Trigger preposition + capitalized run
        3. City + US state code ("Palm Springs CA")
        4. Leading capitalized run not matching a category
        5. Known location abbreviation
        6. Category-anchored residue (handles lowercase queries)
    """
    if _detect_near_me(query_lower):
        return GEOLOCATION_SENTINEL

    m = _LOCATION_TRIGGER_RE.search(query)
    if m:
        return m.group(1).strip()

    m = _CITY_STATE_RE.search(query)
    if m and m.group(2).lower() in US_STATE_CODES:
        return f"{m.group(1)} {m.group(2)}"

    # Leading capitalized run - "Palm Springs restaurants" -> "Palm Springs"
    tokens = query.split()
    cap_run: list[str] = []
    for tok in tokens:
        cleaned = re.sub(r"[^\w]", "", tok)
        if not cleaned:
            break
        if cleaned[0].isupper() and cleaned.lower() not in CATEGORY_NOUNS_PLURAL \
                and cleaned.lower() not in CATEGORY_NOUNS_SINGULAR \
                and cleaned.lower() not in LIST_MODIFIERS:
            cap_run.append(cleaned)
        else:
            break
    if cap_run and 1 <= len(cap_run) <= 4:
        candidate = " ".join(cap_run)
        if candidate.lower() not in {"best", "top", "great"}:
            return candidate

    # Known abbreviations anywhere
    for tok in tokens:
        cleaned = re.sub(r"[^\w]", "", tok).lower()
        if cleaned in LOCATION_ABBREVIATIONS:
            return cleaned.upper()

    # Fallback: residue-based location.
    # Run when we have either a category or a list modifier to anchor against.
    # Everything else that isn't a stopword or known signal token is the
    # candidate location. Handles lowercase queries like "palm springs
    # restaurants" or "best pizza brooklyn".
    if category or modifiers:
        residue = query_lower
        if category:
            residue = residue.replace(category, " ", 1)
        for cat_word in CATEGORY_NOUNS_PLURAL | CATEGORY_NOUNS_SINGULAR:
            if " " not in cat_word:
                residue = re.sub(rf"\b{re.escape(cat_word)}\b", " ", residue)
        for mod in modifiers:
            residue = residue.replace(mod, " ")
        for qual in ENTITY_QUALIFIERS:
            residue = re.sub(rf"\b{re.escape(qual)}\b", " ", residue)
        tokens_residue = [
            t for t in re.findall(r"[a-z][a-z\-]*", residue)
            if t not in _STOPWORDS_FOR_RESIDUE
        ]
        if 1 <= len(tokens_residue) <= 4:
            candidate = " ".join(tok.capitalize() for tok in tokens_residue)
            return candidate

    return None


def _looks_like_brand(query: str, query_lower: str) -> bool:
    """
    Heuristic: 1-3 tokens that look like a brand name.

    Two recognition modes:
        1. Standard: most tokens start with capital ("Burger King", "OpenTable")
        2. CamelCase / internal caps: any token has an uppercase letter
           beyond position 0 ("eBay", "iPhone", "macOS", "BlackBerry")

    Disqualifiers (any of these blocks brand detection):
        - Entity qualifier present ("starbucks hours" - ENTITY, not NAV)
        - List modifier present ("best pizza" - LIST)
        - Last token is a plural category ("Palm Springs Restaurants" - LIST)

    Singular category words within the query are allowed because brand names
    can contain them ("Pizza Hut", "Burger King"). Rule precedence in _score
    handles disambiguation via the entity qualifier and list modifier checks.
    """
    tokens = query.split()
    if not 1 <= len(tokens) <= 3:
        return False
    if _detect_entity_qualifier(query_lower):
        return False
    if any(tok.lower() in LIST_MODIFIERS for tok in tokens):
        return False
    last_lower = re.sub(r"[^\w]", "", tokens[-1]).lower()
    if last_lower in CATEGORY_NOUNS_PLURAL:
        return False

    # Mode 1: most tokens start capitalized
    capitalized = sum(1 for tok in tokens if tok and tok[0].isupper())
    if capitalized >= max(1, len(tokens) - 1):
        return True

    # Mode 2: camelCase / internal-caps brand names (eBay, iPhone, macOS)
    for tok in tokens:
        if len(tok) >= 2 and any(c.isupper() for c in tok[1:]):
            return True

    return False


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def classify(query: str) -> IntentResult:
    """
    Classify the intent of a search query.

    Idempotent, pure, ~100 microseconds on realistic queries.
    """
    if not query or not query.strip():
        return IntentResult(
            intent=Intent.INFORMATIONAL,
            confidence=0.0,
            raw_query=query or "",
        )

    raw = query.strip()
    q = raw.lower()

    category, is_plural = _detect_category(q)
    modifiers = _detect_modifiers(q)
    location = _detect_location(raw, q, category, modifiers)
    has_entity_qualifier = _detect_entity_qualifier(q)
    has_near_me = _detect_near_me(q)
    tokens = raw.split()
    has_question_word = bool(tokens) and tokens[0].lower() in QUESTION_WORDS
    has_count_pattern = bool(_COUNT_PATTERN_RE.search(q))

    signals = IntentSignals(
        has_category=category is not None,
        category_plural=is_plural,
        has_location=location is not None,
        has_near_me=has_near_me,
        has_list_modifier=bool(modifiers),
        has_entity_qualifier=has_entity_qualifier,
        has_question_word=has_question_word,
        has_count_pattern=has_count_pattern,
        token_count=len(tokens),
    )

    intent, confidence = _score(signals, raw, q)

    return IntentResult(
        intent=intent,
        confidence=confidence,
        category=category,
        location=location,
        modifiers=modifiers,
        signals=signals,
        raw_query=raw,
    )


def _score(signals: IntentSignals, raw: str, q: str) -> tuple[Intent, float]:
    """
    Decision tree. Order matters: more specific rules first.

    Precedence design notes:
        - Entity qualifier (hours, menu, reservations) is a strong entity
          signal, but plural category or list modifier overrides because
          "best coffee shops with reservations" is a list query.
        - Singular category alone is weak (it's typically descriptive); needs
          a list modifier or location to imply list intent.
        - Count patterns ("top 10") always imply list, even without category.
        - Conservative on LIST: false positives penalize legitimate entity
          results, false negatives only fail to clean up SERPs we'd otherwise
          have lived with.
    """
    plural_cat = signals.has_category and signals.category_plural
    singular_cat = signals.has_category and not signals.category_plural

    # Rule 1: leading question word + no category + no entity qualifier
    if signals.has_question_word and not signals.has_category \
            and not signals.has_entity_qualifier:
        return Intent.INFORMATIONAL, 0.85

    # Rule 2: entity qualifier dominates unless plural category or modifier present
    # Catches "starbucks hours", "spencer's restaurant reservations"
    if signals.has_entity_qualifier and not plural_cat and not signals.has_list_modifier:
        return Intent.ENTITY, 0.92

    # Rule 3: explicit count pattern always implies list
    if signals.has_count_pattern:
        return Intent.LIST, 0.95

    # Rule 4: plural category -> strong list intent
    if plural_cat:
        confidence = 0.75
        if signals.has_location:
            confidence += 0.15
        if signals.has_list_modifier:
            confidence += 0.05
        return Intent.LIST, min(0.97, confidence)

    # Rule 5: singular category + list modifier -> list intent
    if singular_cat and signals.has_list_modifier:
        confidence = 0.70
        if signals.has_location:
            confidence += 0.15
        return Intent.LIST, min(0.92, confidence)

    # Rule 6: brand-like (capitalized, short, no list modifier).
    # Must run before residue-based singular-cat+location rule because
    # "Burger King" will extract "King" as residue-location otherwise.
    # All brand-like queries route to NAVIGATIONAL; the previous token-count
    # split (single -> NAV, multi -> ENTITY) was arbitrary. "Shake Shack" is
    # just as navigational as "OpenTable". Entity qualifiers (already caught
    # by Rule 2) are what distinguishes ENTITY intent.
    if _looks_like_brand(raw, q):
        return Intent.NAVIGATIONAL, 0.70

    # Rule 7: singular category + location -> probable list
    if singular_cat and signals.has_location:
        return Intent.LIST, 0.60

    # Rule 8: list modifier + location, no category -> probable list
    if signals.has_list_modifier and signals.has_location:
        return Intent.LIST, 0.55

    # Rule 9: bare category (e.g., "restaurants" alone)
    if signals.has_category:
        return Intent.LIST, 0.55

    # Default: informational
    return Intent.INFORMATIONAL, 0.45
