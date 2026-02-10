from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from models import SearchRequest, SearchResponse, SearchResult
from search_providers import brave_search, serper_search, ddg_search
from ranking import rerank
from summarizer import synthesize

APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = (APP_DIR.parent / "frontend").resolve()

app = FastAPI(
    title="Cerulean Search API",
    version="0.1.0",
    description="Ad-minimized, quality-weighted search client with optional synthesis.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static GUI
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

@app.post("/api/search", response_model=SearchResponse)
def api_search(req: SearchRequest):
    try:
        if req.provider == "brave":
            raw = brave_search(req.q, count=req.count)
        elif req.provider == "serper":
            raw = serper_search(req.q, count=req.count, prefer_recent_days=req.prefer_recent_days)
        elif req.provider == "ddg":
            raw = ddg_search(req.q, count=req.count)
        else:
            raise HTTPException(status_code=400, detail="Unsupported provider")
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search provider error: {type(e).__name__}: {e}")

    ranked = rerank(req, raw)

    syn = []
    if req.synthesize:
        try:
            syn = synthesize(ranked, fetch_top_n=req.fetch_top_n, max_bullets=req.max_summary_bullets, max_chars=req.max_summary_chars)
        except Exception:
            syn = []

    meta: Dict[str, Any] = {
        "count_requested": req.count,
        "count_returned": len(ranked),
        "no_commerce": req.no_commerce,
        "prefer_official": req.prefer_official,
        "prefer_recent_days": req.prefer_recent_days,
    }

    return SearchResponse(
        query=req.q,
        provider=req.provider,
        results=ranked,
        synthesis=syn,
        meta=meta,
    )
