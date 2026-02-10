import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response

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

app = FastAPI(title="Cerulean Search API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# If / is routed to the function, bounce to the static file that Vercel serves.
@app.get("/")
def root():
    return RedirectResponse(url="/index.html")

# Optional: prevent favicon requests from causing noise
@app.get("/favicon.ico")
def favicon_ico():
    return Response(status_code=204)

@app.get("/favicon.png")
def favicon_png():
    return Response(status_code=204)

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
                max_chars=req.max_summary_chars,
            )
        except Exception:
            syn = []

    return SearchResponse(
        query=req.q,
        provider=req.provider,
        results=ranked,
        synthesis=syn,
        meta={"count_returned": len(ranked)},
    )
