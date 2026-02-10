from __future__ import annotations

import re
import time
import ipaddress
from urllib.parse import urlparse
from typing import List, Tuple, Dict, Optional

import requests
from readability import Document
from bs4 import BeautifulSoup

from models import SynthesisBullet, SearchResult

_STOP = set([
    "a","an","the","and","or","but","if","then","else","when","where","why","how",
    "to","of","in","on","for","with","as","by","at","from","into","over","under",
    "is","are","was","were","be","been","being","it","this","that","these","those",
    "you","your","yours","we","our","ours","they","their","them","i","me","my","mine",
])

def _is_private_netloc(netloc: str) -> bool:
    # Basic SSRF guard: block localhost and private IPs
    host = netloc.split(":")[0].strip().lower()
    if host in {"localhost"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except Exception:
        return False

def fetch_readable_text(url: str, timeout: int = 12, max_chars: int = 200_000) -> str:
    p = urlparse(url)
    if _is_private_netloc(p.netloc):
        return ""
    headers = {
        "User-Agent": "CeruleanSearch/1.0 (+https://example.local)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    html = r.text
    if len(html) > max_chars:
        html = html[:max_chars]

    doc = Document(html)
    content_html = doc.summary(html_partial=True)

    soup = BeautifulSoup(content_html, "lxml")
    text = soup.get_text("\n")
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()

def _sentences(text: str) -> List[str]:
    # Conservative sentence splitter
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[\.\!\?])\s+", text)
    sents = []
    for s in parts:
        s = s.strip()
        if 40 <= len(s) <= 280:
            sents.append(s)
    return sents

def _tokenize(s: str) -> List[str]:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    toks = [t for t in s.split() if t and t not in _STOP and len(t) > 2]
    return toks

def extractive_summary_bullets(texts: List[str], max_bullets: int = 5, max_chars: int = 1200) -> List[str]:
    corpus = " ".join(texts)
    sents = _sentences(corpus)
    if not sents:
        return []

    # term frequency
    freq: Dict[str, int] = {}
    for s in sents:
        for t in _tokenize(s):
            freq[t] = freq.get(t, 0) + 1
    if not freq:
        return []

    # score sentences
    scored: List[Tuple[float, str]] = []
    for s in sents:
        toks = _tokenize(s)
        if not toks:
            continue
        score = sum(freq.get(t, 0) for t in toks) / (len(toks) ** 0.75)
        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    bullets: List[str] = []
    used: set = set()
    total_chars = 0
    for _, s in scored:
        key = s.lower()
        if key in used:
            continue
        used.add(key)
        if total_chars + len(s) + 4 > max_chars:
            continue
        bullets.append(s)
        total_chars += len(s) + 4
        if len(bullets) >= max_bullets:
            break

    # Light rewrite: make them bullets without ending fragments
    cleaned = []
    for b in bullets:
        b = b.strip()
        if b and b[-1] not in ".!?":
            b += "."
        cleaned.append(b)
    return cleaned

def synthesize(results: List[SearchResult], fetch_top_n: int, max_bullets: int, max_chars: int) -> List[SynthesisBullet]:
    # Fetch readable text from top N results. Attach bullet citations to those sources.
    texts: List[str] = []
    cite_map: List[int] = []
    for idx, r in enumerate(results[:fetch_top_n], start=1):
        try:
            t = fetch_readable_text(str(r.url))
            if t:
                texts.append(t[:50_000])
                cite_map.append(idx)
        except Exception:
            continue

    # Fall back to snippets if fetch fails
    if not texts:
        texts = [(r.title + ". " + (r.snippet or "")).strip() for r in results[:max(1, fetch_top_n)]]
        cite_map = list(range(1, min(len(results), max(1, fetch_top_n)) + 1))

    bullets = extractive_summary_bullets(texts, max_bullets=max_bullets, max_chars=max_chars)

    out: List[SynthesisBullet] = []
    for b in bullets:
        out.append(SynthesisBullet(text=b, cites=cite_map[:]))
    return out
