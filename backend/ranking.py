from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple, Set, Dict
from urllib.parse import urlparse, parse_qs

from models import SearchResult, SearchRequest

_STOP = {
    "a","an","the","and","or","but","if","then","else","when","where","why","how",
    "to","of","in","on","for","with","as","by","at","from","into","over","under",
    "is","are","was","were","be","been","being","it","this","that","these","those",
    "you","your","yours","we","our","ours","they","their","them","i","me","my","mine",
}

_AFFIL_PATTERNS = [
    r"utm_", r"aff", r"affiliate", r"ref=", r"refid", r"coupon", r"deal", r"tag=",
    r"gclid", r"fbclid", r"msclkid", r"igshid",
]

_COMMERCE_DOMAINS = {
    "amazon.com","amzn.to","ebay.com","walmart.com","target.com","bestbuy.com",
    "homedepot.com","lowes.com","etsy.com","aliexpress.com","temu.com","shein.com",
}

_OFFICIAL_TLDS = {".gov", ".edu"}
_OFFICIAL_HOST_HINTS = ("docs.", "developer.", "api.", "support.", "help.", "standards", "ietf", "w3.org")

# Source types that get a quality boost when quality_boost=True.
# These are editorial / vetted sources that the wrapper layer should promote
# over equally-relevant commercial or unknown content.
_EDITORIAL_SOURCE_TYPES = {
    "academic":  0.20,
    "gov":       0.18,
    "reference": 0.15,
    "news":      0.10,
    "docs":      0.10,
}
# Source types that get demoted when quality_boost=True.
_DEMOTED_SOURCE_TYPES = {
    "ai_slop":    -0.40,
    "commercial": -0.15,
}

def _tokenize(s: str) -> List[str]:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    toks = [t for t in s.split() if t and t not in _STOP]
    return toks

def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

def _tld(domain: str) -> str:
    # returns '.gov' etc if found
    for tld in _OFFICIAL_TLDS:
        if domain.endswith(tld):
            return tld
    return ""

def _has_tracking(url: str) -> bool:
    try:
        q = parse_qs(urlparse(url).query)
        for k in q.keys():
            if k.lower().startswith("utm_"):
                return True
        # also scan raw
        raw = url.lower()
        return any(p in raw for p in ("gclid=", "fbclid=", "msclkid=", "igshid="))
    except Exception:
        return False

def _commercialish(url: str, title: str, snippet: str) -> bool:
    u = url.lower()
    d = _domain(url)
    if d in _COMMERCE_DOMAINS:
        return True
    if any(re.search(p, u) for p in _AFFIL_PATTERNS):
        return True
    t = (title + " " + snippet).lower()
    if any(w in t for w in ("best ", "top ", "coupon", "discount", "deal", "promo code", "review roundup")):
        return True
    return False

def _officialish(domain: str) -> bool:
    if _tld(domain) in _OFFICIAL_TLDS:
        return True
    if any(domain.startswith(h) for h in _OFFICIAL_HOST_HINTS):
        return True
    return False

def _relevance_score(query: str, title: str, snippet: str) -> float:
    qtoks = set(_tokenize(query))
    if not qtoks:
        return 0.0
    dtoks = _tokenize(title + " " + snippet)
    if not dtoks:
        return 0.0
    overlap = sum(1 for t in dtoks if t in qtoks)
    return overlap / max(6, len(qtoks))

def rerank(req: SearchRequest, results: List[SearchResult]) -> List[SearchResult]:
    # Deduplicate by URL (normalized) and keep best snippet/title.
    seen: Set[str] = set()
    uniq: List[SearchResult] = []
    for r in results:
        key = str(r.url).split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    domain_counts: Dict[str, int] = {}
    for r in uniq:
        domain_counts[r.domain] = domain_counts.get(r.domain, 0) + 1

    # Quality Boost gates the opinionated overlays. When off, only baseline
    # signals (relevance, dedup, tracking) apply.
    boost = getattr(req, "quality_boost", True)

    scored: List[SearchResult] = []
    for r in uniq:
        reasons: List[str] = []
        score = 0.0

        rel = _relevance_score(req.q, r.title, r.snippet)
        score += 0.60 * rel
        if rel > 0.0:
            reasons.append(f"relevance:{rel:.2f}")

        # Prefer official sources (only when Quality Boost active)
        if boost and req.prefer_official and _officialish(r.domain):
            score += 0.25
            reasons.append("official:+0.25")

        # Demote commerce/affiliate material (only when Quality Boost active)
        if boost and req.no_commerce and _commercialish(str(r.url), r.title, r.snippet):
            score -= 0.35
            reasons.append("commerce:-0.35")

        # Editorial source-type lift (only when Quality Boost active)
        if boost:
            lift = _EDITORIAL_SOURCE_TYPES.get(r.source_type)
            if lift:
                score += lift
                reasons.append(f"editorial:+{lift:.2f}")
            penalty = _DEMOTED_SOURCE_TYPES.get(r.source_type)
            if penalty:
                score += penalty
                reasons.append(f"low-quality:{penalty:.2f}")

        # Tracking penalty (always on)
        if _has_tracking(str(r.url)):
            score -= 0.10
            reasons.append("tracking:-0.10")

        # Domain repetition penalty (always on)
        if domain_counts.get(r.domain, 0) > 2:
            score -= 0.05 * (domain_counts[r.domain] - 2)
            reasons.append("dupdomain:-")

        # Allow/block filters
        if req.allow_domains:
            if r.domain not in {d.lower() for d in req.allow_domains}:
                score -= 0.50
                reasons.append("not-allowlisted:-0.50")
        if req.block_domains:
            if r.domain in {d.lower() for d in req.block_domains}:
                score -= 1.00
                reasons.append("blocklisted:-1.00")

        r.score = float(score)
        r.reasons = reasons
        scored.append(r)

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored
