from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Literal, Dict, Any

Provider = Literal["brave", "serper", "ddg"]

class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=512)
    provider: Provider = "brave"
    count: int = Field(10, ge=1, le=25)

    # Filtering / ranking controls
    no_commerce: bool = True
    prefer_official: bool = True
    prefer_recent_days: Optional[int] = Field(None, ge=1, le=3650)

    # Domain filters
    block_domains: List[str] = Field(default_factory=list)
    allow_domains: List[str] = Field(default_factory=list)

    # Summarization controls
    synthesize: bool = True
    fetch_top_n: int = Field(3, ge=0, le=5)
    max_summary_bullets: int = Field(5, ge=1, le=10)
    max_summary_chars: int = Field(1200, ge=200, le=6000)

class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: str = ""
    source: str = ""
    published: Optional[str] = None  # ISO date or provider string
    domain: str = ""
    score: float = 0.0
    reasons: List[str] = Field(default_factory=list)

class SynthesisBullet(BaseModel):
    text: str
    cites: List[int] = Field(default_factory=list)  # 1-based indices into results

class SearchResponse(BaseModel):
    query: str
    provider: Provider
    results: List[SearchResult]
    synthesis: List[SynthesisBullet] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
