"""
backend/topic_extractor.py

Extracts a short "what is this page about" descriptor from a result's title +
snippet. No body fetch. No external calls. Pure regex over the data already
returned by the provider API.

The output is rendered under each result as a "Topic" callout when the
Summarize chip is on. It is intentionally short (~140 chars) and biased
toward definitional clauses ("X is a Y", "X refers to Z") because those
read like topic descriptors. When no definitional pattern fires, the
extractor returns None and the UI hides the callout for that result.

This is a v1 heuristic. It works well for reference and academic content
(Wikipedia, Britannica, .edu, .gov), acceptably for news ledes, and
inconsistently for blogs and commercial pages. That is the expected
distribution: topic callouts surface on the high-quality content where
they add the most value.
"""
from __future__ import annotations

import re
from typing import Optional

_MAX_TOPIC_LEN = 160

# Definitional patterns: capture the predicate after the copula.
# Group 1 is the descriptor we want to surface.
_DEFINITIONAL = [
    # "X is a/an/the Y..."
    re.compile(r"\b(?:is|are|was|were)\s+(?:a|an|the)\s+([^.;:!?]{8,160})", re.IGNORECASE),
    # "X refers to Y..."
    re.compile(r"\brefers?\s+to\s+([^.;:!?]{8,160})", re.IGNORECASE),
    # "X means Y..." / "X denotes Y..."
    re.compile(r"\b(?:means|denotes|describes)\s+([^.;:!?]{8,160})", re.IGNORECASE),
    # "Y is the field/study/practice of X..."
    re.compile(r"\b(?:the\s+)?(?:field|study|practice|discipline|branch|area)\s+of\s+([^.;:!?]{8,160})", re.IGNORECASE),
    # "X, the/a Y by which..." (comma-appositive)
    re.compile(r"^[A-Z][\w\s\-]{2,40},\s+((?:the|a|an)\s+[^.;:!?]{8,160})", re.IGNORECASE),
]

# Patterns we reject up front. Junk that often appears in snippets.
_BLOCKLIST_RE = re.compile(
    r"(?:cookie|sign in|log in|subscribe|privacy policy|terms of (?:use|service)"
    r"|search results|all rights reserved|javascript is)",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    if not text:
        return ""
    s = re.sub(r"\s+", " ", text).strip()
    # Strip trailing punctuation we don't want hanging
    s = s.rstrip(" ,;-")
    if len(s) > _MAX_TOPIC_LEN:
        # Cut at last space within limit to avoid mid-word truncation
        cut = s.rfind(" ", 0, _MAX_TOPIC_LEN)
        s = (s[:cut] if cut > 80 else s[:_MAX_TOPIC_LEN]).rstrip(" ,;-") + "…"
    return s


def extract_topic(title: str, snippet: str) -> Optional[str]:
    """
    Return a topic descriptor for a result, or None if no clean signal exists.

    Strategy:
      1. Search snippet for a definitional pattern. If found, return the
         captured predicate.
      2. If snippet starts with the title verbatim followed by a copula
         ("Quantum computing is..."), splice it as the topic.
      3. Otherwise return None. The UI hides the callout when None.
    """
    if not snippet:
        return None
    s = snippet.strip()
    if _BLOCKLIST_RE.search(s[:200]):
        return None

    # Try definitional patterns on the first 400 chars (limits regex cost)
    head = s[:400]
    for pat in _DEFINITIONAL:
        m = pat.search(head)
        if m:
            candidate = _clean(m.group(1))
            if candidate and len(candidate) >= 8:
                return candidate

    # Title-prefix fallback: "Quantum computing is a..." pattern where the
    # title appears verbatim at the start of the snippet.
    if title:
        t = title.strip()
        # Strip common Wikipedia/site suffixes from title
        t_short = re.split(r"\s+[\-|–—]\s+", t)[0].strip()
        if t_short and s.lower().startswith(t_short.lower()):
            tail = s[len(t_short):].lstrip(" ,:-")
            m = re.match(r"(?:is|are|was|were)\s+(?:a|an|the)?\s*([^.;:!?]{8,160})", tail, re.IGNORECASE)
            if m:
                candidate = _clean(m.group(1))
                if candidate and len(candidate) >= 8:
                    return candidate

    return None
