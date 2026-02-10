import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
PUBLIC_DIR = PROJECT_ROOT / "public"

for p in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

try:
    from backend.models import SearchRequest, SearchResponse
    from backend.search_providers import brave_search, serper_search, ddg_search
    from backend.ranking import rerank
    from backend.summarizer import synthesize
except Exception:
    from models import SearchRequest, SearchResponse
    from search_providers import brave_search, serper_search, ddg_search
    from ranking import rerank
    from summarizer import synthesize

app = FastAPI(
    title="Cerulean Search API",
    version="0.1.0",
    description="Ad-minimized, quality-weighted search API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static file routes ---

@app.get("/")
def serve_index():
    p = PUBLIC_DIR / "index.html"
    if p.exists():
        return FileResponse(str(p), media_type="text/html")
    return Response(content="Cerulean Search API is running. Visit /docs for API documentation.", media_type="text/plain")

@app.get("/styles.css")
def styles():
    p = PUBLIC_DIR / "styles.css"
    if p.exists():
        return FileResponse(str(p), media_type="text/css")
    raise HTTPException(status_code=404)

@app.get("/app.js")
def appjs():
    p = PUBLIC_DIR / "app.js"
    if p.exists():
        return FileResponse(str(p), media_type="application/javascript")
    raise HTTPException(status_code=404)

@app.get("/favicon.ico")
def favicon_ico():
    p = PUBLIC_DIR / "favicon.ico"
    if p.exists():
        return FileResponse(str(p))
    return Response(status_code=204)

@app.get("/favicon.png")
def favicon_png():
    p = PUBLIC_DIR / "favicon.png"
    if p.exists():
        return FileResponse(str(p), media_type="image/png")
    return Response(status_code=204)

# --- API routes ---

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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Provider error: {type(e).__name__}: {e}")

    ranked = rerank(req, raw)

    syn = []
    if req.synthesize:
        try:
            syn = synthesize(
                ranked,
                fetch_top_n=req.fetch_top_n,
                max_bullets=req.max_summary_bullets,
                max_chars=req.max_summary_chars
            )
        except Exception:
            syn = []

    return SearchResponse(
        query=req.q,
        provider=req.provider,
        results=ranked,
        synthesis=syn,
        meta={
            "count_requested": req.count,
            "count_returned": len(ranked),
            "no_commerce": req.no_commerce,
            "prefer_official": req.prefer_official,
            "prefer_recent_days": req.prefer_recent_days,
        },
    )
