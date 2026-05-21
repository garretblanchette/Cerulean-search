"""
backend/ai_detector.py

Heuristic AI-content likelihood scoring. No network calls.
Operates on title + snippet + source_type. Returns float in [0, 1].

Components (additive, capped at 1.0):
  domain=ai_slop          +0.70
  title-pattern hits      +0.15 each (cap +0.40)
  LLM-tell phrase hits    +0.05 each (cap +0.40)
  em-dash density >2/100c +0.15
  no date + no named ent  +0.10
"""
import re

LLM_TELLS = (
    "delve into", "delving into", "navigate the complexit",
    "in today's fast-paced", "in today's digital",
    "it's important to note", "it is important to note",
    "let's explore", "let's dive", "in the realm of",
    "deep dive", "dive deep", "unlock the secret", "unlock the power",
    "the world of", "in conclusion,", "furthermore,", "moreover,",
    "in summary", "a testament to", "as we navigate",
    "embark on a journey", "the ever-evolving", "harness the power",
    "elevate your", "elevate the", "game-changer", "game changer",
    "in this article, we will", "look no further",
    "ultimate guide", "comprehensive guide", "the importance of",
)

TITLE_PATTERNS = (
    re.compile(r"^\d+\s+(best|top|ways|reasons|tips|things|secrets|amazing)", re.I),
    re.compile(r"^(top|best)\s+\d+", re.I),
    re.compile(r"\b(ultimate|complete|comprehensive)\s+guide\b", re.I),
    re.compile(r"^how\s+to\s+\w+\s+(in|with)\s+\d+", re.I),
    re.compile(r"\b(discover|unlock)\b", re.I),
    re.compile(r"^why\s+(every|you)\s", re.I),
    re.compile(r"\bgame[- ]chang(er|ing)\b", re.I),
    re.compile(r"\beverything\s+you\s+need\s+to\s+know\b", re.I),
)

YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
NAMED_ENTITY_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")


def score_ai_likelihood(title: str, snippet: str, source_type: str = "other") -> float:
    """Return AI-likelihood score in [0, 1]."""
    title = title or ""
    snippet = snippet or ""
    text = (title + " " + snippet).lower()
    score = 0.0

    if source_type == "ai_slop":
        score += 0.70

    score += min(0.40, sum(1 for p in TITLE_PATTERNS if p.search(title)) * 0.15)
    score += min(0.40, sum(1 for s in LLM_TELLS if s in text) * 0.05)

    if snippet:
        emdash = snippet.count("\u2014") + snippet.count("\u2013")
        if (emdash / len(snippet)) * 100 > 2:
            score += 0.15

    if len(snippet) > 50:
        if not YEAR_RE.search(snippet) and not NAMED_ENTITY_RE.search(snippet[1:]):
            score += 0.10

    return min(1.0, round(score, 2))


def score_results(results):
    """Mutate each result's ai_likelihood field in place."""
    for r in results:
        r.ai_likelihood = score_ai_likelihood(
            getattr(r, "title", "") or "",
            getattr(r, "snippet", "") or "",
            getattr(r, "source_type", "other"),
        )
