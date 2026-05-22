from __future__ import annotations

import html as _html
import os
import re as _re
import datetime as _dt
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import requests
from duckduckgo_search import DDGS

from models import SearchResult
from source_categorizer import categorize

_TAG_RE = _re.compile(r"<[^>]+>")
_WS_RE = _re.compile(r"\s+")

def _strip_html(text):
    if not text:
        return ""
    s = _TAG_RE.sub("", text)
    s = _html.unescape(s)
    s = _WS_RE.sub(" ", s).strip()
    return s

def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

def brave_search(query: str, count: int = 10) -> List[SearchResult]:
    # Brave Search API: https://api.search.brave.com/app/documentation/web-search/get-started
    key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not key:
        raise RuntimeError("BRAVE_SEARCH_API_KEY not set")
    count = min(count, 20)  # Brave API caps at 20

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": key,
    }
    params = {"q": query, "count": str(count)}
    r = requests.get(url, headers=headers, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    out: List[SearchResult] = []
    for item in (data.get("web", {}) or {}).get("results", [])[:count]:
        link = item.get("url") or ""
        if not link:
            continue
        out.append(SearchResult(
            title=_strip_html(item.get("title")) or link,
            url=link,
            snippet=_strip_html(item.get("description")),
            source="brave",
            published=item.get("age") or None,
            domain=_domain(link),
            source_type=categorize(link),
        ))
    return out

def serper_search(query: str, count: int = 10, prefer_recent_days: Optional[int] = None) -> List[SearchResult]:
    # Serper (Google results via API): https://serper.dev/
    key = os.environ.get("SERPER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("SERPER_API_KEY not set")

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": key, "Content-Type": "application/json"}
    payload: Dict[str, Any] = {"q": query, "num": min(count, 10)}
    if prefer_recent_days is not None:
        # Serper supports "tbs" for date constraints via Google syntax (e.g., qdr:d7)
        # We'll approximate via qdr.
        days = int(prefer_recent_days)
        if days <= 1:
            payload["tbs"] = "qdr:d"
        elif days <= 7:
            payload["tbs"] = "qdr:w"
        elif days <= 30:
            payload["tbs"] = "qdr:m"
        else:
            payload["tbs"] = "qdr:y"

    r = requests.post(url, headers=headers, json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()

    out: List[SearchResult] = []

    # Explicitly ignore ads
    organic = data.get("organic", []) or []
    for item in organic[:count]:
        link = item.get("link") or ""
        if not link:
            continue
        out.append(SearchResult(
            title=_strip_html(item.get("title")) or link,
            url=link,
            snippet=_strip_html(item.get("snippet")),
            source="serper",
            published=item.get("date") or None,
            domain=_domain(link),
            source_type=categorize(link),
        ))
    return out

def ddg_search(query: str, count: int = 10) -> List[SearchResult]:
    # DuckDuckGo results (scraped via library). Not Google; used as a no-key fallback.
    out: List[SearchResult] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=count):
            link = item.get("href") or item.get("url") or ""
            if not link:
                continue
            out.append(SearchResult(
                title=_strip_html(item.get("title")) or link,
                url=link,
                snippet=_strip_html(item.get("body")),
                source="ddg",
                published=None,
                domain=_domain(link),
            source_type=categorize(link),
            ))
    return out
